"""Encoding-aware interpretation of bytes already owned by parsing."""

from __future__ import annotations

import tokenize
from dataclasses import dataclass
from io import BytesIO, StringIO

from arctrellis.core import SourceLocation
from arctrellis.parsing import ParsedSource, SyntaxNode, SyntaxSpan

from .errors import SemanticExtractionError, SourceDecodingError


def _span_metadata(span: SyntaxSpan) -> tuple[tuple[str, str], ...]:
    names = ("start_byte", "end_byte", "start_line", "start_column", "end_line", "end_column")
    return tuple((name, str(getattr(span, name))) for name in names)


def _location(path: str, span: SyntaxSpan) -> SourceLocation:
    end_line = span.end_line - int(span.end_column == 0 and span.end_byte > span.start_byte)
    return SourceLocation(path, span.start_line, max(span.start_line, end_line))


@dataclass(frozen=True, slots=True)
class _PythonSource:
    parsed: ParsedSource
    encoding: str

    @classmethod
    def from_parsed(cls, parsed: ParsedSource) -> _PythonSource:
        try:
            encoding, _ = tokenize.detect_encoding(BytesIO(parsed.source).readline)
            parsed.source.decode(encoding)
        except (SyntaxError, UnicodeError, LookupError) as error:
            raise SourceDecodingError(f"cannot decode Python source {parsed.path}") from error
        # Strip the BOM only at the file boundary, never from arbitrary fragments.
        return cls(parsed, "utf-8" if encoding == "utf-8-sig" else encoding)

    def text(self, node: SyntaxNode) -> str:
        return self.decode(self.parsed.bytes_for(node))

    def decode(self, source: bytes) -> str:
        try:
            return source.decode(self.encoding)
        except (UnicodeError, LookupError) as error:
            raise SourceDecodingError(f"cannot decode syntax slice in {self.parsed.path}") from error

    def signature(self, definition: SyntaxNode, body: SyntaxNode) -> str:
        header = self.decode(self.parsed.source[definition.span.start_byte : body.span.start_byte])
        depth = 0
        boundary = None
        line_offsets = [0] + [index + 1 for index, character in enumerate(header) if character == "\n"]
        try:
            for token in tokenize.generate_tokens(StringIO(header).readline):
                if token.type != tokenize.OP:
                    continue
                if token.string in ("(", "[", "{"):
                    depth += 1
                elif token.string in (")", "]", "}"):
                    depth -= 1
                elif token.string == ":" and depth == 0:
                    row, column = token.start
                    boundary = line_offsets[row - 1] + column
        except (tokenize.TokenError, IndentationError, SyntaxError) as error:
            raise SemanticExtractionError("cannot locate declaration header boundary") from error
        if boundary is not None:
            return header[:boundary].strip()
        raise SemanticExtractionError("declaration header has no top-level colon")
