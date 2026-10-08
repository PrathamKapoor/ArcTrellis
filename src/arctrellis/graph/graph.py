"""Append-oriented graph with indexed, deterministic structural queries."""

from bisect import insort
from collections import deque
from collections.abc import Iterator, Set

from arctrellis.core import CodeEntity, Relationship, RelationshipKind

from .errors import (
    DuplicateEntityError, DuplicateRelationshipError, UnknownEntityError,
    UnknownRelationshipError,
)
from .results import GraphPath, TraversalResult


def _require_id(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("lookup ID must be a string")


def _single_kind(kind: RelationshipKind | None) -> frozenset[RelationshipKind] | None:
    if kind is None:
        return None
    if not isinstance(kind, RelationshipKind):
        raise TypeError("kind must be RelationshipKind or None")
    return frozenset((kind,))


def _selected_kinds(
    kinds: Set[RelationshipKind] | None,
) -> frozenset[RelationshipKind] | None:
    if kinds is None:
        return None
    if not isinstance(kinds, Set) or any(not isinstance(kind, RelationshipKind) for kind in kinds):
        raise TypeError("relationship_kinds must be a set of RelationshipKind values or None")
    return frozenset(kinds)


class CodeGraph:
    """Own immutable records and sorted incoming/outgoing relationship indexes.

    Equal value reinsertions are idempotent; conflicting same-ID records fail.
    Parallel edges and self-loops are allowed. Every relationship endpoint must
    already exist. The graph is mutable, append-oriented and not thread-safe.
    Queries follow inserted relationships regardless of confidence; they do not
    infer relationships or certify the adequacy of their evidence.
    """

    def __init__(self) -> None:
        self._entities: dict[str, CodeEntity] = {}
        self._relationships: dict[str, Relationship] = {}
        self._outgoing: dict[str, list[str]] = {}
        self._incoming: dict[str, list[str]] = {}

    @property
    def entity_count(self) -> int:
        """Number of unique entity IDs stored in the graph."""
        return len(self._entities)

    @property
    def relationship_count(self) -> int:
        """Number of unique relationship IDs, including parallel edges."""
        return len(self._relationships)

    def add_entity(self, entity: CodeEntity) -> None:
        """Insert a record or accept an equal reinsertion; never overwrite it."""
        if not isinstance(entity, CodeEntity):
            raise TypeError("entity must be CodeEntity")
        existing = self._entities.get(entity.id)
        if existing is not None:
            if existing != entity:
                raise DuplicateEntityError(f"Conflicting entity ID: {entity.id!r}")
            return
        self._entities[entity.id] = entity
        self._outgoing[entity.id] = []
        self._incoming[entity.id] = []

    def add_relationship(self, relationship: Relationship) -> None:
        """Insert an edge only after duplicate and endpoint checks succeed."""
        if not isinstance(relationship, Relationship):
            raise TypeError("relationship must be Relationship")
        existing = self._relationships.get(relationship.id)
        if existing is not None:
            if existing != relationship:
                raise DuplicateRelationshipError(f"Conflicting relationship ID: {relationship.id!r}")
            return
        self.get_entity(relationship.source_entity_id)
        self.get_entity(relationship.target_entity_id)
        self._relationships[relationship.id] = relationship
        insort(self._outgoing[relationship.source_entity_id], relationship.id)
        insort(self._incoming[relationship.target_entity_id], relationship.id)

    def has_entity(self, entity_id: str) -> bool:
        """Whether this exact string ID is present; do not normalize it."""
        _require_id(entity_id)
        return entity_id in self._entities

    def has_relationship(self, relationship_id: str) -> bool:
        """Whether this exact string relationship ID is present."""
        _require_id(relationship_id)
        return relationship_id in self._relationships

    def get_entity(self, entity_id: str) -> CodeEntity:
        """Return the stored entity; raise UnknownEntityError if absent."""
        _require_id(entity_id)
        entity = self._entities.get(entity_id)
        if entity is None:
            raise UnknownEntityError(f"Unknown entity ID: {entity_id!r}")
        return entity

    def get_relationship(self, relationship_id: str) -> Relationship:
        """Return the stored relationship; raise UnknownRelationshipError if absent."""
        _require_id(relationship_id)
        relationship = self._relationships.get(relationship_id)
        if relationship is None:
            raise UnknownRelationshipError(f"Unknown relationship ID: {relationship_id!r}")
        return relationship

    def entities(self) -> tuple[CodeEntity, ...]:
        """Immutable snapshot sorted lexically by entity ID."""
        return tuple(self._entities[key] for key in sorted(self._entities))

    def relationships(self) -> tuple[Relationship, ...]:
        """Immutable snapshot sorted lexically by relationship ID."""
        return tuple(self._relationships[key] for key in sorted(self._relationships))

    def outgoing(
        self, entity_id: str, *, kind: RelationshipKind | None = None,
    ) -> tuple[Relationship, ...]:
        """Edges leaving a known entity, optionally filtered, sorted by edge ID."""
        self.get_entity(entity_id)
        return self._adjacent(entity_id, reverse=False, kinds=_single_kind(kind))

    def incoming(
        self, entity_id: str, *, kind: RelationshipKind | None = None,
    ) -> tuple[Relationship, ...]:
        """Edges entering a known entity, optionally filtered, sorted by edge ID."""
        self.get_entity(entity_id)
        return self._adjacent(entity_id, reverse=True, kinds=_single_kind(kind))

    def successors(
        self, entity_id: str, *, kind: RelationshipKind | None = None,
    ) -> tuple[CodeEntity, ...]:
        """Unique one-edge outgoing neighbors sorted by entity ID."""
        neighbor_ids = {edge.target_entity_id for edge in self.outgoing(entity_id, kind=kind)}
        return tuple(self._entities[key] for key in sorted(neighbor_ids))

    def predecessors(
        self, entity_id: str, *, kind: RelationshipKind | None = None,
    ) -> tuple[CodeEntity, ...]:
        """Unique one-edge incoming neighbors sorted by entity ID."""
        neighbor_ids = {edge.source_entity_id for edge in self.incoming(entity_id, kind=kind)}
        return tuple(self._entities[key] for key in sorted(neighbor_ids))

    def traverse_forward(
        self, start_entity_id: str, max_depth: int, *,
        relationship_kinds: Set[RelationshipKind] | None = None,
    ) -> TraversalResult:
        """Discover distinct nodes within max_depth outgoing steps, start included."""
        return self._traverse(start_entity_id, max_depth, reverse=False, kinds=relationship_kinds)

    def traverse_reverse(
        self, start_entity_id: str, max_depth: int, *,
        relationship_kinds: Set[RelationshipKind] | None = None,
    ) -> TraversalResult:
        """Discover distinct nodes within max_depth incoming steps, start included."""
        return self._traverse(start_entity_id, max_depth, reverse=True, kinds=relationship_kinds)

    def shortest_path(
        self, source_entity_id: str, target_entity_id: str, *,
        relationship_kinds: Set[RelationshipKind] | None = None,
    ) -> GraphPath | None:
        """Find an unweighted directed path, or None for disconnected known nodes.

        Unknown endpoints raise UnknownEntityError. Equal-length ties follow BFS
        discovery via relationship-ID-ordered adjacency. Same-node paths have one
        entity and no edges. None selects all kinds; an empty set selects no edges.
        """
        self.get_entity(source_entity_id)
        self.get_entity(target_entity_id)
        kinds = _selected_kinds(relationship_kinds)
        parents: dict[str, Relationship] = {}
        for entity_id, edge in self._breadth_first(source_entity_id, None, reverse=False, kinds=kinds):
            if edge is not None:
                parents[entity_id] = edge
            if entity_id == target_entity_id:
                return self._build_path(source_entity_id, target_entity_id, parents)
        return None

    def _adjacent(
        self, entity_id: str, *, reverse: bool,
        kinds: frozenset[RelationshipKind] | None,
    ) -> tuple[Relationship, ...]:
        index = self._incoming if reverse else self._outgoing
        return tuple(
            self._relationships[key] for key in index[entity_id]
            if kinds is None or self._relationships[key].kind in kinds
        )

    def _traverse(
        self, start_entity_id: str, max_depth: int, *, reverse: bool,
        kinds: Set[RelationshipKind] | None,
    ) -> TraversalResult:
        self.get_entity(start_entity_id)
        if type(max_depth) is not int:
            raise TypeError("max_depth must be an integer")
        if max_depth < 0:
            raise ValueError("max_depth must be >= 0")
        selected = _selected_kinds(kinds)
        return TraversalResult(tuple(
            self._entities[key]
            for key, _ in self._breadth_first(start_entity_id, max_depth, reverse=reverse, kinds=selected)
        ))

    def _breadth_first(
        self, start: str, max_depth: int | None, *, reverse: bool,
        kinds: frozenset[RelationshipKind] | None,
    ) -> Iterator[tuple[str, Relationship | None]]:
        """Yield (entity ID, discovery edge); the start has no discovery edge."""
        visited = {start}
        queue = deque(((start, 0),))
        yield start, None
        while queue:
            current, depth = queue.popleft()
            if max_depth is not None and depth >= max_depth:
                continue
            for edge in self._adjacent(current, reverse=reverse, kinds=kinds):
                neighbor = edge.source_entity_id if reverse else edge.target_entity_id
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))
                yield neighbor, edge

    def _build_path(
        self, source: str, target: str, parents: dict[str, Relationship],
    ) -> GraphPath:
        entity_ids = [target]
        edges: list[Relationship] = []
        current = target
        while current != source:
            edge = parents[current]
            edges.append(edge)
            current = edge.source_entity_id
            entity_ids.append(current)
        return GraphPath(
            tuple(self._entities[key] for key in reversed(entity_ids)),
            tuple(reversed(edges)),
        )
