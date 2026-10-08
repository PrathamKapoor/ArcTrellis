"""Conservative FastAPI, Flask and Express static endpoint adapters."""

from .errors import FrameworkAnalysisError, FrameworkExtractionError, FrameworkResolutionInvariantError
from .extraction import extract_framework_observations
from .models import (
    EndpointResolutionStatus,
    Framework,
    FrameworkAnalysisResult,
    FrameworkBinding,
    HttpEndpointResolution,
    HttpRouteObservation,
)
from .resolution import resolve_http_endpoints

__all__ = [
    "Framework",
    "FrameworkBinding",
    "HttpRouteObservation",
    "HttpEndpointResolution",
    "EndpointResolutionStatus",
    "FrameworkAnalysisResult",
    "FrameworkAnalysisError",
    "FrameworkExtractionError",
    "FrameworkResolutionInvariantError",
    "extract_framework_observations",
    "resolve_http_endpoints",
]
