"""Explicit framework analysis boundary failures."""


class FrameworkAnalysisError(Exception):
    """Base static framework analysis failure."""


class FrameworkExtractionError(FrameworkAnalysisError):
    """Normalized syntax and semantic input do not describe the same source."""


class FrameworkResolutionInvariantError(FrameworkAnalysisError):
    """Repository observations or analysis snapshots are inconsistent."""
