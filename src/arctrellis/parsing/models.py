"""ArcTrellis-owned immutable syntax, with no parser-library references."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum

from arctrellis.ingestion import DiscoveredFile, Language


def _text(value: str, field: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    if not value or value != value.strip():
        raise ValueError(f"{field} must be nonempty without surrounding whitespace")


@dataclass(frozen=True, slots=True)
class SyntaxSpan:
    """Half-open byte/point range: 1-based lines and 0-based byte columns.

    Columns count bytes since the last newline, not Unicode characters. The end
    is exclusive, including when it is column zero on the following line.
    """

    start_byte: int
    end_byte: int
    start_line: int
    start_column: int
    end_line: int
    end_column: int

    def __post_init__(self) -> None:
        for field in ("start_byte", "end_byte", "start_line", "start_column", "end_line", "end_column"):
            if type(getattr(self, field)) is not int:
                raise TypeError(f"{field} must be an integer, not a boolean")
        if self.start_byte < 0 or self.end_byte < self.start_byte:
            raise ValueError("byte range must satisfy 0 <= start_byte <= end_byte")
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError("line range must satisfy 1 <= start_line <= end_line")
        if self.start_column < 0 or self.end_column < 0:
            raise ValueError("columns must be >= 0")
        if self.start_line == self.end_line and self.end_column < self.start_column:
            raise ValueError("end point must not precede start point")


@dataclass(frozen=True, slots=True, eq=False)
class SyntaxNode:
    """Grammar kind and ordered children, retaining named and recovery nodes."""

    kind: str
    span: SyntaxSpan
    field_name: str | None = None
    children: tuple[SyntaxNode, ...] = ()
    is_error: bool = False
    is_missing: bool = False
    is_named: bool = True

    def __post_init__(self) -> None:
        _text(self.kind, "kind")
        if not isinstance(self.span, SyntaxSpan):
            raise TypeError("span must be SyntaxSpan")
        if self.field_name is not None:
            _text(self.field_name, "field_name")
        if not isinstance(self.children, tuple) or any(not isinstance(c, SyntaxNode) for c in self.children):
            raise TypeError("children must be a tuple of SyntaxNode values")
        for field in ("is_error", "is_missing", "is_named"):
            if type(getattr(self, field)) is not bool:
                raise TypeError(f"{field} must be a boolean")
        previous = self.span.start_byte
        for child in self.children:
            if (
                child.span.start_byte < previous
                or child.span.end_byte > self.span.end_byte
                or (child.span.start_line, child.span.start_column) < (self.span.start_line, self.span.start_column)
                or (child.span.end_line, child.span.end_column) > (self.span.end_line, self.span.end_column)
            ):
                raise ValueError("children must be contained in the parent and in source order")
            previous = child.span.start_byte

    def _signature(self) -> tuple[str, SyntaxSpan, str | None, bool, bool, bool, int]:
        return (
            self.kind,
            self.span,
            self.field_name,
            self.is_error,
            self.is_missing,
            self.is_named,
            len(self.children),
        )

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        pending = [(self, other)]
        while pending:
            left, right = pending.pop()
            if left is right:
                continue
            if left._signature() != right._signature():
                return False
            pending.extend(zip(left.children, right.children, strict=True))
        return True

    def __hash__(self) -> int:
        value = 0
        for node in self.walk():
            value = hash((value, node._signature()))
        return value

    def child_by_field(self, name: str) -> SyntaxNode | None:
        """Return the first direct matching child in grammar order, or None."""
        _text(name, "field name")
        return next((child for child in self.children if child.field_name == name), None)

    def walk(self) -> Iterator[SyntaxNode]:
        """Yield this node and descendants in iterative preorder/grammar order."""
        pending = [self]
        while pending:
            node = pending.pop()
            yield node
            pending.extend(reversed(node.children))


class DiagnosticKind(StrEnum):
    """Recovery information actually reported by the syntax parser."""

    ERROR = "ERROR"
    MISSING = "MISSING"


@dataclass(frozen=True, slots=True)
class ParseDiagnostic:
    """Recovery category, grammar kind and span; no invented compiler message."""

    kind: DiagnosticKind
    node_kind: str
    span: SyntaxSpan

    def __post_init__(self) -> None:
        if not isinstance(self.kind, DiagnosticKind):
            raise TypeError("kind must be DiagnosticKind")
        _text(self.node_kind, "node_kind")
        if not isinstance(self.span, SyntaxSpan):
            raise TypeError("span must be SyntaxSpan")


@dataclass(frozen=True, slots=True)
class ParsedSource:
    """Exact source bytes and normalized syntax, with preorder diagnostics.

    Immutable fields provide deterministic value equality. Source bytes are not
    JSON primitives; consumers must choose an explicit encoding if serializing.
    """

    path: str
    language: Language
    source: bytes
    root: SyntaxNode
    diagnostics: tuple[ParseDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source, bytes):
            raise TypeError("source must be immutable bytes")
        if not isinstance(self.language, Language):
            raise TypeError("language must be a supported Language")
        DiscoveredFile(self.path, len(self.source), self.language)
        if not isinstance(self.root, SyntaxNode):
            raise TypeError("root must be SyntaxNode")
        if not isinstance(self.diagnostics, tuple) or any(not isinstance(d, ParseDiagnostic) for d in self.diagnostics):
            raise TypeError("diagnostics must be a tuple of ParseDiagnostic values")
        if self.root.span.end_byte > len(self.source) or any(
            d.span.end_byte > len(self.source) for d in self.diagnostics
        ):
            raise ValueError("syntax and diagnostic byte spans must fit source bytes")

    @property
    def size_bytes(self) -> int:
        """Length of retained source bytes."""
        return len(self.source)

    @property
    def has_errors(self) -> bool:
        """Whether any ERROR or MISSING diagnostic exists."""
        return bool(self.diagnostics)

    @property
    def diagnostic_count(self) -> int:
        """Number of explicit recovery diagnostics."""
        return len(self.diagnostics)

    def bytes_for(self, node: SyntaxNode) -> bytes:
        """Slice an explicitly supplied bounded node; no decoding or tree-membership claim."""
        if not isinstance(node, SyntaxNode):
            raise TypeError("node must be SyntaxNode")
        if node.span.end_byte > len(self.source):
            raise ValueError("node span exceeds source bytes")
        return self.source[node.span.start_byte : node.span.end_byte]
