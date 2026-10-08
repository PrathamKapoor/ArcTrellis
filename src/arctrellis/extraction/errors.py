"""Caller-facing failures distinct from conservative partial extraction."""


class ExtractionError(Exception):
    """Base exception for semantic extraction failures."""


class UnsupportedExtractionLanguageError(ExtractionError):
    """The extractor does not support the supplied source language."""


class SourceDecodingError(ExtractionError):
    """Owned source bytes cannot be decoded using the language's encoding policy."""


class SemanticExtractionError(ExtractionError):
    """Normalized input violates an expected semantic boundary or invariant."""
