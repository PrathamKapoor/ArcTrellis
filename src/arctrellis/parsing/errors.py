"""Public failures distinct from recoverable syntax diagnostics."""


class ParsingError(Exception):
    """Base exception for parser infrastructure failures."""


class UnsupportedLanguageError(ParsingError):
    """No grammar matches the supplied canonical language and extension."""


class SourceReadError(ParsingError):
    """Source is unavailable, changed during reading or could not be read."""


class UnsafeSourceError(SourceReadError):
    """An observed source path is linked, indirect or not an ordinary file."""


class SourceTooLargeError(ParsingError):
    """Source exceeds the configured inclusive byte limit."""


class ParserConfigurationError(ParsingError):
    """The installed runtime or grammar could not initialize a parser."""


class ParserExecutionError(ParsingError):
    """The parser failed to return a syntax tree, rather than finding bad syntax."""
