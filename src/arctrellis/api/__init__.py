"""Loopback-only read-only HTTP interface over the existing analysis snapshot.

This package adds no analysis, no query logic and no runtime dependency. It parses
a bounded JSON payload into the same validated QueryRequest the CLI builds, calls
the same run_query, and returns the bundle's own serialization. The analyzed root
is fixed at startup and is unreachable from any request (D-148).

Because there is no authentication, this service must never be exposed beyond
loopback.
"""

from __future__ import annotations

from .app import ApiApplication, ApiResponse, make_handler
from .errors import (
    AmbiguousSelectionError,
    AnalysisUnavailableError,
    ApiError,
    EntityNotFoundError,
    InvalidPayloadError,
    InvalidSourceError,
    MethodNotAllowedError,
    NotFoundRouteError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
    UnsupportedOperationError,
    ValidationFailedError,
)
from .server import (
    ALLOWED_HOSTS,
    DEFAULT_HOST,
    DEFAULT_PORT,
    UnsafeBindError,
    create_server,
    is_loopback,
    server_banner,
)
from .service import (
    API_PREFIX,
    API_VERSION,
    INTENT_NAMES,
    MAX_REQUEST_BYTES,
    AnalysisService,
    decode_payload,
    encode_payload,
    route_table,
)

__all__ = [
    "ALLOWED_HOSTS",
    "API_PREFIX",
    "API_VERSION",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "INTENT_NAMES",
    "MAX_REQUEST_BYTES",
    "AmbiguousSelectionError",
    "AnalysisService",
    "AnalysisUnavailableError",
    "ApiApplication",
    "ApiError",
    "ApiResponse",
    "EntityNotFoundError",
    "InvalidPayloadError",
    "InvalidSourceError",
    "MethodNotAllowedError",
    "NotFoundRouteError",
    "PayloadTooLargeError",
    "UnsafeBindError",
    "UnsupportedMediaTypeError",
    "UnsupportedOperationError",
    "ValidationFailedError",
    "create_server",
    "decode_payload",
    "encode_payload",
    "is_loopback",
    "make_handler",
    "route_table",
    "server_banner",
]
