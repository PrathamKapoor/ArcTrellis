"""Independent database interaction snapshots; no syntax or filesystem access."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from arctrellis.calls.ids import _identity
from arctrellis.core import CodeEntity, Confidence, EntityKind, Evidence, Relationship, RelationshipKind
from arctrellis.extraction.source import _span_metadata
from arctrellis.graph import CodeGraph

from .models import DatabaseAnalysisResult, DatabaseOperationKind, DatabaseOperationObservation

if TYPE_CHECKING:
    from arctrellis.indexing import RepositoryIndexResult


def _operation_entity(observation: DatabaseOperationObservation) -> CodeEntity:
    metadata = dict(observation.metadata)
    metadata.update(_span_metadata(observation.span))
    metadata.update(
        provider=observation.provider,
        operation_kind=observation.operation_kind.value,
        operation_name=observation.operation_name,
        observation_id=observation.id,
    )
    if observation.target_name is not None:
        metadata["target_name"] = observation.target_name
    detail = (observation.target_name + "." if observation.target_name else "") + observation.operation_name
    name = observation.provider + ":" + detail + "@" + str(observation.span.start_byte)
    return CodeEntity(
        id=_identity("arctrellis-database-entity-v1", observation.id, tuple(sorted(metadata.items()))),
        kind=EntityKind.DATABASE_OPERATION,
        name=name,
        qualified_name=observation.path + "::database:" + name,
        location=observation.location,
        parent_id=observation.owner_entity_id,
        language=observation.language.value,
        metadata=tuple(sorted(metadata.items())),
    )


def _database_edge(observation: DatabaseOperationObservation, entity: CodeEntity) -> Relationship | None:
    effect = dict(observation.metadata)["effect_stage"]
    kind = None
    if observation.operation_kind is DatabaseOperationKind.READ and effect in (
        "read_capable",
        "statement_execution",
        "client_request",
    ):
        kind = RelationshipKind.READS_DATABASE
    elif observation.operation_kind in (DatabaseOperationKind.WRITE, DatabaseOperationKind.DELETE) and effect in (
        "statement_execution",
        "client_request",
    ):
        kind = RelationshipKind.WRITES_DATABASE
    if kind is None:
        return None
    proof = Evidence(
        _identity("arctrellis-database-evidence-v1", entity.id, entity.metadata),
        observation.location,
        dict(observation.metadata)["analysis_method"],
        entity.metadata,
    )
    return Relationship(
        _identity("arctrellis-database-edge-v1", observation.owner_entity_id, kind.value, entity.id, proof.id),
        observation.owner_entity_id,
        kind,
        entity.id,
        Confidence.LIKELY,
        0.85,
        (proof,),
    )


@dataclass(frozen=True, slots=True)
class DatabaseGraphResult:
    """Frozen records owning an ordinary mutable graph; treat it as a snapshot."""

    graph: CodeGraph
    observations: tuple[DatabaseOperationObservation, ...]
    operation_entities: tuple[CodeEntity, ...]
    relationships: tuple[Relationship, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.graph, CodeGraph):
            raise TypeError("graph must be CodeGraph")
        DatabaseAnalysisResult(self.observations)
        expected = tuple(_operation_entity(o) for o in self.observations)
        if self.operation_entities != expected:
            raise ValueError("database entities must exactly match ordered observations")
        edges = tuple(
            edge for o, e in zip(self.observations, expected, strict=True) if (edge := _database_edge(o, e)) is not None
        )
        if self.relationships != edges:
            raise ValueError("database relationships must match eligible operation effects")
        if any(not self.graph.has_entity(e.id) or self.graph.get_entity(e.id) != e for e in expected) or any(
            not self.graph.has_relationship(e.id) or self.graph.get_relationship(e.id) != e for e in edges
        ):
            raise ValueError("database result records must exist in its graph")
        if {e.id for e in self.graph.entities() if e.kind is EntityKind.DATABASE_OPERATION} != {
            e.id for e in expected
        } or {
            e.id
            for e in self.graph.relationships()
            if e.kind in (RelationshipKind.READS_DATABASE, RelationshipKind.WRITES_DATABASE)
        } != {e.id for e in edges}:
            raise ValueError("database graph cannot contain unaccounted operation facts")

    @property
    def relationship_count(self) -> int:
        return len(self.relationships)

    @property
    def operation_counts(self) -> tuple[tuple[DatabaseOperationKind, int], ...]:
        return DatabaseAnalysisResult(self.observations).operation_counts

    @property
    def provider_counts(self) -> tuple[tuple[str, int], ...]:
        return DatabaseAnalysisResult(self.observations).provider_counts

    @property
    def unmaterialized_observation_count(self) -> int:
        return len(self.observations) - len(self.operation_entities)

    @property
    def unlinked_observation_count(self) -> int:
        return len(self.observations) - len(self.relationships)

    @property
    def staged_observation_count(self) -> int:
        return sum(dict(o.metadata).get("effect_stage") == "staged_mutation" for o in self.observations)


def materialize_database_graph(
    index: RepositoryIndexResult,
    *,
    base_graph: CodeGraph | None = None,
) -> DatabaseGraphResult:
    """Copy an indexed/enriched snapshot and add only supported database capability facts."""
    from arctrellis.indexing import RepositoryIndexResult

    if not isinstance(index, RepositoryIndexResult):
        raise TypeError("index must be RepositoryIndexResult")
    replace(index)  # Revalidate its mutable graph and retained provenance, without rereading syntax.
    base = index.graph if base_graph is None else base_graph
    if not isinstance(base, CodeGraph):
        raise TypeError("base_graph must be CodeGraph")
    if any(not base.has_entity(e.id) or base.get_entity(e.id) != e for e in index.graph.entities()) or any(
        not base.has_relationship(e.id) or base.get_relationship(e.id) != e for e in index.graph.relationships()
    ):
        raise ValueError("database input must preserve the indexed snapshot")
    if any(e.kind is EntityKind.DATABASE_OPERATION for e in base.entities()) or any(
        e.kind in (RelationshipKind.READS_DATABASE, RelationshipKind.WRITES_DATABASE) for e in base.relationships()
    ):
        raise ValueError("database input cannot contain prior database materialization")
    graph = CodeGraph()
    for entity in base.entities():
        graph.add_entity(entity)
    for relationship in base.relationships():
        graph.add_relationship(relationship)
    operations = tuple(_operation_entity(o) for o in index.database_observations)
    edges = []
    for observation, entity in zip(index.database_observations, operations, strict=True):
        graph.add_entity(entity)
        edge = _database_edge(observation, entity)
        if edge is not None:
            graph.add_relationship(edge)
            edges.append(edge)
    return DatabaseGraphResult(graph, index.database_observations, operations, tuple(edges))
