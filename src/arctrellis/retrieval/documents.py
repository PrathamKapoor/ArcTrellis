"""Immutable canonical search documents projected from existing CodeEntity records.

A document is a *value projection* of exactly one CodeEntity identified by its
canonical ``CodeEntity.id``. It stores bounded, allowlisted structural metadata
only. It never stores source bytes, syntax trees, signatures, parser objects,
environment values, credentials, tracebacks or arbitrary metadata (D-128).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from arctrellis.core import CodeEntity, EntityKind, SourceLocation

from .errors import RetrievalInvariantError
from .normalization import MAX_FIELD_TOKENS, MAX_FIELD_VALUE_LENGTH, canonical_text, tokenize_value

FIELD_ENTITY_KIND = "entity_kind"
FIELD_LANGUAGE = "language"
FIELD_NAME = "name"
FIELD_PATH = "repository_relative_path"
FIELD_QUALIFIED_NAME = "qualified_name"

#: Explicit allowlist of existing canonical metadata keys that become searchable
#: fields. Verified against the actual producers in frameworks/, database/,
#: extraction/ and indexing/. Every other metadata key (byte offsets, statement
#: witnesses, decorator spellings, observation IDs, ...) is excluded by omission.
SEARCHABLE_METADATA_KEYS: tuple[str, ...] = (
    "alias",
    "binding",
    "composition_scope",
    "effect_stage",
    "framework",
    "http_method",
    "import_form",
    "imported_name",
    "is_type_only",
    "module",
    "operation_kind",
    "operation_name",
    "path_completeness",
    "provider",
    "registration_kind",
    "route_path",
    "target_basis",
    "target_name",
)


def _require_text(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be nonempty and have no surrounding whitespace")


@dataclass(frozen=True, slots=True)
class SearchField:
    """One approved searchable field: its name, bounded original value and tokens."""

    name: str
    value: str
    tokens: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text(self.name, "field name")
        _require_text(self.value, "field value")
        if not isinstance(self.tokens, tuple) or any(not isinstance(token, str) for token in self.tokens):
            raise TypeError("field tokens must be a tuple of strings")
        if len(self.tokens) > MAX_FIELD_TOKENS:
            raise ValueError("field tokens exceed the documented per-field maximum")
        if self.tokens != tokenize_value(self.value):
            raise RetrievalInvariantError("field tokens must be the canonical tokenization of the value")

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "value": self.value, "tokens": list(self.tokens)}


@dataclass(frozen=True, slots=True)
class SearchDocument:
    """Immutable retrieval projection of exactly one canonical CodeEntity.

    ``source_location`` and ``repository_relative_path`` are None when the
    canonical entity has no location; line numbers are never invented. ``fields``
    is sorted by field name so equal content yields equal documents regardless of
    graph insertion order. The name lookup mapping is a read-only proxy over a
    dictionary that is never exposed, so no mutable container is reachable here.
    """

    entity_id: str
    entity_kind: EntityKind
    name: str
    qualified_name: str
    language: str | None
    parent_id: str | None
    repository_relative_path: str | None
    source_location: SourceLocation | None
    fields: tuple[SearchField, ...]
    _by_name: Mapping[str, SearchField] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _require_text(self.entity_id, "entity_id")
        if not isinstance(self.entity_kind, EntityKind):
            raise TypeError("entity_kind must be EntityKind")
        _require_text(self.name, "name")
        _require_text(self.qualified_name, "qualified_name")
        if self.language is not None:
            _require_text(self.language, "language")
        if self.parent_id is not None:
            _require_text(self.parent_id, "parent_id")
        if self.repository_relative_path is not None:
            _require_text(self.repository_relative_path, "repository_relative_path")
        if self.source_location is not None and not isinstance(self.source_location, SourceLocation):
            raise TypeError("source_location must be SourceLocation or None")
        if not isinstance(self.fields, tuple) or any(not isinstance(item, SearchField) for item in self.fields):
            raise TypeError("fields must be a SearchField tuple")
        names = tuple(item.name for item in self.fields)
        if names != tuple(sorted(set(names))):
            raise ValueError("fields must be sorted by unique name")
        if (self.repository_relative_path is None) != (self.source_location is None):
            raise ValueError("repository path and source location must both be present or absent")
        object.__setattr__(self, "_by_name", MappingProxyType({item.name: item for item in self.fields}))

    def field(self, name: str) -> SearchField | None:
        """Return the projected field, or None when the entity does not carry it."""
        return self._by_name.get(name)

    def field_value(self, name: str) -> str | None:
        """Original bounded field value, or None when the field is absent."""
        found = self._by_name.get(name)
        return None if found is None else found.value

    def field_tokens(self, name: str) -> tuple[str, ...]:
        """Tokens of one projected field, empty when the field is absent."""
        found = self._by_name.get(name)
        return () if found is None else found.tokens

    @property
    def tokens(self) -> tuple[str, ...]:
        """All document tokens in field-name order, including repeats."""
        return tuple(token for item in self.fields for token in item.tokens)

    @property
    def token_count(self) -> int:
        """BM25 document length: every token occurrence across approved fields."""
        return sum(len(item.tokens) for item in self.fields)

    @property
    def distinct_tokens(self) -> frozenset[str]:
        return frozenset(self.tokens)

    def to_dict(self) -> dict[str, object]:
        return {
            "entity_id": self.entity_id,
            "entity_kind": self.entity_kind.value,
            "name": self.name,
            "qualified_name": self.qualified_name,
            "language": self.language,
            "parent_id": self.parent_id,
            "repository_relative_path": self.repository_relative_path,
            "source_location": (
                None
                if self.source_location is None
                else {
                    "file_path": self.source_location.file_path,
                    "start_line": self.source_location.start_line,
                    "end_line": self.source_location.end_line,
                }
            ),
            "fields": [item.to_dict() for item in self.fields],
        }


def build_document(entity: CodeEntity) -> SearchDocument:
    """Project one canonical entity into an immutable, allowlist-bounded document.

    Take only the allowlisted metadata keys and truncate each projected value to
    ``MAX_FIELD_VALUE_LENGTH``; the canonical CodeEntity keeps the full value.
    Signatures are deliberately excluded: they can embed arbitrary source-level
    literals, and Phase 2.3 does not index source content. Empty values are
    dropped because a database operation with no known target is genuinely
    unknown.
    """
    if not isinstance(entity, CodeEntity):
        raise TypeError("entity must be CodeEntity")
    metadata = dict(entity.metadata)
    location = entity.location
    raw: dict[str, str] = {
        FIELD_NAME: canonical_text(entity.name),
        FIELD_QUALIFIED_NAME: canonical_text(entity.qualified_name),
        FIELD_ENTITY_KIND: entity.kind.value,
    }
    if entity.language is not None:
        raw[FIELD_LANGUAGE] = canonical_text(entity.language)
    if location is not None:
        raw[FIELD_PATH] = canonical_text(location.file_path)
    for key in SEARCHABLE_METADATA_KEYS:
        value = metadata.get(key)
        if value:
            raw[key] = canonical_text(value)
    projected = tuple(
        (name, value[:MAX_FIELD_VALUE_LENGTH], tokenize_value(value)) for name, value in sorted(raw.items())
    )
    fields = tuple(SearchField(name, value, tokens) for name, value, tokens in projected if tokens)
    return SearchDocument(
        entity_id=entity.id,
        entity_kind=entity.kind,
        name=entity.name,
        qualified_name=entity.qualified_name,
        language=entity.language,
        parent_id=entity.parent_id,
        repository_relative_path=None if location is None else location.file_path,
        source_location=location,
        fields=fields,
    )
