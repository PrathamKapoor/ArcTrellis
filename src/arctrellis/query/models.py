"""Immutable value results referencing original immutable graph records, never graphs/source.

Concurrent external graph mutation is unsupported. Confidence summaries are weakest
supporting edge summaries, never calibrated probabilities or runtime execution claims.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from json import dumps
from uuid import NAMESPACE_URL, uuid5

from arctrellis.core import CodeEntity, Confidence, Relationship
from arctrellis.graph import CodeGraph, GraphPath
from arctrellis.graph.errors import GraphError

from .errors import InvalidQueryLimitError, QueryGraphInvariantError


class QueryStatus(StrEnum):
    FOUND = "FOUND"
    NO_KNOWN_PATH = "NO_KNOWN_PATH"


class AnalysisCompleteness(StrEnum):
    """Caller-supplied source-analysis context, independent of static reachability."""

    UNKNOWN = "unknown"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class TraversalDirection(StrEnum):
    FORWARD = "forward"
    REVERSE = "reverse"


def validate_limits(max_depth: int, max_paths: int, max_expansions: int) -> None:
    for name, value in (("max_depth", max_depth), ("max_paths", max_paths), ("max_expansions", max_expansions)):
        if type(value) is not int or value <= 0:
            raise InvalidQueryLimitError(f"{name} must be a positive integer")


@dataclass(frozen=True, slots=True)
class EvidencePath:
    """Simple path in stored forward edge order, including for reverse searches.

    Use from_graph to validate membership at query time. Direct construction checks
    continuity only; it cannot authenticate a graph or source. Empty proof remains
    empty. If any edge score is missing, weakest_edge_score is unknown (None).
    """

    entities: tuple[CodeEntity, ...]
    relationships: tuple[Relationship, ...]

    def __post_init__(self) -> None:
        try:
            GraphPath(self.entities, self.relationships)
            if len(set(self.entity_ids)) != len(self.entities):
                raise ValueError("query paths must be simple")
        except (TypeError, ValueError) as error:
            raise QueryGraphInvariantError("invalid path continuity or records") from error

    @classmethod
    def from_graph(
        cls, graph: CodeGraph, entities: tuple[CodeEntity, ...], relationships: tuple[Relationship, ...]
    ) -> EvidencePath:
        path = cls(entities, relationships)
        try:
            if any(graph.get_entity(e.id) != e for e in entities) or any(
                graph.get_relationship(r.id) != r for r in relationships
            ):
                raise QueryGraphInvariantError("path records disagree with graph")
        except GraphError as error:
            raise QueryGraphInvariantError("path references missing graph records") from error
        return path

    @property
    def entity_ids(self) -> tuple[str, ...]:
        return tuple(e.id for e in self.entities)

    @property
    def relationship_ids(self) -> tuple[str, ...]:
        return tuple(e.id for e in self.relationships)

    @property
    def hop_count(self) -> int:
        return len(self.relationships)

    @property
    def path_id(self) -> str:
        return str(uuid5(NAMESPACE_URL, dumps(["arctrellis-query-path-v1", self.relationship_ids, self.entity_ids])))

    @property
    def weakest_edge_score(self) -> float | None:
        scores = tuple(edge.confidence_score for edge in self.relationships)
        if not scores or any(score is None for score in scores):
            return None
        return min(score for score in scores if score is not None)

    @property
    def confidence_classification(self) -> Confidence | None:
        rank = (Confidence.PROVEN, Confidence.LIKELY, Confidence.POSSIBLE, Confidence.UNRESOLVED)
        return max((e.confidence for e in self.relationships), key=rank.index, default=None)

    def to_dict(self) -> dict[str, object]:
        return {
            "path_id": self.path_id,
            "entity_ids": list(self.entity_ids),
            "relationship_ids": list(self.relationship_ids),
            "hop_count": self.hop_count,
            "weakest_edge_score": self.weakest_edge_score,
            "confidence_classification": self.confidence_classification.value
            if self.confidence_classification
            else None,
            "entities": [entity_dict(e) for e in self.entities],
            "relationships": [relationship_dict(e) for e in self.relationships],
        }


def entity_dict(entity: CodeEntity) -> dict[str, object]:
    return {
        "id": entity.id,
        "kind": entity.kind.value,
        "name": entity.name,
        "qualified_name": entity.qualified_name,
        "location": asdict(entity.location) if entity.location else None,
        "parent_id": entity.parent_id,
        "language": entity.language,
        "metadata": dict(entity.metadata),
        "signature": entity.signature,
    }


def relationship_dict(edge: Relationship) -> dict[str, object]:
    return {
        "relationship_id": edge.id,
        "kind": edge.kind.value,
        "source_id": edge.source_entity_id,
        "target_id": edge.target_entity_id,
        "confidence": edge.confidence.value,
        "score": edge.confidence_score,
        "evidence": [
            {
                "id": p.id,
                "location": asdict(p.location),
                "analysis_method": p.analysis_method,
                "metadata": dict(p.metadata),
            }
            for p in edge.evidence
        ],
    }


@dataclass(frozen=True, slots=True)
class PathQueryResult:
    """Bounded discovered paths, sorted by length/edge IDs/entity IDs.

    NO_KNOWN_PATH is never proof of absence at runtime, even for COMPLETE analysis.
    expansions counts examined adjacency records (including rejected kinds/cycles).
    """

    query_kind: str
    source_entity_id: str
    paths: tuple[EvidencePath, ...]
    direction: TraversalDirection
    max_depth: int
    max_paths: int
    max_expansions: int
    expansions: int
    truncation_reasons: tuple[str, ...] = ()
    analysis_completeness: AnalysisCompleteness = AnalysisCompleteness.UNKNOWN

    def __post_init__(self) -> None:
        validate_limits(self.max_depth, self.max_paths, self.max_expansions)
        if not isinstance(self.direction, TraversalDirection) or not isinstance(
            self.analysis_completeness, AnalysisCompleteness
        ):
            raise TypeError("direction/completeness must be canonical query enums")
        if not isinstance(self.paths, tuple) or any(not isinstance(p, EvidencePath) for p in self.paths):
            raise TypeError("paths must be an EvidencePath tuple")
        if type(self.expansions) is not int or not 0 <= self.expansions <= self.max_expansions:
            raise ValueError("invalid expansion count")
        if len(self.paths) > self.max_paths or len({p.path_id for p in self.paths}) != len(self.paths):
            raise ValueError("invalid path count or duplicates")
        if tuple(sorted(self.paths, key=path_order)) != self.paths:
            raise ValueError("paths must be deterministically ordered")
        for path in self.paths:
            source = path.entity_ids[0] if self.direction is TraversalDirection.FORWARD else path.entity_ids[-1]
            if source != self.source_entity_id or path.hop_count > self.max_depth:
                raise ValueError("path source or depth disagrees with result")
        if not isinstance(self.truncation_reasons, tuple) or self.truncation_reasons != tuple(
            sorted(set(self.truncation_reasons))
        ):
            raise ValueError("truncation reasons must be sorted and unique")
        if any(r not in ("max_depth", "max_paths", "max_expansions") for r in self.truncation_reasons):
            raise ValueError("unknown truncation reason")

    @property
    def status(self) -> QueryStatus:
        return QueryStatus.FOUND if self.paths else QueryStatus.NO_KNOWN_PATH

    @property
    def truncated(self) -> bool:
        return bool(self.truncation_reasons)

    def to_dict(self) -> dict[str, object]:
        return {
            "query_kind": self.query_kind,
            "source_entity_id": self.source_entity_id,
            "status": self.status.value,
            "paths": [p.to_dict() for p in self.paths],
            "direction": self.direction.value,
            "truncated": self.truncated,
            "truncation_reasons": list(self.truncation_reasons),
            "max_depth": self.max_depth,
            "max_paths": self.max_paths,
            "max_expansions": self.max_expansions,
            "expansions": self.expansions,
            "analysis_completeness": self.analysis_completeness.value,
        }


def path_order(path: EvidencePath) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    return path.hop_count, path.relationship_ids, path.entity_ids
