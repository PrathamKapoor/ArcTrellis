"""Immutable request, plan, selection and evidence contracts.

A request states *what* the caller wants. A plan states *how* ArcTrellis will
obtain it. Neither carries executable callbacks, timestamps or random values,
so equal requests over equal analysis snapshots always produce equal plans and
equal serialized bundles (D-142).

Nothing here interprets natural language. ``search_text`` is retrieval input
only; it never selects an architectural intent.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from arctrellis.core import EntityKind, SourceLocation
from arctrellis.query import AnalysisCompleteness
from arctrellis.retrieval import MAX_ACCEPTED_TOP_K, SearchHit

from .errors import InvalidQueryLimitError, InvalidQueryRequestError, UnsupportedIntentError

SCHEMA_VERSION = 1

CALLABLE_KINDS = frozenset((EntityKind.FUNCTION, EntityKind.METHOD))
DATABASE_OPERATION_KINDS = frozenset(("read", "write", "delete"))
ENDPOINT_SCOPES = ("local", "declared", "effective", "application")
DATABASE_KINDS = frozenset(DATABASE_OPERATION_KINDS)

MAX_REQUEST_SEARCH_LENGTH = 512
MAX_REQUEST_IDENTIFIER_LENGTH = 1024

#: Request defaults. They are named constants because an unsupported option is
#: detected by comparing a supplied value against the default it would have to
#: differ from to be meaningful (D-142).
DEFAULT_TOP_K = 25
DEFAULT_MAX_DEPTH = 12
DEFAULT_MAX_PATHS = 25
DEFAULT_MAX_EXPANSIONS = 10000
DEFAULT_POSTING_BUDGET = 50000


class QueryIntent(StrEnum):
    """Bounded structured intents backed by existing structural-query functions."""

    SEARCH_ENTITIES = "SEARCH_ENTITIES"
    LIST_ENDPOINTS = "LIST_ENDPOINTS"
    TRACE_ENDPOINT_TO_DATABASE = "TRACE_ENDPOINT_TO_DATABASE"
    TRACE_CALLABLE_TO_DATABASE = "TRACE_CALLABLE_TO_DATABASE"
    DIRECT_DATABASE_OPERATIONS = "DIRECT_DATABASE_OPERATIONS"
    LIST_DATABASE_CALLERS = "LIST_DATABASE_CALLERS"
    FIND_DIRECT_TESTS = "FIND_DIRECT_TESTS"
    FIND_CALLERS = "FIND_CALLERS"
    FIND_AFFECTED_ENDPOINTS = "FIND_AFFECTED_ENDPOINTS"


class SelectorForm(StrEnum):
    """Explicit, mutually exclusive ways to name a canonical source entity.

    ``ENDPOINT_METHOD_PATH`` selects one endpoint registration; the same HTTP
    pair on an inventory intent is a list filter, reported as
    ``ENDPOINT_FILTER`` so the two meanings never blur.
    """

    ENTITY_ID = "ENTITY_ID"
    QUALIFIED_NAME = "QUALIFIED_NAME"
    ENDPOINT_METHOD_PATH = "ENDPOINT_METHOD_PATH"
    ENDPOINT_FILTER = "ENDPOINT_FILTER"
    SEARCH_TEXT = "SEARCH_TEXT"
    NONE = "NONE"


class PlanStep(StrEnum):
    """Small fixed vocabulary of planned operations."""

    SEARCH_CANDIDATES = "SEARCH_CANDIDATES"
    SELECT_CANONICAL_ENTITY = "SELECT_CANONICAL_ENTITY"
    EXECUTE_STRUCTURAL_QUERY = "EXECUTE_STRUCTURAL_QUERY"
    ASSEMBLE_EVIDENCE = "ASSEMBLE_EVIDENCE"


class SelectionStatus(StrEnum):
    """Explicit canonical-selection outcomes; never an implicit guess.

    ``CANDIDATES`` means a lexical query produced ranked candidates and
    deliberately selected nothing: a high relevance score is not entity identity.
    ``NOT_REQUIRED`` means the intent is graph-wide and names no source entity.
    """

    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"
    INVALID = "INVALID"
    CANDIDATES = "CANDIDATES"
    NOT_REQUIRED = "NOT_REQUIRED"


class SelectionBasis(StrEnum):
    """Why a candidate was produced."""

    EXACT_ENTITY_ID = "EXACT_ENTITY_ID"
    EXACT_QUALIFIED_NAME = "EXACT_QUALIFIED_NAME"
    EXACT_ENDPOINT_METHOD_PATH = "EXACT_ENDPOINT_METHOD_PATH"
    LEXICAL_CANDIDATES = "LEXICAL_CANDIDATES"


class BundleStatus(StrEnum):
    """What the evidence bundle actually establishes."""

    SEARCH_RESULTS = "SEARCH_RESULTS"
    EVIDENCE_PATHS = "EVIDENCE_PATHS"
    INVENTORY = "INVENTORY"
    NO_KNOWN_PATH = "NO_KNOWN_PATH"
    AMBIGUOUS_SOURCE = "AMBIGUOUS_SOURCE"
    NOT_FOUND_SOURCE = "NOT_FOUND_SOURCE"
    INVALID_SOURCE = "INVALID_SOURCE"


@dataclass(frozen=True, slots=True)
class IntentSpec:
    """Which request fields an intent actually consumes.

    Every field not required by an intent must keep its default value. Rejecting
    an unsupported field is deliberate: silently ignoring it would hide a caller
    mistake such as passing a graph-context option to a structural query.
    """

    intent: QueryIntent
    source_kinds: frozenset[EntityKind]
    selector_forms: frozenset[SelectorForm]
    structural_query: str | None
    uses_search_text: bool = False
    uses_endpoint_filters: bool = False
    uses_graph_context: bool = False
    uses_operation_filter: bool = False
    uses_transitive: bool = False
    uses_search_limits: bool = False
    uses_path_limits: bool = False
    #: Whether the intent passes framework, scope and path filters into retrieval.
    uses_retrieval_filters: bool = False


_SPECS: Mapping[QueryIntent, IntentSpec] = MappingProxyType(
    {
        QueryIntent.SEARCH_ENTITIES: IntentSpec(
            QueryIntent.SEARCH_ENTITIES,
            frozenset(),
            frozenset((SelectorForm.SEARCH_TEXT,)),
            None,
            uses_search_text=True,
            uses_graph_context=True,
            uses_operation_filter=True,
            uses_search_limits=True,
            uses_retrieval_filters=True,
        ),
        QueryIntent.LIST_ENDPOINTS: IntentSpec(
            QueryIntent.LIST_ENDPOINTS,
            frozenset(),
            frozenset((SelectorForm.NONE, SelectorForm.ENDPOINT_FILTER)),
            "list_endpoints",
            uses_endpoint_filters=True,
            uses_path_limits=True,
        ),
        QueryIntent.LIST_DATABASE_CALLERS: IntentSpec(
            QueryIntent.LIST_DATABASE_CALLERS,
            frozenset(),
            frozenset((SelectorForm.NONE,)),
            "list_direct_database_callers",
            uses_operation_filter=True,
            uses_path_limits=True,
        ),
        QueryIntent.TRACE_ENDPOINT_TO_DATABASE: IntentSpec(
            QueryIntent.TRACE_ENDPOINT_TO_DATABASE,
            frozenset((EntityKind.API_ENDPOINT,)),
            frozenset(
                (
                    SelectorForm.ENTITY_ID,
                    SelectorForm.QUALIFIED_NAME,
                    SelectorForm.ENDPOINT_METHOD_PATH,
                )
            ),
            "trace_endpoint_to_database",
            uses_operation_filter=True,
            uses_path_limits=True,
        ),
        QueryIntent.TRACE_CALLABLE_TO_DATABASE: IntentSpec(
            QueryIntent.TRACE_CALLABLE_TO_DATABASE,
            CALLABLE_KINDS,
            frozenset((SelectorForm.ENTITY_ID, SelectorForm.QUALIFIED_NAME)),
            "trace_callable_to_database",
            uses_operation_filter=True,
            uses_path_limits=True,
        ),
        QueryIntent.DIRECT_DATABASE_OPERATIONS: IntentSpec(
            QueryIntent.DIRECT_DATABASE_OPERATIONS,
            CALLABLE_KINDS | frozenset((EntityKind.MODULE,)),
            frozenset((SelectorForm.ENTITY_ID, SelectorForm.QUALIFIED_NAME)),
            "get_direct_database_operations",
            uses_operation_filter=True,
            uses_path_limits=True,
        ),
        QueryIntent.FIND_DIRECT_TESTS: IntentSpec(
            QueryIntent.FIND_DIRECT_TESTS,
            CALLABLE_KINDS,
            frozenset((SelectorForm.ENTITY_ID, SelectorForm.QUALIFIED_NAME)),
            "find_direct_tests_for_symbol",
            uses_path_limits=True,
        ),
        QueryIntent.FIND_CALLERS: IntentSpec(
            QueryIntent.FIND_CALLERS,
            CALLABLE_KINDS,
            frozenset((SelectorForm.ENTITY_ID, SelectorForm.QUALIFIED_NAME)),
            "find_callers",
            uses_transitive=True,
            uses_path_limits=True,
        ),
        QueryIntent.FIND_AFFECTED_ENDPOINTS: IntentSpec(
            QueryIntent.FIND_AFFECTED_ENDPOINTS,
            CALLABLE_KINDS,
            frozenset((SelectorForm.ENTITY_ID, SelectorForm.QUALIFIED_NAME)),
            "find_potentially_affected_endpoints",
            uses_path_limits=True,
        ),
    }
)

HTTP_METHODS = frozenset(("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"))


def intent_spec(intent: QueryIntent) -> IntentSpec:
    """Return the immutable specification backing one supported intent."""
    if not isinstance(intent, QueryIntent):
        raise InvalidQueryRequestError("intent must be a QueryIntent")
    return _SPECS[intent]


def _optional_text(value: str | None, name: str, maximum: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidQueryRequestError(f"{name} must be a string or None")
    if not value or value != value.strip():
        raise InvalidQueryRequestError(f"{name} must be nonempty without surrounding whitespace")
    if len(value) > maximum:
        raise InvalidQueryRequestError(f"{name} must not exceed {maximum} characters")
    if any(ord(character) < 32 for character in value):
        raise InvalidQueryRequestError(f"{name} must not contain control characters")
    return value


def _limit(name: str, value: int, maximum: int | None = None) -> int:
    if type(value) is not int:
        raise InvalidQueryLimitError(f"{name} must be a positive integer, not {type(value).__name__}")
    if value <= 0:
        raise InvalidQueryLimitError(f"{name} must be a positive integer")
    if maximum is not None and value > maximum:
        raise InvalidQueryLimitError(f"{name} must not exceed {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class QueryRequest:
    """One validated structural query request.

    Selector forms are mutually exclusive: exactly one of entity_id,
    qualified_name, http_method+route_path or search_text may be present, and
    only forms the intent supports are accepted. ``entity_kind``, ``language``
    and ``path_prefix`` are constraints on the selected entity when an intent
    selects one, and retrieval filters when an intent searches.
    """

    intent: QueryIntent
    entity_id: str | None = None
    qualified_name: str | None = None
    http_method: str | None = None
    route_path: str | None = None
    search_text: str | None = None
    entity_kind: EntityKind | None = None
    language: str | None = None
    path_prefix: str | None = None
    framework: str | None = None
    endpoint_scope: str | None = None
    operation_kinds: frozenset[str] = DATABASE_KINDS
    include_graph_context: bool = False
    transitive_callers: bool = False
    top_k: int = DEFAULT_TOP_K
    max_depth: int = DEFAULT_MAX_DEPTH
    max_paths: int = DEFAULT_MAX_PATHS
    max_expansions: int = DEFAULT_MAX_EXPANSIONS
    max_examined_postings: int = DEFAULT_POSTING_BUDGET

    def __post_init__(self) -> None:
        if not isinstance(self.intent, QueryIntent):
            raise InvalidQueryRequestError("intent must be a QueryIntent")
        spec = intent_spec(self.intent)
        _optional_text(self.entity_id, "entity_id", MAX_REQUEST_IDENTIFIER_LENGTH)
        _optional_text(self.qualified_name, "qualified_name", MAX_REQUEST_IDENTIFIER_LENGTH)
        _optional_text(self.route_path, "route_path", MAX_REQUEST_IDENTIFIER_LENGTH)
        _optional_text(self.search_text, "search_text", MAX_REQUEST_SEARCH_LENGTH)
        _optional_text(self.language, "language", 64)
        _optional_text(self.path_prefix, "path_prefix", MAX_REQUEST_IDENTIFIER_LENGTH)
        _optional_text(self.framework, "framework", 64)
        if self.entity_kind is not None and not isinstance(self.entity_kind, EntityKind):
            raise InvalidQueryRequestError("entity_kind must be EntityKind or None")
        if self.http_method is not None:
            if not isinstance(self.http_method, str):
                raise InvalidQueryRequestError("http_method must be a string or None")
            if self.http_method != self.http_method.strip().upper():
                raise InvalidQueryRequestError("http_method must be uppercase without padding")
            if self.http_method not in HTTP_METHODS:
                raise InvalidQueryRequestError(f"http_method must be one of {sorted(HTTP_METHODS)}")
        if self.endpoint_scope is not None and self.endpoint_scope not in ENDPOINT_SCOPES:
            raise InvalidQueryRequestError(f"endpoint_scope must be one of {ENDPOINT_SCOPES}")
        if type(self.include_graph_context) is not bool:
            raise InvalidQueryRequestError("include_graph_context must be a boolean")
        if type(self.transitive_callers) is not bool:
            raise InvalidQueryRequestError("transitive_callers must be a boolean")
        if not isinstance(self.operation_kinds, frozenset) or any(
            not isinstance(item, str) for item in self.operation_kinds
        ):
            raise InvalidQueryRequestError("operation_kinds must be a frozenset of strings")
        if not self.operation_kinds or not self.operation_kinds <= DATABASE_KINDS:
            raise InvalidQueryRequestError(f"operation_kinds must be a nonempty subset of {sorted(DATABASE_KINDS)}")
        _limit("top_k", self.top_k, MAX_ACCEPTED_TOP_K)
        _limit("max_depth", self.max_depth)
        _limit("max_paths", self.max_paths)
        _limit("max_expansions", self.max_expansions)
        _limit("max_examined_postings", self.max_examined_postings)
        if SelectorForm.ENDPOINT_METHOD_PATH in spec.selector_forms and (self.http_method is None) != (
            self.route_path is None
        ):
            raise InvalidQueryRequestError("http_method and route_path must be supplied together")
        selector_forms = self.selector_forms()
        unsupported = selector_forms - spec.selector_forms
        if unsupported:
            raise UnsupportedIntentError(
                f"{self.intent.value} does not support selector(s) {sorted(form.value for form in unsupported)}"
            )
        if SelectorForm.NONE not in spec.selector_forms and not selector_forms:
            raise InvalidQueryRequestError(f"{self.intent.value} requires an explicit entity selector")
        self._reject_unsupported(spec)

    def _reject_unsupported(self, spec: IntentSpec) -> None:
        """Reject non-default fields the intent cannot consume.

        Silently ignoring an option would hide a caller mistake, such as asking
        a structural query for graph-context ranking it never applies. Budget
        fields belong to exactly one family: retrieval budgets (``top_k`` and
        ``max_examined_postings``) or traversal budgets (``max_paths``,
        ``max_depth`` and ``max_expansions``). ``framework`` and
        ``endpoint_scope`` are list filters for an inventory and constraints on
        the selected entity for every intent that selects one.
        """
        retrieval = spec.uses_search_limits
        endpoint_facts = spec.uses_endpoint_filters or spec.uses_retrieval_filters or bool(spec.source_kinds)
        checks: tuple[tuple[str, bool, bool], ...] = (
            ("search_text", spec.uses_search_text, self.search_text is not None),
            ("framework", endpoint_facts, self.framework is not None),
            ("endpoint_scope", endpoint_facts, self.endpoint_scope is not None),
            ("include_graph_context", spec.uses_graph_context, self.include_graph_context),
            ("operation_kinds", spec.uses_operation_filter, self.operation_kinds != DATABASE_KINDS),
            ("transitive_callers", spec.uses_transitive, self.transitive_callers),
            (
                "max_examined_postings",
                retrieval,
                self.max_examined_postings != DEFAULT_POSTING_BUDGET,
            ),
            ("top_k", retrieval, self.top_k != DEFAULT_TOP_K),
            ("max_paths", spec.uses_path_limits, self.max_paths != DEFAULT_MAX_PATHS),
            ("max_depth", spec.uses_path_limits, self.max_depth != DEFAULT_MAX_DEPTH),
            ("max_expansions", spec.uses_path_limits, self.max_expansions != DEFAULT_MAX_EXPANSIONS),
        )
        for name, allowed, supplied in checks:
            if supplied and not allowed:
                raise UnsupportedIntentError(f"{self.intent.value} does not support the {name} option")

    def selector_forms(self) -> frozenset[SelectorForm]:
        """Which explicit selector forms this request actually supplies.

        The HTTP method and route are read as a pair. Whether that pair selects
        one endpoint or filters an inventory is decided by the intent's own
        specification, never by the field names alone.
        """
        forms: set[SelectorForm] = set()
        if self.entity_id is not None:
            forms.add(SelectorForm.ENTITY_ID)
        if self.qualified_name is not None:
            forms.add(SelectorForm.QUALIFIED_NAME)
        if self.search_text is not None:
            forms.add(SelectorForm.SEARCH_TEXT)
        if self.http_method is not None and self.route_path is not None:
            spec = intent_spec(self.intent)
            forms.add(
                SelectorForm.ENDPOINT_METHOD_PATH
                if SelectorForm.ENDPOINT_METHOD_PATH in spec.selector_forms
                else SelectorForm.ENDPOINT_FILTER
            )
        if len(forms) > 1:
            raise InvalidQueryRequestError(
                f"exactly one selector form is allowed, received {sorted(form.value for form in forms)}"
            )
        return frozenset(forms)

    @property
    def selector_form(self) -> SelectorForm:
        forms = self.selector_forms()
        return next(iter(forms)) if forms else SelectorForm.NONE

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.value,
            "selector_form": self.selector_form.value,
            "entity_id": self.entity_id,
            "qualified_name": self.qualified_name,
            "http_method": self.http_method,
            "route_path": self.route_path,
            "search_text": self.search_text,
            "entity_kind": self.entity_kind.value if self.entity_kind else None,
            "language": self.language,
            "path_prefix": self.path_prefix,
            "framework": self.framework,
            "endpoint_scope": self.endpoint_scope,
            "operation_kinds": sorted(self.operation_kinds),
            "include_graph_context": self.include_graph_context,
            "transitive_callers": self.transitive_callers,
            "top_k": self.top_k,
            "max_depth": self.max_depth,
            "max_paths": self.max_paths,
            "max_expansions": self.max_expansions,
            "max_examined_postings": self.max_examined_postings,
        }


@dataclass(frozen=True, slots=True)
class QueryPlan:
    """Intended operations for one request; never a result and never executable.

    Steps are a small fixed vocabulary. ``structural_query`` names the existing
    public query function that will run; the orchestrator holds no reference to
    it, so a serialized plan stays inert data.
    """

    request: QueryRequest
    steps: tuple[PlanStep, ...]
    source_kinds: frozenset[EntityKind]
    structural_query: str | None
    planned_output: str

    def __post_init__(self) -> None:
        if not isinstance(self.request, QueryRequest):
            raise InvalidQueryRequestError("plan requires a validated QueryRequest")
        if not isinstance(self.steps, tuple) or not self.steps:
            raise InvalidQueryRequestError("plan requires a nonempty step tuple")
        if any(not isinstance(step, PlanStep) for step in self.steps):
            raise InvalidQueryRequestError("plan steps must be PlanStep values")
        if PlanStep.ASSEMBLE_EVIDENCE not in self.steps:
            raise InvalidQueryRequestError("every plan must assemble evidence")
        if not isinstance(self.source_kinds, frozenset) or any(
            not isinstance(kind, EntityKind) for kind in self.source_kinds
        ):
            raise InvalidQueryRequestError("source_kinds must be a frozenset of EntityKind")
        if not isinstance(self.planned_output, str) or not self.planned_output:
            raise InvalidQueryRequestError("planned_output must be a nonempty string")

    @property
    def requires_selection(self) -> bool:
        return PlanStep.SELECT_CANONICAL_ENTITY in self.steps

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.request.intent.value,
            "steps": [step.value for step in self.steps],
            "selector_form": self.request.selector_form.value,
            "required_source_kinds": sorted(kind.value for kind in self.source_kinds),
            "structural_query": self.structural_query,
            "planned_output": self.planned_output,
            "limits": {
                "top_k": self.request.top_k,
                "max_depth": self.request.max_depth,
                "max_paths": self.request.max_paths,
                "max_expansions": self.request.max_expansions,
                "max_examined_postings": self.request.max_examined_postings,
            },
        }


@dataclass(frozen=True, slots=True)
class EntityCandidate:
    """One canonical entity a selector could refer to.

    ``relevance_score`` is a lexical relevance value and is present only for
    lexical candidates; it is never a probability and never a selection decision.
    """

    entity_id: str
    name: str
    qualified_name: str
    entity_kind: EntityKind
    language: str | None
    repository_relative_path: str | None
    source_location: SourceLocation | None
    basis: SelectionBasis
    relevance_score: float | None = None
    matched_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.entity_id or not self.name or not self.qualified_name:
            raise InvalidQueryRequestError("candidates require canonical identity fields")
        if not isinstance(self.entity_kind, EntityKind):
            raise InvalidQueryRequestError("entity_kind must be EntityKind")
        if not isinstance(self.basis, SelectionBasis):
            raise InvalidQueryRequestError("basis must be SelectionBasis")
        if self.source_location is not None and not isinstance(self.source_location, SourceLocation):
            raise InvalidQueryRequestError("source_location must be SourceLocation or None")

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "qualified_name": self.qualified_name,
            "entity_kind": self.entity_kind.value,
            "language": self.language,
            "repository_relative_path": self.repository_relative_path,
            "source_location": None
            if self.source_location is None
            else {
                "file_path": self.source_location.file_path,
                "start_line": self.source_location.start_line,
                "end_line": self.source_location.end_line,
            },
            "basis": self.basis.value,
            "relevance_score": self.relevance_score,
            "matched_fields": list(self.matched_fields),
        }


@dataclass(frozen=True, slots=True)
class SelectionResult:
    """Explicit selection outcome; a bundle never claims an unproven identity."""

    status: SelectionStatus
    selector_form: SelectorForm
    selector_text: str
    selected_entity_id: str | None
    candidates: tuple[EntityCandidate, ...]
    truncated: bool
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, SelectionStatus):
            raise InvalidQueryRequestError("status must be SelectionStatus")
        if not isinstance(self.selector_form, SelectorForm):
            raise InvalidQueryRequestError("selector_form must be SelectorForm")
        if not isinstance(self.candidates, tuple):
            raise InvalidQueryRequestError("candidates must be a tuple")
        if type(self.truncated) is not bool:
            raise InvalidQueryRequestError("truncated must be a boolean")
        if not isinstance(self.reason, str) or not self.reason:
            raise InvalidQueryRequestError("reason must be a nonempty string")
        if self.status is SelectionStatus.RESOLVED and self.selected_entity_id is None:
            raise InvalidQueryRequestError("RESOLVED selection must name a canonical entity ID")
        if self.status is not SelectionStatus.RESOLVED and self.selected_entity_id is not None:
            raise InvalidQueryRequestError("only RESOLVED selections may name an entity")
        if self.status is SelectionStatus.RESOLVED and self.candidates:
            raise InvalidQueryRequestError("a resolved selection returns the single selected candidate only")
        if self.status is SelectionStatus.AMBIGUOUS and len(self.candidates) < 2:
            raise InvalidQueryRequestError("an ambiguous selection requires at least two candidates")
        if self.status is SelectionStatus.RESOLVED and self.truncated:
            raise InvalidQueryRequestError("a resolved selection cannot claim truncation")
        if self.status is SelectionStatus.CANDIDATES and not self.candidates:
            raise InvalidQueryRequestError("CANDIDATES requires at least one ranked candidate")

    @property
    def resolved(self) -> bool:
        return self.status is SelectionStatus.RESOLVED

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "selector_form": self.selector_form.value,
            "selector_text": self.selector_text,
            "selected_entity_id": self.selected_entity_id,
            "candidate_count": len(self.candidates),
            "truncated": self.truncated,
            "reason": self.reason,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


@dataclass(frozen=True, slots=True)
class EntitySummary:
    """Canonical identity of a bundle entity, without any source text."""

    entity_id: str
    entity_kind: EntityKind
    name: str
    qualified_name: str
    language: str | None
    repository_relative_path: str | None
    source_location: SourceLocation | None
    canonical_facts: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.entity_kind, EntityKind):
            raise InvalidQueryRequestError("entity_kind must be EntityKind")
        if not isinstance(self.canonical_facts, tuple):
            raise InvalidQueryRequestError("canonical_facts must be a tuple of key/value pairs")

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_kind": self.entity_kind.value,
            "name": self.name,
            "qualified_name": self.qualified_name,
            "language": self.language,
            "repository_relative_path": self.repository_relative_path,
            "source_location": None
            if self.source_location is None
            else {
                "file_path": self.source_location.file_path,
                "start_line": self.source_location.start_line,
                "end_line": self.source_location.end_line,
            },
            "canonical_facts": dict(self.canonical_facts),
        }


@dataclass(frozen=True, slots=True)
class EvidenceDetail:
    """One original Evidence record; locations and methods only, never content."""

    evidence_id: str
    analysis_method: str
    file_path: str
    start_line: int
    end_line: int
    metadata: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "analysis_method": self.analysis_method,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class RelationshipEvidence:
    """One stored relationship with its original confidence and Evidence."""

    relationship_id: str
    relationship_kind: str
    source_entity_id: str
    target_entity_id: str
    confidence: str
    confidence_score: float | None
    evidence: tuple[EvidenceDetail, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "relationship_id": self.relationship_id,
            "relationship_kind": self.relationship_kind,
            "source_entity_id": self.source_entity_id,
            "target_entity_id": self.target_entity_id,
            "confidence": self.confidence,
            "confidence_score": self.confidence_score,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True, slots=True)
class PathEvidence:
    """One evidence-backed structural path in stored forward edge order."""

    path_id: str
    entities: tuple[EntitySummary, ...]
    relationships: tuple[RelationshipEvidence, ...]
    direction: str
    weakest_edge_score: float | None
    confidence_classification: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.entities, tuple) or not isinstance(self.relationships, tuple):
            raise InvalidQueryRequestError("path evidence requires immutable tuples")
        if len(self.entities) != len(self.relationships) + 1:
            raise InvalidQueryRequestError("a path has exactly one more entity than relationship")
        for index, relationship in enumerate(self.relationships):
            if (
                relationship.source_entity_id != self.entities[index].entity_id
                or relationship.target_entity_id != self.entities[index + 1].entity_id
            ):
                raise InvalidQueryRequestError("path relationships must follow stored forward continuity")

    @property
    def hop_count(self) -> int:
        return len(self.relationships)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path_id": self.path_id,
            "hop_count": self.hop_count,
            "direction": self.direction,
            "weakest_edge_score": self.weakest_edge_score,
            "confidence_classification": self.confidence_classification,
            "entities": [entity.to_dict() for entity in self.entities],
            "relationships": [relationship.to_dict() for relationship in self.relationships],
        }


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """Stable, JSON-compatible result of one structured orchestration request.

    The bundle distinguishes a known structural path, a lexically ranked search,
    no known path, ambiguous selection and incomplete analysis. It never contains
    source bytes, declaration signatures, absolute paths, credentials or
    tracebacks, and it never multiplies confidence scores into a probability.
    """

    schema_version: int
    status: BundleStatus
    request: dict[str, Any]
    plan: dict[str, Any]
    selection: SelectionResult
    selected_entity: EntitySummary | None
    candidate_entities: tuple[EntityCandidate, ...]
    search_hits: tuple[SearchHit, ...]
    paths: tuple[PathEvidence, ...]
    analysis_completeness: AnalysisCompleteness
    retrieval_truncation: tuple[str, ...]
    graph_truncation: tuple[str, ...]
    limitations: tuple[str, ...]
    index_snapshot_id: str
    _lookup: Mapping[str, EntitySummary] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise InvalidQueryRequestError(f"schema_version must be {SCHEMA_VERSION}")
        if not isinstance(self.status, BundleStatus):
            raise InvalidQueryRequestError("status must be BundleStatus")
        if not isinstance(self.selection, SelectionResult):
            raise InvalidQueryRequestError("selection must be a SelectionResult")
        if not isinstance(self.analysis_completeness, AnalysisCompleteness):
            raise InvalidQueryRequestError("analysis_completeness must be AnalysisCompleteness")
        for name in ("candidate_entities", "search_hits", "paths"):
            if not isinstance(getattr(self, name), tuple):
                raise InvalidQueryRequestError(f"{name} must be a tuple")
        for name in ("retrieval_truncation", "graph_truncation", "limitations"):
            value = getattr(self, name)
            if not isinstance(value, tuple) or value != tuple(sorted(set(value))):
                raise InvalidQueryRequestError(f"{name} must be a sorted unique tuple")
        if self.status is BundleStatus.EVIDENCE_PATHS and not self.paths:
            raise InvalidQueryRequestError("EVIDENCE_PATHS requires at least one path")
        if self.status is BundleStatus.INVENTORY and (self.paths or not self.candidate_entities):
            raise InvalidQueryRequestError("INVENTORY requires candidates and no evidence path")
        if self.status is BundleStatus.NO_KNOWN_PATH and self.paths:
            raise InvalidQueryRequestError("NO_KNOWN_PATH cannot carry paths")
        if self.status is BundleStatus.AMBIGUOUS_SOURCE and self.selected_entity is not None:
            raise InvalidQueryRequestError("AMBIGUOUS_SOURCE cannot select an entity")
        identifiers = tuple(path.path_id for path in self.paths)
        if len(set(identifiers)) != len(identifiers):
            raise InvalidQueryRequestError("path IDs must be unique within a bundle")
        if not isinstance(self.index_snapshot_id, str) or not self.index_snapshot_id:
            raise InvalidQueryRequestError("index_snapshot_id must be a nonempty string")
        object.__setattr__(self, "_lookup", MappingProxyType({item.entity_id: item for item in self.path_entities()}))

    @property
    def found_paths(self) -> bool:
        return bool(self.paths)

    @property
    def truncated(self) -> bool:
        return bool(self.retrieval_truncation) or bool(self.graph_truncation)

    def path_entities(self) -> tuple[EntitySummary, ...]:
        seen: dict[str, EntitySummary] = {}
        for path in self.paths:
            for entity in path.entities:
                seen.setdefault(entity.entity_id, entity)
        return tuple(seen[identifier] for identifier in sorted(seen))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status.value,
            "request": self.request,
            "plan": self.plan,
            "selection": self.selection.to_dict(),
            "selected_entity": None if self.selected_entity is None else self.selected_entity.to_dict(),
            "candidate_entities": [item.to_dict() for item in self.candidate_entities],
            "search_hits": [hit.to_dict() for hit in self.search_hits],
            "paths": [path.to_dict() for path in self.paths],
            "path_count": len(self.paths),
            "relationship_count": sum(path.hop_count for path in self.paths),
            "analysis_completeness": self.analysis_completeness.value,
            "retrieval_truncation": list(self.retrieval_truncation),
            "graph_truncation": list(self.graph_truncation),
            "truncated": self.truncated,
            "limitations": list(self.limitations),
            "index_snapshot_id": self.index_snapshot_id,
        }
