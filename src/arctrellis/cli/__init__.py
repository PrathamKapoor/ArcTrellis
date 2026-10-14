"""Offline command-line interface over the orchestration API.

The CLI is a thin adapter: it validates arguments, calls the existing analysis and
query entry points, and renders their records. It never executes, imports or
installs target repository code.
"""

from __future__ import annotations

from .errors import (
    EXIT_AMBIGUOUS,
    EXIT_ANALYSIS_FAILURE,
    EXIT_SUCCESS,
    EXIT_UNSUPPORTED,
    EXIT_USAGE,
    CliAmbiguityError,
    CliAnalysisError,
    CliError,
    CliExplanation,
    CliUnsupportedError,
    CliUsageError,
)
from .main import INTENT_ALIASES, entry_point, main

__all__ = [
    "EXIT_AMBIGUOUS",
    "EXIT_ANALYSIS_FAILURE",
    "EXIT_SUCCESS",
    "EXIT_UNSUPPORTED",
    "EXIT_USAGE",
    "INTENT_ALIASES",
    "CliAmbiguityError",
    "CliAnalysisError",
    "CliError",
    "CliExplanation",
    "CliUnsupportedError",
    "CliUsageError",
    "entry_point",
    "main",
]
