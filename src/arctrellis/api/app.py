"""HTTP routing over AnalysisService, with no analysis or query logic of its own.

The handler is deliberately thin: it bounds the request, decodes JSON, dispatches
one declared route, and maps a typed ApiError to a status and a bounded body. No
traceback, absolute path, environment value or target source ever reaches a client
(D-148).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .errors import (
    ApiError,
    InvalidPayloadError,
    MethodNotAllowedError,
    NotFoundRouteError,
)
from .service import (
    API_PREFIX,
    MAX_REQUEST_BYTES,
    AnalysisService,
    decode_payload,
    encode_payload,
    route_table,
)

#: Query-string filters the read-only GET routes accept. Anything else is
#: rejected rather than ignored, so a typo cannot silently widen a filter.
ENDPOINT_QUERY_FIELDS = frozenset({"method", "path", "framework", "scope", "limit"})

MAX_LIMIT = 1000


@dataclass(frozen=True, slots=True)
class ApiResponse:
    """One bounded JSON response, ready to write."""

    status: int
    payload: dict[str, Any]
    headers: Mapping[str, str]


def _endpoint_filters(query: str) -> dict[str, Any]:
    parsed = parse_qs(query, keep_blank_values=True, strict_parsing=False)
    filters: dict[str, Any] = {}
    for key in sorted(parsed):
        if key not in ENDPOINT_QUERY_FIELDS:
            raise InvalidPayloadError(f"endpoints does not accept query parameter {key!r}")
        values = parsed[key]
        if len(values) != 1:
            raise InvalidPayloadError(f"{key} must be supplied at most once")
        value = values[0]
        if key == "limit":
            try:
                filters[key] = int(value)
            except ValueError as error:
                raise InvalidPayloadError("limit must be an integer") from error
        else:
            filters[key] = value
    return filters


class ApiApplication:
    """Route dispatch over one service, callable in-process without a socket."""

    def __init__(self, service: AnalysisService) -> None:
        if not isinstance(service, AnalysisService):
            raise TypeError("ApiApplication requires an AnalysisService")
        self._service = service
        self._routes = {(method, path): operation for method, path, operation in route_table()}
        self._paths: dict[str, set[str]] = {}
        for method, path in self._routes:
            self._paths.setdefault(path, set()).add(method)

    @property
    def service(self) -> AnalysisService:
        return self._service

    def handle(
        self,
        method: str,
        target: str,
        body: bytes | None = None,
        content_type: str | None = None,
    ) -> ApiResponse:
        """Dispatch one request and return a bounded response.

        The path and query string are parsed, never resolved on the filesystem, so
        no request can address a repository other than the configured one.
        """
        try:
            return self._dispatch(method, target, body, content_type)
        except ApiError as error:
            return ApiResponse(error.status_code, error.payload(), _HEADERS)

    def _dispatch(
        self,
        method: str,
        target: str,
        body: bytes | None,
        content_type: str | None,
    ) -> ApiResponse:
        split = urlsplit(target)
        path = split.path.rstrip("/") or "/"
        operation = self._routes.get((method.upper(), path))
        if operation is None:
            allowed = self._paths.get(path)
            if allowed is not None:
                raise MethodNotAllowedError(f"{method.upper()} is not allowed for {path}; allowed: {sorted(allowed)}")
            raise NotFoundRouteError(f"no route for {path}; available: {sorted(self._paths)}")
        if operation == "health":
            return ApiResponse(200, self._service.health(), _HEADERS)
        if operation == "summary":
            return ApiResponse(200, self._service.summary(), _HEADERS)
        if operation == "endpoints":
            payload = self._service.endpoints(_endpoint_filters(split.query))
            return ApiResponse(200, payload, _HEADERS)
        decoded = decode_payload(body, content_type)
        if operation == "search":
            return ApiResponse(200, self._service.search(decoded), _HEADERS)
        return ApiResponse(200, self._service.query(decoded), _HEADERS)


_HEADERS: Mapping[str, str] = {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
}


def make_handler(application: ApiApplication) -> type[BaseHTTPRequestHandler]:
    """Build a BaseHTTPRequestHandler bound to one application.

    The handler is created per application rather than per module so the service it
    serves cannot be replaced at runtime from a request.
    """

    class Handler(BaseHTTPRequestHandler):
        server_version = "arctrellis-local"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            self._respond(application.handle("GET", self.path))

        def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            body = self._read_body()
            if body is None:
                self._respond(application.handle("POST", self.path, None, None))
                return
            self._respond(application.handle("POST", self.path, body, self.headers.get("Content-Type")))

        def do_PUT(self) -> None:  # noqa: N802
            self._respond(application.handle("PUT", self.path, None, None))

        def do_DELETE(self) -> None:  # noqa: N802
            self._respond(application.handle("DELETE", self.path, None, None))

        def do_PATCH(self) -> None:  # noqa: N802
            self._respond(application.handle("PATCH", self.path, None, None))

        def do_HEAD(self) -> None:  # noqa: N802
            response = application.handle("GET", self.path)
            self._respond(response, body_only=False)

        def _read_body(self) -> bytes | None:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                return b""
            try:
                length = int(raw_length)
            except ValueError:
                self._respond(
                    ApiResponse(400, {"error": "invalid_payload", "message": "invalid Content-Length"}, _HEADERS)
                )
                return None
            if length < 0 or length > MAX_REQUEST_BYTES:
                # Refuse before reading so an oversized body is never buffered.
                self._respond(
                    ApiResponse(
                        413,
                        {
                            "error": "payload_too_large",
                            "message": f"request body must not exceed {MAX_REQUEST_BYTES} bytes",
                        },
                        _HEADERS,
                    )
                )
                return None
            return self.rfile.read(length) if length else b""

        def _respond(self, response: ApiResponse, body_only: bool = True) -> None:
            encoded = encode_payload(response.payload)
            self.send_response(response.status)
            for key, value in response.headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            if body_only:
                self.wfile.write(encoded)

        def log_message(self, format: str, *args: Any) -> None:
            """Suppress the default stderr request log.

            A read-only local service must not write request lines that could
            contain a caller-supplied selector into another process's output.
            """

    return Handler


API_ROOT = API_PREFIX
