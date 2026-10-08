"""Conservative FastAPI, Flask and Express static endpoint adapters."""

from .composition import join_http_paths
from .composition_extraction import extract_router_observations
from .composition_models import RouterMountObservation, RouterMountResolution, RouterPrefixObservation
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

from .flow import resolve_framework_flow
from .flow_extraction import extract_pre_handler_observations
from .flow_models import FrameworkFlowResult, PreHandlerKind, PreHandlerObservation

__all__ += [
    "FrameworkFlowResult",
    "PreHandlerObservation",
    "PreHandlerKind",
    "extract_pre_handler_observations",
    "resolve_framework_flow",
]


__all__ += [
    "join_http_paths",
    "RouterPrefixObservation",
    "RouterMountObservation",
    "RouterMountResolution",
    "extract_router_observations",
]
