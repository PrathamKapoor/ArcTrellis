"""Public normalized syntax API; native parser objects stay behind this boundary."""

from .errors import (
    ParserConfigurationError,
    ParserExecutionError,
    ParsingError,
    SourceReadError,
    SourceTooLargeError,
    UnsafeSourceError,
    UnsupportedLanguageError,
)
from .models import DiagnosticKind, ParseDiagnostic, ParsedSource, SyntaxNode, SyntaxSpan
from .parser import parse_discovered_file, parse_source
from .source import DEFAULT_MAX_SOURCE_BYTES

__all__ = [
    "DEFAULT_MAX_SOURCE_BYTES",
    "DiagnosticKind",
    "ParseDiagnostic",
    "ParsedSource",
    "ParserConfigurationError",
    "ParserExecutionError",
    "ParsingError",
    "SourceReadError",
    "SourceTooLargeError",
    "SyntaxNode",
    "SyntaxSpan",
    "UnsafeSourceError",
    "UnsupportedLanguageError",
    "parse_discovered_file",
    "parse_source",
]
