"""Build-time one-hop graph context projection over the indexed graph snapshot.

Only the canonical relationship kinds that mean something at query time are
projected. DEFINES, CONTAINS, INHERITS, USES and IMPORTS are deliberately
excluded: they describe lexical containment or import reachability, never
execution, and retrieval must never treat them as invocation (D-133).

The projection is built once, from a single ``graph.relationships()`` read, and
stored inside the retrieval snapshot. Retrieval never re-reads the graph, never
calls an adjacency API per candidate and therefore never repeats the eager
allocation that public graph snapshots perform before any budget applies.

Neighbor lists are capped per entity and direction. When a cap is reached the
index records how many lists were capped, so a caller never reads a bounded
neighborhood as a complete one. Because capping is applied per entity and
direction, the two directions can hold different edge subsets; ``edge_count``
therefore counts the stored outgoing projection only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from arctrellis.core import Confidence, Evidence, Relationship, RelationshipKind

from .errors import RetrievalInvariantError

#: Canonical relationship kinds usable as retrieval context. Direction is always
#: the stored one; retrieval reports whether the matched entity is the edge
#: source (``outgoing``) or target (``incoming``).
CONTEXT_RELATIONSHIP_KINDS: tuple[RelationshipKind, ...] = (
    RelationshipKind.EXPOSES,
    RelationshipKind.CALLS,
    RelationshipKind.TESTS,
    RelationshipKind.WRITES_DATABASE,
    RelationshipKind.READS_DATABASE,
    RelationshipKind.APPLIES_MIDDLEWARE,
)

#: Per-edge contribution weight. Middleware is a pre-handler association and is
#: weighted below invocation, never presented as an execution dependency.
CONTEXT_EDGE_WEIGHTS: Mapping[RelationshipKind, float] = {
    RelationshipKind.EXPOSES: 1.0,
    RelationshipKind.CALLS: 0.8,
    RelationshipKind.WRITES_DATABASE: 0.6,
    RelationshipKind.READS_DATABASE: 0.5,
    RelationshipKind.TESTS: 0.5,
    RelationshipKind.APPLIES_MIDDLEWARE: 0.4,
}

#: Absolute cap on one context contribution. It equals the largest single-edge
#: weight, so the cap is a structural invariant rather than a tuned number: no
#: edge kind, neighbor count or hub degree can raise one contribution above it.
GRAPH_CONTEXT_BOOST_CAP = 1.0

DEFAULT_MAX_CONTEXT_NEIGHBORS = 16

OUTGOING = "outgoing"
INCOMING = "incoming"


class ContextDirection(StrEnum):
    """Stored edge direction relative to the returned hit."""

    OUTGOING = OUTGOING
    INCOMING = INCOMING


@dataclass(frozen=True, slots=True)
class ContextEdge:
    """Immutable projection of one stored relationship that may provide context."""

    relationship_id: str
    kind: RelationshipKind
    source_entity_id: str
    target_entity_id: str
    confidence: Confidence
    confidence_score: float | None
    evidence: tuple[Evidence, ...]

    def __post_init__(self) -> None:
        if not self.relationship_id or not self.source_entity_id or not self.target_entity_id:
            raise ValueError("context edges require nonempty relationship and endpoint IDs")
        if not isinstance(self.kind, RelationshipKind) or not isinstance(self.confidence, Confidence):
            raise TypeError("context edges require canonical relationship enums")
        if not isinstance(self.evidence, tuple):
            raise TypeError("context evidence must be a tuple of original Evidence records")

    @classmethod
    def from_relationship(cls, relationship: Relationship) -> ContextEdge:
        if not isinstance(relationship, Relationship):
            raise TypeError("relationship must be Relationship")
        return cls(
            relationship.id,
            relationship.kind,
            relationship.source_entity_id,
            relationship.target_entity_id,
            relationship.confidence,
            relationship.confidence_score,
            relationship.evidence,
        )

    def other_endpoint(self, entity_id: str) -> str:
        if entity_id == self.source_entity_id:
            return self.target_entity_id
        if entity_id == self.target_entity_id:
            return self.source_entity_id
        raise ValueError("entity is not an endpoint of this context edge")

    def direction_from(self, entity_id: str) -> str:
        if entity_id == self.source_entity_id:
            return OUTGOING
        if entity_id == self.target_entity_id:
            return INCOMING
        raise ValueError("entity is not an endpoint of this context edge")

    @property
    def weight(self) -> float:
        return CONTEXT_EDGE_WEIGHTS[self.kind]


@dataclass(frozen=True, slots=True)
class GraphContextIndex:
    """Bounded one-hop adjacency projection; never retains the CodeGraph."""

    outgoing: Mapping[str, tuple[ContextEdge, ...]]
    incoming: Mapping[str, tuple[ContextEdge, ...]]
    edge_count: int
    max_neighbors_per_entity: int
    capped_list_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.outgoing, Mapping) or not isinstance(self.incoming, Mapping):
            raise TypeError("context adjacency must be mappings")
        if type(self.max_neighbors_per_entity) is not int or self.max_neighbors_per_entity < 1:
            raise ValueError("max_neighbors_per_entity must be a positive integer")
        if type(self.capped_list_count) is not int or self.capped_list_count < 0:
            raise ValueError("capped_list_count must be a nonnegative integer")
        known = set(self.outgoing)
        if known != set(self.incoming):
            raise RetrievalInvariantError("context adjacency must describe the same entity set in both directions")
        for identifier, edges in self.outgoing.items():
            if not isinstance(edges, tuple) or len(edges) > self.max_neighbors_per_entity:
                raise RetrievalInvariantError("context adjacency lists must be bounded tuples")
            if edges != tuple(sorted(edges, key=lambda edge: edge.relationship_id)):
                raise RetrievalInvariantError("context adjacency must be ordered by relationship ID")
            stored = tuple(edge.relationship_id for edge in edges)
            if len(set(stored)) != len(stored):
                raise RetrievalInvariantError("context adjacency must not repeat a relationship")
            if any(edge.source_entity_id != identifier for edge in edges):
                raise RetrievalInvariantError("outgoing context edges must start at their own entity")
            if any(edge.target_entity_id != identifier for edge in self.incoming[identifier]):
                raise RetrievalInvariantError("incoming context edges must end at their own entity")
        if self.edge_count != sum(len(edges) for edges in self.outgoing.values()):
            raise RetrievalInvariantError("context edge count must match the stored outgoing projection")

    @property
    def entity_count(self) -> int:
        return len(self.outgoing)

    def edges(self, entity_id: str, *, limit: int) -> tuple[tuple[ContextEdge, str], ...]:
        """One-hop neighbors as ``(edge, direction)``, ordered and length bounded.

        Incoming edges come first so an incoming association is never hidden by a
        large outgoing neighborhood, and the caller's limit always applies.
        """
        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be a positive integer")
        combined = tuple((edge, INCOMING) for edge in self.incoming.get(entity_id, ())) + tuple(
            (edge, OUTGOING) for edge in self.outgoing.get(entity_id, ())
        )
        return combined[:limit]


def build_graph_context_index(
    relationships: tuple[Relationship, ...],
    entity_ids: frozenset[str],
    *,
    max_neighbors_per_entity: int = DEFAULT_MAX_CONTEXT_NEIGHBORS,
) -> GraphContextIndex:
    """Project allowed one-hop relationships once, in deterministic bounded form.

    ``relationships`` must be the single already-materialized snapshot read from
    the graph being indexed; it is never re-read per candidate. A relationship
    whose endpoints are not part of the corpus is an invariant failure rather
    than a silently dropped context record.
    """
    if type(max_neighbors_per_entity) is not int or max_neighbors_per_entity < 1:
        raise ValueError("max_neighbors_per_entity must be a positive integer")
    outgoing_lists: dict[str, list[ContextEdge]] = {}
    incoming_lists: dict[str, list[ContextEdge]] = {}
    capped = 0
    for relationship in relationships:
        if relationship.kind not in CONTEXT_RELATIONSHIP_KINDS:
            continue
        if relationship.source_entity_id not in entity_ids or relationship.target_entity_id not in entity_ids:
            raise RetrievalInvariantError("context relationship references an entity outside the retrieval corpus")
        edge = ContextEdge.from_relationship(relationship)
        for identifier, table in (
            (relationship.source_entity_id, outgoing_lists),
            (relationship.target_entity_id, incoming_lists),
        ):
            bucket = table.setdefault(identifier, [])
            if len(bucket) >= max_neighbors_per_entity:
                capped += 1
                continue
            bucket.append(edge)
    frozen_outgoing = {
        identifier: tuple(sorted(bucket, key=lambda edge: edge.relationship_id))
        for identifier, bucket in outgoing_lists.items()
    }
    frozen_incoming = {
        identifier: tuple(sorted(bucket, key=lambda edge: edge.relationship_id))
        for identifier, bucket in incoming_lists.items()
    }
    edge_count = sum(len(bucket) for bucket in frozen_outgoing.values())
    identifiers = frozenset(entity_ids)
    return GraphContextIndex(
        outgoing=MappingProxyType(
            {identifier: frozen_outgoing.get(identifier, ()) for identifier in sorted(identifiers)}
        ),
        incoming=MappingProxyType(
            {identifier: frozen_incoming.get(identifier, ()) for identifier in sorted(identifiers)}
        ),
        edge_count=edge_count,
        max_neighbors_per_entity=max_neighbors_per_entity,
        capped_list_count=capped,
    )
