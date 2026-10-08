"""Typed call-analysis boundary failures."""


class CallAnalysisError(Exception):
    """Base for call-analysis failures."""


class CallExtractionError(CallAnalysisError):
    """Normalized syntax and semantic ownership are incompatible."""


class CallResolutionInvariantError(CallAnalysisError):
    """Repository and import snapshots are incompatible or corrupted."""
