"""Offline CLI failures that map to the documented exit-code policy."""

from __future__ import annotations

from collections.abc import Iterable


class CliError(Exception):
    """Base CLI failure carrying the process exit status it must produce."""

    exit_code = 5

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CliUsageError(CliError, ValueError):
    """The command line itself is wrong: unknown value, missing selector, bad limit."""

    exit_code = 2


class CliExplanation(CliError):
    """A well-formed request the analyzed repository could not resolve or execute."""

    exit_code = 2


class CliAmbiguityError(CliError):
    """A selector matched more than one canonical entity and must not be guessed."""

    exit_code = 3

    def __init__(self, message: str, candidates: Iterable[object] = ()) -> None:
        super().__init__(message)
        self.candidates = tuple(candidates)


class CliAnalysisError(CliError):
    """The requested repository could not be analyzed."""

    exit_code = 4


class CliUnsupportedError(CliError):
    """The request names something this build does not implement."""

    exit_code = 5


EXIT_SUCCESS = 0
EXIT_USAGE = CliUsageError.exit_code
EXIT_AMBIGUOUS = CliAmbiguityError.exit_code
EXIT_ANALYSIS_FAILURE = CliAnalysisError.exit_code
EXIT_UNSUPPORTED = CliUnsupportedError.exit_code
