"""Immutable per-file entities with explicit lexical ownership."""

from dataclasses import dataclass

from arctrellis.core import CodeEntity, EntityKind, SourceLocation
from arctrellis.ingestion import DiscoveredFile, Language
from arctrellis.parsing import SyntaxSpan


def _entity_span(entity: CodeEntity) -> SyntaxSpan:
    metadata = dict(entity.metadata)
    names = ("start_byte", "end_byte", "start_line", "start_column", "end_line", "end_column")
    try:
        values = tuple(int(metadata[name]) for name in names)
    except (KeyError, ValueError) as error:
        raise ValueError("extracted entities require six integer syntax coordinates") from error
    if any(str(value) != metadata[name] for name, value in zip(names, values)):
        raise ValueError("syntax coordinates must use canonical decimal strings")
    return SyntaxSpan(*values)


def _entity_order(entity: CodeEntity) -> tuple[int, int, str, str]:
    span = _entity_span(entity)
    return span.start_byte, span.end_byte, entity.kind.value, entity.id


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """One module followed by source-ordered declarations, with local parent IDs.

    Remaining order is (start_byte, end_byte, kind, ID). Parents precede their
    children, so cycles and dangling ownership are rejected without recursion.
    The common result accepts supported languages; each extractor sets its own.
    """

    path: str
    language: Language
    entities: tuple[CodeEntity, ...]
    partial: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.language, Language):
            raise TypeError("language must be Language")
        DiscoveredFile(self.path, 0, self.language)
        if type(self.partial) is not bool:
            raise TypeError("partial must be a boolean")
        if not isinstance(self.entities, tuple) or any(not isinstance(e, CodeEntity) for e in self.entities):
            raise TypeError("entities must be a tuple of CodeEntity values")
        modules = tuple(e for e in self.entities if e.kind is EntityKind.MODULE)
        if len(modules) != 1 or self.entities[0] != modules[0] or modules[0].parent_id is not None:
            raise ValueError("exactly one parentless MODULE must be first")
        seen: dict[str, CodeEntity] = {}
        spans: dict[str, SyntaxSpan] = {}
        previous = None
        for index, entity in enumerate(self.entities):
            if entity.id in seen:
                raise ValueError("duplicate entity ID")
            if entity.language != self.language.value or entity.location is None or entity.location.file_path != self.path:
                raise ValueError("entity language and source location must match the result")
            span = _entity_span(entity)
            last_line = max(span.start_line, span.end_line - int(span.end_column == 0 and span.end_byte > span.start_byte))
            if entity.location != SourceLocation(self.path, span.start_line, last_line):
                raise ValueError("entity location must agree with its exact syntax span")
            if index:
                parent = seen.get(entity.parent_id)
                if parent is None or parent.kind not in (EntityKind.MODULE, EntityKind.CLASS, EntityKind.FUNCTION, EntityKind.METHOD):
                    raise ValueError("entity parent must be an earlier semantic scope in this result")
                parent_span = spans[parent.id]
                if span.start_byte < parent_span.start_byte or span.end_byte > parent_span.end_byte:
                    raise ValueError("entity must lie inside its lexical parent")
                key = _entity_order(entity)
                if previous is not None and key < previous:
                    raise ValueError("entities must be in deterministic source order")
                previous = key
            seen[entity.id] = entity
            spans[entity.id] = span

    @property
    def module(self) -> CodeEntity:
        """Return the unique lexical module root."""
        return self.entities[0]

    def entities_of_kind(self, kind: EntityKind) -> tuple[CodeEntity, ...]:
        """Return matching declarations in their original deterministic order."""
        if not isinstance(kind, EntityKind):
            raise TypeError("kind must be EntityKind")
        return tuple(entity for entity in self.entities if entity.kind is kind)
