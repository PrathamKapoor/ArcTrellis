"""Language-independent database observations and deterministic summaries."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from re import fullmatch
from uuid import NAMESPACE_URL, uuid5

from arctrellis.core import CodeEntity, EntityKind, SourceLocation
from arctrellis.core.models import Metadata, _require_text, _validate_metadata
from arctrellis.extraction.models import _entity_span
from arctrellis.extraction.source import _location
from arctrellis.ingestion import Language
from arctrellis.parsing import SyntaxSpan


class DatabaseOperationKind(StrEnum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    TRANSACTION = "transaction"
    UNKNOWN = "unknown"


_OWNERS = (EntityKind.MODULE, EntityKind.FUNCTION, EntityKind.METHOD)


@dataclass(frozen=True, slots=True)
class DatabaseOperationObservation:
    """An adapter's claimed operation; construction does not certify its truth.

    Use make_database_operation_observation to check canonical owner coordinates.
    No universal confidence or database graph edge follows from this record.
    """

    path: str
    language: Language
    owner_entity_id: str
    owner_kind: EntityKind
    operation_kind: DatabaseOperationKind
    provider: str
    operation_name: str
    location: SourceLocation
    span: SyntaxSpan
    target_name: str | None = None
    metadata: Metadata = ()
    id: str = field(init=False)

    def __post_init__(self) -> None:
        _require_text(self.owner_entity_id, "owner_entity_id")
        _require_text(self.provider, "provider")
        _require_text(self.operation_name, "operation_name")
        if self.target_name is not None:
            _require_text(self.target_name, "target_name")
        if not isinstance(self.language, Language) or not isinstance(self.operation_kind, DatabaseOperationKind):
            raise TypeError("database language/operation kind must be canonical enums")
        if not isinstance(self.owner_kind, EntityKind):
            raise TypeError("owner_kind must be EntityKind")
        if self.owner_kind not in _OWNERS:
            raise ValueError("database owner must be MODULE, FUNCTION or METHOD")
        if not isinstance(self.location, SourceLocation) or not isinstance(self.span, SyntaxSpan):
            raise TypeError("database location/span must be owned coordinates")
        if self.location != _location(self.path, self.span):
            raise ValueError("database location must agree with path and exact coordinates")
        if fullmatch(r"[a-z][a-z0-9_]*", self.provider) is None:
            raise ValueError("provider must be a stable lowercase identifier")
        _validate_metadata(self.metadata)
        components = (
            "arctrellis-database-operation-v1",
            self.language.value,
            self.path,
            self.owner_entity_id,
            self.provider,
            self.operation_kind.value,
            self.operation_name,
            self.target_name,
            self.span.start_byte,
            self.span.end_byte,
        )
        object.__setattr__(
            self, "id", str(uuid5(NAMESPACE_URL, json.dumps(components, ensure_ascii=True, separators=(",", ":"))))
        )


def make_database_operation_observation(
    *,
    owner: CodeEntity,
    language: Language,
    operation_kind: DatabaseOperationKind,
    provider: str,
    operation_name: str,
    span: SyntaxSpan,
    target_name: str | None = None,
    metadata: Metadata = (),
) -> DatabaseOperationObservation:
    """Validate a supplied canonical execution owner; never inspect target source."""
    if not isinstance(owner, CodeEntity) or not isinstance(span, SyntaxSpan):
        raise TypeError("database observation requires a canonical owner and owned span")
    if not isinstance(language, Language):
        raise TypeError("language must be Language")
    if owner.kind not in _OWNERS or owner.location is None or owner.language != language.value:
        raise ValueError("database observation requires a matching canonical execution owner")
    owner_span = _entity_span(owner)
    if owner.location != _location(owner.location.file_path, owner_span):
        raise ValueError("database owner must retain consistent canonical coordinates")
    if not (
        owner_span.start_byte <= span.start_byte <= span.end_byte <= owner_span.end_byte
        and (owner_span.start_line, owner_span.start_column) <= (span.start_line, span.start_column)
        and (span.end_line, span.end_column) <= (owner_span.end_line, owner_span.end_column)
    ):
        raise ValueError("database operation must lie inside its canonical execution owner")
    path = owner.location.file_path
    return DatabaseOperationObservation(
        path,
        language,
        owner.id,
        owner.kind,
        operation_kind,
        provider,
        operation_name,
        _location(path, span),
        span,
        target_name,
        metadata,
    )


def _operation_order(observation: DatabaseOperationObservation) -> tuple[str, int, int, str]:
    return observation.path, observation.span.start_byte, observation.span.end_byte, observation.id


@dataclass(frozen=True, slots=True)
class DatabaseAnalysisResult:
    """Ordered adapter output, not a repository extractor or graph conversion."""

    observations: tuple[DatabaseOperationObservation, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.observations, tuple) or any(
            not isinstance(o, DatabaseOperationObservation) for o in self.observations
        ):
            raise TypeError("database observations must be an immutable canonical tuple")
        if self.observations != tuple(sorted(self.observations, key=_operation_order)) or len(
            {o.id for o in self.observations}
        ) != len(self.observations):
            raise ValueError("database observations must be ordered and unique")

    @classmethod
    def from_observations(cls, observations: tuple[DatabaseOperationObservation, ...]) -> DatabaseAnalysisResult:
        if not isinstance(observations, tuple) or any(
            not isinstance(o, DatabaseOperationObservation) for o in observations
        ):
            raise TypeError("database observations must be an immutable canonical tuple")
        return cls(tuple(sorted(observations, key=_operation_order)))

    @property
    def observation_count(self) -> int:
        return len(self.observations)

    @property
    def operation_counts(self) -> tuple[tuple[DatabaseOperationKind, int], ...]:
        return tuple(
            sorted(Counter(o.operation_kind for o in self.observations).items(), key=lambda item: item[0].value)
        )

    @property
    def provider_counts(self) -> tuple[tuple[str, int], ...]:
        return tuple(sorted(Counter(o.provider for o in self.observations).items()))
