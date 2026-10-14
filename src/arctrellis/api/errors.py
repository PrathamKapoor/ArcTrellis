"""Typed HTTP failures for the local read-only API.

Each failure carries the status code it maps to and a bounded public message. A
client never receives a traceback, an absolute path, a target source location
beyond repository-relative coordinates, or an internal identifier (D-148).
"""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """Base API failure with the HTTP status it maps to."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, bundle: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.bundle = bundle

    def payload(self) -> dict[str, Any]:
        body: dict[str, Any] = {"error": self.code, "message": self.message}
        if self.bundle is not None:
            # The bundle travels with the refusal so a client sees the candidates
            # and the preserved evidence instead of a bare failure.
            body["bundle"] = self.bundle
        return body


class InvalidPayloadError(ApiError):
    """The request body is not a JSON object this interface accepts."""

    status_code = 400
    code = "invalid_payload"


class ValidationFailedError(ApiError):
    """The payload is JSON but does not satisfy the orchestration contract."""

    status_code = 422
    code = "validation_failed"


class AmbiguousSelectionError(ApiError):
    """A selector matched more than one canonical entity and was not guessed."""

    status_code = 409
    code = "ambiguous_selection"


class EntityNotFoundError(ApiError):
    """The selected entity does not exist in the analyzed snapshot."""

    status_code = 404
    code = "entity_not_found"


class InvalidSourceError(ApiError):
    """The selected entity exists but its kind cannot satisfy the intent."""

    status_code = 409
    code = "invalid_source"


class PayloadTooLargeError(ApiError):
    """The request body exceeds the fixed bound."""

    status_code = 413
    code = "payload_too_large"


class UnsupportedMediaTypeError(ApiError):
    """The request Content-Type is not application/json."""

    status_code = 415
    code = "unsupported_media_type"


class MethodNotAllowedError(ApiError):
    """The path exists but not for this HTTP method."""

    status_code = 405
    code = "method_not_allowed"


class NotFoundRouteError(ApiError):
    """No versioned route matches the request path."""

    status_code = 404
    code = "unknown_route"


class UnsupportedOperationError(ApiError):
    """The request names an operation this build does not implement."""

    status_code = 501
    code = "unsupported_operation"


class AnalysisUnavailableError(ApiError):
    """The startup analysis did not complete, so no query can be served."""

    status_code = 503
    code = "analysis_unavailable"
