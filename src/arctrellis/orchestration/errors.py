"""Typed orchestration failures: caller input, unavailable analysis, broken invariants."""

from __future__ import annotations


class OrchestrationError(Exception):
    """Base structural orchestration failure."""


class InvalidQueryRequestError(OrchestrationError, TypeError):
    """The request is structurally wrong for its intent."""


class InvalidQueryLimitError(OrchestrationError, ValueError):
    """A request budget is not a positive non-boolean integer within its cap."""


class UnsupportedIntentError(OrchestrationError):
    """The intent or selector combination has no execution backend."""


class AnalysisPipelineError(OrchestrationError):
    """The requested repository analysis could not be completed."""


class OrchestrationInvariantError(OrchestrationError):
    """Stored analysis records violate the orchestration contract."""
