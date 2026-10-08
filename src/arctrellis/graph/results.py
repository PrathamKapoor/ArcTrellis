"""Immutable query results holding the original canonical domain records."""

from dataclasses import dataclass

from arctrellis.core import CodeEntity, Relationship


def _require_records(records: tuple[object, ...], record_type: type[object], field: str) -> None:
    if not isinstance(records, tuple):
        raise TypeError(f"{field} must be a tuple")
    if any(not isinstance(record, record_type) for record in records):
        raise TypeError(f"{field} must contain {record_type.__name__} records")


@dataclass(frozen=True, slots=True)
class TraversalResult:
    """Distinct nodes in BFS discovery order; entities[0] is the starting node.

    This result contains nodes only. It is not a path or an induced subgraph.
    """

    entities: tuple[CodeEntity, ...]

    def __post_init__(self) -> None:
        _require_records(self.entities, CodeEntity, "entities")
        if not self.entities:
            raise ValueError("traversal must contain its starting entity")
        if len({entity.id for entity in self.entities}) != len(self.entities):
            raise ValueError("traversal must contain distinct entity IDs")


@dataclass(frozen=True, slots=True)
class GraphPath:
    """A directed walk retaining each edge and its original embedded evidence.

    Requires one more entity than relationship and matching adjacent endpoints.
    A zero-edge path contains one entity. No path is represented by None, not by
    an empty GraphPath. Shortest paths have no repeated nodes; arbitrary walks may.
    """

    entities: tuple[CodeEntity, ...]
    relationships: tuple[Relationship, ...]

    def __post_init__(self) -> None:
        _require_records(self.entities, CodeEntity, "entities")
        _require_records(self.relationships, Relationship, "relationships")
        if len(self.entities) != len(self.relationships) + 1:
            raise ValueError("path must contain exactly one more entity than relationship")
        for index, edge in enumerate(self.relationships):
            if edge.source_entity_id != self.entities[index].id or edge.target_entity_id != self.entities[index + 1].id:
                raise ValueError("path relationships must connect adjacent entities in source-to-target order")
