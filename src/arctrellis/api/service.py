"""The read-only service over one already-analyzed snapshot.

This layer holds no analysis and no query logic. It parses a bounded JSON payload
into the same validated QueryRequest the CLI builds, calls the same run_query, and
returns the bundle's own serialization. The repository root is fixed at startup and
is not reachable from any request (D-148).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from arctrellis.orchestration import (
    AnalysisSnapshot,
    BundleStatus,
    InvalidQueryLimitError,
    InvalidQueryRequestError,
    QueryIntent,
    QueryRequest,
    SelectionStatus,
    UnsupportedIntentError,
    analyze_repository,
    run_query,
)

from .errors import (
    AmbiguousSelectionError,
    EntityNotFoundError,
    InvalidPayloadError,
    InvalidSourceError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
    UnsupportedOperationError,
    ValidationFailedError,
)

#: Fixed request bound. The payload is a small selector and limit object, so a
#: larger body is never legitimate and is rejected before parsing.
MAX_REQUEST_BYTES = 64 * 1024
JSON_CONTENT_TYPE = "application/json"

API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"

#: Intent names accepted over HTTP. Identical to the CLI aliases so one request
#: means the same thing in either surface.
INTENT_NAMES: Mapping[str, QueryIntent] = {
    "search-entities": QueryIntent.SEARCH_ENTITIES,
    "list-endpoints": QueryIntent.LIST_ENDPOINTS,
    "list-database-callers": QueryIntent.LIST_DATABASE_CALLERS,
    "trace-endpoint-to-database": QueryIntent.TRACE_ENDPOINT_TO_DATABASE,
    "trace-callable-to-database": QueryIntent.TRACE_CALLABLE_TO_DATABASE,
    "direct-database-operations": QueryIntent.DIRECT_DATABASE_OPERATIONS,
    "find-direct-tests": QueryIntent.FIND_DIRECT_TESTS,
    "find-callers": QueryIntent.FIND_CALLERS,
    "find-affected-endpoints": QueryIntent.FIND_AFFECTED_ENDPOINTS,
}

OPERATION_KINDS = ("read", "write", "delete")
LANGUAGES = ("python", "javascript", "typescript")
ENDPOINT_SCOPES = ("local", "declared", "effective", "application")

SEARCH_FIELDS = frozenset(
    {
        "text",
        "limit",
        "kind",
        "language",
        "path_prefix",
        "framework",
        "scope",
        "include_graph_context",
    }
)
QUERY_FIELDS = frozenset(
    {
        "intent",
        "text",
        "entity_id",
        "qualified_name",
        "method",
        "path",
        "kind",
        "language",
        "path_prefix",
        "framework",
        "scope",
        "operations",
        "include_graph_context",
        "transitive",
        "limit",
        "max_depth",
        "max_paths",
        "max_expansions",
    }
)
ENDPOINT_FIELDS = frozenset({"method", "path", "framework", "scope", "limit"})


def _require_object(payload: object, what: str) -> Mapping[str, Any]:
    if not isinstance(payload, dict):
        raise InvalidPayloadError(f"{what} must be a JSON object")
    for key in payload:
        if not isinstance(key, str):
            raise InvalidPayloadError(f"{what} keys must be strings")
    return payload


def _reject_unknown(payload: Mapping[str, Any], allowed: frozenset[str], what: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValidationFailedError(f"{what} does not accept {unknown}")


def _string(payload: Mapping[str, Any], name: str) -> str | None:
    value = payload.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationFailedError(f"{name} must be a string")
    return value


def _integer(payload: Mapping[str, Any], name: str) -> int | None:
    value = payload.get(name)
    if value is None:
        return None
    if type(value) is not int:
        raise ValidationFailedError(f"{name} must be an integer, not {type(value).__name__}")
    return value


def _boolean(payload: Mapping[str, Any], name: str) -> bool:
    value = payload.get(name, False)
    if type(value) is not bool:
        raise ValidationFailedError(f"{name} must be a boolean")
    return value


def _operations(payload: Mapping[str, Any]) -> frozenset[str] | None:
    value = payload.get("operations")
    if value is None:
        return None
    if not isinstance(value, list) or not value:
        raise ValidationFailedError("operations must be a nonempty list")
    requested: set[str] = set()
    for item in value:
        if not isinstance(item, str) or item.casefold() not in OPERATION_KINDS:
            raise ValidationFailedError(f"operations entries must be one of {list(OPERATION_KINDS)}")
        requested.add(item.casefold())
    return frozenset(requested)


def _build_request(payload: Mapping[str, Any], fields: frozenset[str], what: str) -> QueryRequest:
    """Translate a validated payload into a QueryRequest or raise a typed failure."""
    _reject_unknown(payload, fields, what)
    intent_name = _string(payload, "intent")
    if intent_name is None:
        raise ValidationFailedError("intent is required")
    intent = INTENT_NAMES.get(intent_name.casefold().replace("_", "-"))
    if intent is None:
        raise UnsupportedOperationError(f"unsupported intent {intent_name!r}; expected one of {sorted(INTENT_NAMES)}")
    method = _string(payload, "method")
    if method is not None:
        method = method.strip().upper()
    language = _string(payload, "language")
    if language is not None:
        language = language.casefold()
    scope = _string(payload, "scope")
    operations = _operations(payload)
    limit = _integer(payload, "limit")
    max_depth = _integer(payload, "max_depth")
    max_paths = _integer(payload, "max_paths")
    max_expansions = _integer(payload, "max_expansions")
    kwargs: dict[str, Any] = {
        "intent": intent,
        "entity_id": _string(payload, "entity_id"),
        "qualified_name": _string(payload, "qualified_name"),
        "http_method": method,
        "route_path": _string(payload, "path"),
        "search_text": _string(payload, "text"),
        "entity_kind": None,
        "language": language,
        "path_prefix": _string(payload, "path_prefix"),
        "framework": _string(payload, "framework"),
        "endpoint_scope": scope,
        "include_graph_context": _boolean(payload, "include_graph_context"),
        "transitive_callers": _boolean(payload, "transitive"),
    }
    if operations is not None:
        kwargs["operation_kinds"] = operations
    if limit is not None:
        kwargs["top_k"] = limit
    if max_depth is not None:
        kwargs["max_depth"] = max_depth
    if max_paths is not None:
        kwargs["max_paths"] = max_paths
    if max_expansions is not None:
        kwargs["max_expansions"] = max_expansions
    raw_kind = _string(payload, "kind")
    if raw_kind is not None:
        kwargs["entity_kind"] = _parse_entity_kind(raw_kind)
    try:
        return QueryRequest(**kwargs)
    except (InvalidQueryRequestError, InvalidQueryLimitError, UnsupportedIntentError) as error:
        raise ValidationFailedError(str(error)) from error


def _parse_entity_kind(value: str) -> Any:
    from arctrellis.core import EntityKind

    for kind in EntityKind:
        if kind.value.casefold() == value.casefold():
            return kind
        if kind.value.casefold().replace("_", "-") == value.casefold().replace("_", "-"):
            return kind
    raise ValidationFailedError(f"unknown entity kind {value!r}")


def decode_payload(body: bytes | None, content_type: str | None) -> Mapping[str, Any]:
    """Decode a bounded JSON request body into a validated object."""
    if body is None or body == b"":
        return {}
    if len(body) > MAX_REQUEST_BYTES:
        raise PayloadTooLargeError(f"request body must not exceed {MAX_REQUEST_BYTES} bytes, received {len(body)}")
    if content_type is not None and content_type.split(";")[0].strip().casefold() != JSON_CONTENT_TYPE:
        raise UnsupportedMediaTypeError(f"content type must be {JSON_CONTENT_TYPE}")
    try:
        decoded = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidPayloadError(f"body must be valid UTF-8 JSON: {type(error).__name__}") from error
    return _require_object(decoded, "request body")


def encode_payload(value: object) -> bytes:
    """Serialize a response deterministically as JSON."""
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8")


class AnalysisService:
    """Read-only operations over one analyzed snapshot.

    The root is bound once at construction. No method accepts a filesystem path,
    so no request can redirect the analysis at another repository.
    """

    def __init__(self, snapshot: AnalysisSnapshot) -> None:
        if not isinstance(snapshot, AnalysisSnapshot):
            raise TypeError("AnalysisService requires an AnalysisSnapshot")
        self._snapshot = snapshot

    @classmethod
    def from_root(cls, root: str, *, max_source_bytes: int | None = None) -> AnalysisService:
        """Analyze one configured root exactly once."""
        if max_source_bytes is None:
            from arctrellis.parsing.source import DEFAULT_MAX_SOURCE_BYTES

            max_source_bytes = DEFAULT_MAX_SOURCE_BYTES
        return cls(analyze_repository(root, max_source_bytes=max_source_bytes))

    @property
    def snapshot(self) -> AnalysisSnapshot:
        return self._snapshot

    def health(self) -> dict[str, Any]:
        """Readiness only. The analyzed root is never disclosed."""
        return {
            "status": "ok",
            "api_version": API_VERSION,
            "schema_version": None,
            "analysis_available": True,
            "analysis_completeness": self._snapshot.analysis_completeness.value,
            "index_snapshot_id": self._snapshot.snapshot_id,
            "authentication": "none; loopback use only",
        }

    def summary(self) -> dict[str, Any]:
        """Structural statistics and completeness for the configured root."""
        payload = self._snapshot.to_dict()
        return {
            "api_version": API_VERSION,
            "index_snapshot_id": payload["snapshot_id"],
            "analysis_completeness": payload["analysis_completeness"],
            "counts": payload["counts"],
            "graph_context_edge_count": payload["graph_context_edge_count"],
            "context_capped_list_count": payload["context_capped_list_count"],
        }

    def endpoints(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        _reject_unknown(payload, ENDPOINT_FIELDS, "endpoint filters")
        method = _string(payload, "method")
        scope = _string(payload, "scope")
        limit = _integer(payload, "limit")
        body: dict[str, Any] = {
            "intent": "list-endpoints",
            "method": method.strip().upper() if method is not None else None,
            "path": _string(payload, "path"),
            "framework": _string(payload, "framework"),
        }
        if scope is not None:
            body["scope"] = scope
        if limit is not None:
            body["limit"] = limit
        return self._query(_build_request(body, ENDPOINT_FIELDS | {"intent"}, "endpoint filters"))

    def search(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        body = dict(payload)
        body["intent"] = "search-entities"
        return self._query(_build_request(body, SEARCH_FIELDS | {"intent"}, "search request"))

    def query(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._query(_build_request(payload, QUERY_FIELDS, "query request"))

    def _query(self, request: QueryRequest) -> dict[str, Any]:
        bundle = run_query(self._snapshot, request)
        self._refuse_ambiguous_selection(bundle)
        return bundle.to_dict()

    @staticmethod
    def _refuse_ambiguous_selection(bundle: Any) -> None:
        """Refuse to guess, while still returning the evidence the client can use.

        An empty lexical search is a successful result with zero hits and is never
        an error. Only a selection that could not be made honestly becomes a
        failure, and even then the full bundle travels with it so the caller sees
        the candidates and the reason rather than a bare refusal.
        """
        if bundle.status is BundleStatus.SEARCH_RESULTS:
            return
        status = bundle.selection.status
        if status is SelectionStatus.AMBIGUOUS:
            raise AmbiguousSelectionError(bundle.selection.reason, bundle=bundle.to_dict())
        if status is SelectionStatus.NOT_FOUND:
            raise EntityNotFoundError(bundle.selection.reason, bundle=bundle.to_dict())
        if status is SelectionStatus.INVALID:
            raise InvalidSourceError(bundle.selection.reason, bundle=bundle.to_dict())


def route_table() -> Sequence[tuple[str, str, str]]:
    """Declared (method, path, operation) triples for health, summary, endpoints, search, query."""
    return (
        ("GET", f"{API_PREFIX}/health", "health"),
        ("GET", f"{API_PREFIX}/summary", "summary"),
        ("GET", f"{API_PREFIX}/endpoints", "endpoints"),
        ("POST", f"{API_PREFIX}/search", "search"),
        ("POST", f"{API_PREFIX}/query", "query"),
    )
