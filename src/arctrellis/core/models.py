"""Immutable domain records; constructors validate structure, not source truth.

IDs are opaque caller-supplied strings. Producers must reproduce IDs within a
repository revision; these records do not enforce repository-wide uniqueness.
Metadata is an ordered tuple of unique string-key/string-value pairs. Keeping
values shallow and immutable makes equality, hashing and serialization explicit.
"""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from pathlib import PureWindowsPath
from re import fullmatch

type Metadata = tuple[tuple[str, str], ...]


class EntityKind(StrEnum):
    """Kinds of repository entities, independent of parser implementations."""

    REPOSITORY = "REPOSITORY"
    DIRECTORY = "DIRECTORY"
    FILE = "FILE"
    MODULE = "MODULE"
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"
    VARIABLE = "VARIABLE"
    IMPORT = "IMPORT"
    API_ENDPOINT = "API_ENDPOINT"
    MIDDLEWARE = "MIDDLEWARE"
    TEST = "TEST"
    DATABASE_OPERATION = "DATABASE_OPERATION"


class RelationshipKind(StrEnum):
    """Directional predicates: source entity performs this relation to target."""

    DEFINES = "DEFINES"
    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    INHERITS = "INHERITS"
    USES = "USES"
    EXPOSES = "EXPOSES"
    APPLIES_MIDDLEWARE = "APPLIES_MIDDLEWARE"
    TESTS = "TESTS"
    READS_DATABASE = "READS_DATABASE"
    WRITES_DATABASE = "WRITES_DATABASE"


class Confidence(StrEnum):
    """Static-analysis resolution strength; not a runtime observation."""

    PROVEN = "PROVEN"  # Direct resolution supported by strong static evidence.
    LIKELY = "LIKELY"  # Strong evidence with incomplete semantic information.
    POSSIBLE = "POSSIBLE"  # One candidate among multiple possible relationships.
    UNRESOLVED = "UNRESOLVED"  # Relevant construct exists; target is unidentified.


def _require_text(value: str, field: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    if not value or value != value.strip():
        raise ValueError(f"{field} must be nonempty and have no surrounding whitespace")


def _require_instance(value: object, expected: type, field: str) -> None:
    if not isinstance(value, expected):
        raise TypeError(f"{field} must be {expected.__name__}")


def _validate_metadata(metadata: Metadata) -> None:
    if not isinstance(metadata, tuple):
        raise TypeError("metadata must be a tuple of string pairs")
    keys: set[str] = set()
    for pair in metadata:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise TypeError("metadata entries must be tuples of two strings")
        key, value = pair
        _require_text(key, "metadata key")
        if not isinstance(value, str):
            raise TypeError("metadata values must be strings")
        if key in keys:
            raise ValueError(f"duplicate metadata key: {key}")
        keys.add(key)


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Inclusive, 1-based line range in an unmodified relative POSIX path.

    Adapters must provide forward slashes. Absolute paths, drive-relative paths,
    traversal, dot segments and repeated/trailing separators are rejected.
    This validates path syntax only; it does not access the filesystem.
    """

    file_path: str
    start_line: int
    end_line: int

    def __post_init__(self) -> None:
        _require_text(self.file_path, "file_path")
        if (
            "\\" in self.file_path
            or PureWindowsPath(self.file_path).anchor
            or any(ord(character) < 32 for character in self.file_path)
            or any(part in ("", ".", "..") for part in self.file_path.split("/"))
        ):
            raise ValueError("file_path must be a canonical repository-relative POSIX path")
        for field in ("start_line", "end_line"):
            if type(getattr(self, field)) is not int:
                raise TypeError(f"{field} must be an integer")
        if self.start_line < 1:
            raise ValueError("start_line must be >= 1")
        if self.end_line < self.start_line:
            raise ValueError("end_line must be >= start_line")


@dataclass(frozen=True, slots=True)
class CodeEntity:
    """Named repository concept; source, ownership and language may be absent."""

    id: str
    kind: EntityKind
    name: str
    qualified_name: str
    location: SourceLocation | None = None
    parent_id: str | None = None
    language: str | None = None
    metadata: Metadata = ()

    def __post_init__(self) -> None:
        for field in ("id", "name", "qualified_name"):
            _require_text(getattr(self, field), field)
        _require_instance(self.kind, EntityKind, "kind")
        if self.location is not None:
            _require_instance(self.location, SourceLocation, "location")
        for field in ("parent_id", "language"):
            value = getattr(self, field)
            if value is not None:
                _require_text(value, field)
        _validate_metadata(self.metadata)


@dataclass(frozen=True, slots=True)
class Evidence:
    """Source range and extensible snake_case static-analysis method name."""

    id: str
    location: SourceLocation
    analysis_method: str
    metadata: Metadata = ()

    def __post_init__(self) -> None:
        _require_text(self.id, "id")
        _require_instance(self.location, SourceLocation, "location")
        _require_text(self.analysis_method, "analysis_method")
        if fullmatch(r"[a-z][a-z0-9_]*", self.analysis_method) is None:
            raise ValueError("analysis_method must be a lowercase snake_case identifier")
        _validate_metadata(self.metadata)


@dataclass(frozen=True, slots=True)
class Relationship:
    """Source → target assertion with embedded immutable evidence records.

    confidence_score is an optional finite value in [0, 1]. No universal score
    thresholds are imposed on classifications. Producers are responsible for
    evidence adequacy and may use an opaque placeholder target ID when unresolved.
    Referential integrity belongs to the future graph container.
    """

    id: str
    source_entity_id: str
    kind: RelationshipKind
    target_entity_id: str
    confidence: Confidence
    confidence_score: float | None = None
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        for field in ("id", "source_entity_id", "target_entity_id"):
            _require_text(getattr(self, field), field)
        _require_instance(self.kind, RelationshipKind, "kind")
        _require_instance(self.confidence, Confidence, "confidence")
        if self.confidence_score is not None:
            if type(self.confidence_score) not in (int, float):
                raise TypeError("confidence_score must be a number")
            if not 0 <= self.confidence_score <= 1 or not isfinite(self.confidence_score):
                raise ValueError("confidence_score must be finite and between 0 and 1")
        if not isinstance(self.evidence, tuple):
            raise TypeError("evidence must be a tuple of Evidence records")
        ids: set[str] = set()
        for record in self.evidence:
            _require_instance(record, Evidence, "evidence item")
            if record.id in ids:
                raise ValueError(f"duplicate evidence id: {record.id}")
            ids.add(record.id)
