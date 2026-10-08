"""Immutable import-site decisions, separate from the lexical index snapshot."""

from dataclasses import dataclass
from enum import StrEnum

from arctrellis.graph import CodeGraph


class ImportResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class ImportResolution:
    import_entity_id: str
    status: ImportResolutionStatus
    target_module_id: str | None
    candidate_module_ids: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        for text in (self.import_entity_id, self.reason):
            if not isinstance(text, str) or not text or text != text.strip():
                raise ValueError("resolution identity/reason must be nonempty unpadded strings")
        if not isinstance(self.status, ImportResolutionStatus):
            raise TypeError("status must be ImportResolutionStatus")
        if not isinstance(self.candidate_module_ids, tuple) or any(
            not isinstance(i, str) or not i or i != i.strip() for i in self.candidate_module_ids
        ):
            raise TypeError("candidates must be an immutable tuple of IDs")
        if tuple(sorted(set(self.candidate_module_ids))) != self.candidate_module_ids:
            raise ValueError("candidates must be sorted and unique")
        if self.status is ImportResolutionStatus.RESOLVED:
            if self.target_module_id is None or self.candidate_module_ids != (self.target_module_id,):
                raise ValueError("resolved import requires exactly one matching target")
        elif self.target_module_id is not None:
            raise ValueError("non-resolved import cannot have a target")
        elif self.status is ImportResolutionStatus.AMBIGUOUS:
            if len(self.candidate_module_ids) < 2:
                raise ValueError("ambiguous import requires multiple candidates")
        elif self.candidate_module_ids:
            raise ValueError("unresolved import cannot have candidates")


@dataclass(frozen=True, slots=True)
class ImportResolutionResult:
    """Frozen decisions owning a new graph; original index graph is never mutated."""

    graph: CodeGraph
    resolutions: tuple[ImportResolution, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.graph, CodeGraph):
            raise TypeError("graph must be CodeGraph")
        if not isinstance(self.resolutions, tuple) or any(
            not isinstance(r, ImportResolution) for r in self.resolutions
        ):
            raise TypeError("resolutions must be an immutable decision tuple")
        ids = tuple(r.import_entity_id for r in self.resolutions)
        if tuple(sorted(set(ids))) != ids:
            raise ValueError("resolution sites must be unique and sorted by ID")

    @property
    def resolved_count(self) -> int:
        return sum(r.status is ImportResolutionStatus.RESOLVED for r in self.resolutions)

    @property
    def unresolved_count(self) -> int:
        return sum(r.status is ImportResolutionStatus.UNRESOLVED for r in self.resolutions)

    @property
    def ambiguous_count(self) -> int:
        return sum(r.status is ImportResolutionStatus.AMBIGUOUS for r in self.resolutions)
