"""Small explicit payment graph shared by graph tests."""

from arctrellis.core import (
    CodeEntity, Confidence, EntityKind, Evidence, Relationship, RelationshipKind,
    SourceLocation,
)
from arctrellis.graph import CodeGraph


def entity(entity_id: str, kind: EntityKind = EntityKind.FUNCTION) -> CodeEntity:
    return CodeEntity(entity_id, kind, entity_id, entity_id)


def relationship(
    edge_id: str, source: str, target: str,
    kind: RelationshipKind = RelationshipKind.CALLS,
) -> Relationship:
    evidence = Evidence(
        f"evidence-{edge_id}", SourceLocation("src/payments.ts", 61, 61),
        "direct_call_resolution",
    )
    return Relationship(edge_id, source, kind, target, Confidence.PROVEN, 1.0, (evidence,))


def build_graph(
    entities: tuple[CodeEntity, ...], relationships: tuple[Relationship, ...],
) -> CodeGraph:
    graph = CodeGraph()
    for record in entities:
        graph.add_entity(record)
    for record in relationships:
        graph.add_relationship(record)
    return graph


def payment_graph(reverse_insertion: bool = False) -> CodeGraph:
    entities = (
        CodeEntity("endpoint", EntityKind.API_ENDPOINT, "POST /payments", "POST /payments"),
        CodeEntity("controller", EntityKind.METHOD, "create", "PaymentController.create"),
        CodeEntity("service", EntityKind.METHOD, "create", "PaymentService.create"),
        CodeEntity("fraud", EntityKind.METHOD, "check", "FraudDetector.check"),
        CodeEntity("repository", EntityKind.METHOD, "save", "PaymentRepository.save"),
        CodeEntity("payment", EntityKind.DATABASE_OPERATION, "Payment", "Payment"),
        entity("isolated", EntityKind.MODULE),
    )
    edges = (
        relationship("expose", "endpoint", "controller", RelationshipKind.EXPOSES),
        relationship("controller-call", "controller", "service"),
        relationship("fraud-call", "service", "fraud"),
        relationship("repository-call", "service", "repository"),
        relationship("write", "repository", "payment", RelationshipKind.WRITES_DATABASE),
        relationship("import", "controller", "fraud", RelationshipKind.IMPORTS),
    )
    if reverse_insertion:
        entities, edges = entities[::-1], edges[::-1]
    return build_graph(entities, edges)


def ids(records: tuple) -> tuple[str, ...]:
    return tuple(record.id for record in records)
