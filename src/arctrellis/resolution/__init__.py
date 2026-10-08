"""Static internal-module resolution with explicit uncertainty."""

from .imports import resolve_imports
from .models import ImportResolution, ImportResolutionResult, ImportResolutionStatus

__all__ = ["ImportResolution", "ImportResolutionResult", "ImportResolutionStatus", "resolve_imports"]
