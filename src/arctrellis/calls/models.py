"""Lightweight invocation observations, independent of target resolution."""

from dataclasses import dataclass
from enum import StrEnum

from arctrellis.core import SourceLocation
from arctrellis.core.models import _require_text
from arctrellis.extraction.source import _location
from arctrellis.graph import CodeGraph
from arctrellis.ingestion import Language
from arctrellis.parsing import SyntaxSpan


class CalleeKind(StrEnum):
    NAME = "name"
    MEMBER = "member"


@dataclass(frozen=True, slots=True)
class CallSite:
    """A source invocation with a canonical owner, but no chosen target.

    Span is an owned value, not a retained syntax node or source buffer.
    Repository validation checks owner existence and execution-scope kind.
    """

    id: str
    path: str
    language: Language
    owner_entity_id: str
    callee_kind: CalleeKind
    callee_parts: tuple[str, ...]
    location: SourceLocation
    span: SyntaxSpan

    def __post_init__(self) -> None:
        _require_text(self.id, "id")
        _require_text(self.owner_entity_id, "owner_entity_id")
        if not isinstance(self.language, Language) or not isinstance(self.callee_kind, CalleeKind):
            raise TypeError("language and callee_kind must be canonical enums")
        if not isinstance(self.location, SourceLocation) or not isinstance(self.span, SyntaxSpan):
            raise TypeError("location/span must be owned source coordinates")
        if self.location != _location(self.path, self.span):
            raise ValueError("call location must match path and exact span")
        if not isinstance(self.callee_parts, tuple):
            raise TypeError("callee_parts must be an immutable tuple")
        if not self.callee_parts or any(
            not isinstance(p, str) or not p or not p.replace("$", "_").isidentifier() for p in self.callee_parts
        ):
            raise ValueError("callee parts must be simple identifier spellings")
        if (self.callee_kind is CalleeKind.NAME and len(self.callee_parts) != 1) or (
            self.callee_kind is CalleeKind.MEMBER and len(self.callee_parts) < 2
        ):
            raise ValueError("callee kind must match its part count")


def _site_order(site: CallSite) -> tuple[str, int, int, str]:
    return site.path, site.span.start_byte, site.span.end_byte, site.id


class CallResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class CallResolution:
    """Candidates are callable IDs, or binding IDs witnessing binding ambiguity."""

    call_site_id: str
    status: CallResolutionStatus
    target_entity_id: str | None
    candidate_entity_ids: tuple[str, ...]
    reason: str
    resolution_method: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.call_site_id, "call_site_id")
        _require_text(self.reason, "reason")
        if not isinstance(self.status, CallResolutionStatus):
            raise TypeError("status must be CallResolutionStatus")
        if not isinstance(self.candidate_entity_ids, tuple):
            raise TypeError("candidate IDs must be a tuple")
        for candidate in self.candidate_entity_ids:
            _require_text(candidate, "candidate ID")
        if self.candidate_entity_ids != tuple(sorted(set(self.candidate_entity_ids))):
            raise ValueError("candidate IDs must be sorted and unique")
        if self.status is CallResolutionStatus.RESOLVED:
            if self.target_entity_id is None or self.candidate_entity_ids != (self.target_entity_id,):
                raise ValueError("resolved call requires exactly one matching target")
            if self.resolution_method is None:
                raise ValueError("resolved call requires an analysis method")
            _require_text(self.resolution_method, "resolution_method")
        elif self.target_entity_id is not None or self.resolution_method is not None:
            raise ValueError("non-resolved call cannot have a target or analysis method")
        elif self.status is CallResolutionStatus.AMBIGUOUS:
            if len(self.candidate_entity_ids) < 2:
                raise ValueError("ambiguous call requires multiple candidate witnesses")
        elif self.candidate_entity_ids:
            raise ValueError("unresolved call cannot have candidates")


@dataclass(frozen=True, slots=True)
class CallResolutionResult:
    """Fresh graph plus one decision per call, in the input's source order."""

    graph: CodeGraph
    resolutions: tuple[CallResolution, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.graph, CodeGraph):
            raise TypeError("graph must be CodeGraph")
        if not isinstance(self.resolutions, tuple) or any(not isinstance(r, CallResolution) for r in self.resolutions):
            raise TypeError("resolutions must be an immutable tuple")
        if len({r.call_site_id for r in self.resolutions}) != len(self.resolutions):
            raise ValueError("call resolution sites must be unique")

    @property
    def resolved_count(self) -> int:
        return sum(r.status is CallResolutionStatus.RESOLVED for r in self.resolutions)

    @property
    def unresolved_count(self) -> int:
        return sum(r.status is CallResolutionStatus.UNRESOLVED for r in self.resolutions)

    @property
    def ambiguous_count(self) -> int:
        return sum(r.status is CallResolutionStatus.AMBIGUOUS for r in self.resolutions)
