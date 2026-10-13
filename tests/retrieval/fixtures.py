"""Small canonical unit graphs as untrusted static records; never executed or imported."""

from arctrellis.core import (
    CodeEntity,
    Confidence,
    EntityKind,
    Evidence,
    Relationship,
    RelationshipKind,
    SourceLocation,
)
from arctrellis.graph import CodeGraph


def entity(
    identifier,
    kind,
    name,
    qualified_name,
    *,
    path=None,
    start=None,
    end=None,
    language=None,
    parent_id=None,
    metadata=(),
    signature=None,
):
    location = None if path is None else SourceLocation(path, start or 1, end if end is not None else (start or 1))
    return CodeEntity(
        identifier,
        kind,
        name,
        qualified_name,
        location=location,
        parent_id=parent_id,
        language=language,
        metadata=metadata,
        signature=signature,
    )


def edge(identifier, source_id, kind, target_id, *, confidence=Confidence.LIKELY, score=0.85, evidence=()):
    return Relationship(identifier, source_id, kind, target_id, confidence, score, tuple(evidence))


def proof(identifier, path, start, method, metadata=()):
    return Evidence(identifier, SourceLocation(path, start, start), method, metadata)


def empty_graph():
    return CodeGraph()


def payment_graph(*, extra_entities=(), extra_edges=()):
    """FastAPI/SQLAlchemy style unit graph used by scoring and context tests."""
    graph = CodeGraph()
    records = (
        entity(
            "module:app",
            EntityKind.MODULE,
            "app",
            "app.py",
            path="app.py",
            language="python",
        ),
        entity(
            "endpoint:post-payments",
            EntityKind.API_ENDPOINT,
            "POST /payments",
            "app.py::endpoint:POST /payments",
            path="app.py",
            start=4,
            end=5,
            language="python",
            metadata=(
                ("framework", "fastapi"),
                ("http_method", "POST"),
                ("route_path", "/payments"),
                ("path_completeness", "local"),
            ),
        ),
        entity(
            "endpoint:get-users-id",
            EntityKind.API_ENDPOINT,
            "GET /users/{id}",
            "users.py::endpoint:GET /users/{id}",
            path="users.py",
            start=2,
            end=3,
            language="python",
            metadata=(
                ("framework", "fastapi"),
                ("http_method", "GET"),
                ("route_path", "/users/{id}"),
                ("path_completeness", "local"),
            ),
        ),
        entity(
            "class:PaymentService",
            EntityKind.CLASS,
            "PaymentService",
            "payments.py::PaymentService",
            path="payments.py",
            start=3,
            end=20,
            language="python",
        ),
        entity(
            "function:createPayment",
            EntityKind.FUNCTION,
            "createPayment",
            "payments.py::createPayment",
            path="payments.py",
            start=6,
            end=8,
            language="python",
            parent_id="class:PaymentService",
        ),
        entity(
            "function:deletePayment",
            EntityKind.FUNCTION,
            "deletePayment",
            "payments.py::deletePayment",
            path="payments.py",
            start=22,
            end=24,
            language="python",
            parent_id="class:PaymentService",
        ),
        entity(
            "db:insert",
            EntityKind.DATABASE_OPERATION,
            "sqlalchemy:Payment.execute@121",
            "payments.py::database:sqlalchemy:Payment.execute@121",
            path="payments.py",
            start=121,
            language="python",
            parent_id="function:createPayment",
            metadata=(
                ("provider", "sqlalchemy"),
                ("operation_kind", "write"),
                ("operation_name", "execute"),
                ("target_name", "Payment"),
                ("effect_stage", "statement_execution"),
            ),
        ),
        entity(
            "test:create-payment",
            EntityKind.TEST,
            "test_create_payment",
            "test_payments.py::test:test_create_payment",
            path="test_payments.py",
            start=3,
            end=5,
            language="python",
            metadata=(("framework", "pytest_naming_convention"),),
        ),
        entity(
            "import:persist",
            EntityKind.IMPORT,
            "persist_payment",
            "payments.py::import:persist_payment",
            path="payments.py",
            start=1,
            language="python",
            metadata=(
                ("import_form", "from"),
                ("module", "payments"),
                ("imported_name", "persist_payment"),
                ("binding", "persist_payment"),
            ),
        ),
    ) + tuple(extra_entities)
    for record in records:
        graph.add_entity(record)
    relationships = (
        edge(
            "rel:exposes",
            "endpoint:post-payments",
            RelationshipKind.EXPOSES,
            "function:createPayment",
            confidence=Confidence.PROVEN,
            score=1.0,
            evidence=(proof("ev:exposes", "app.py", 4, "fastapi_decorated_handler"),),
        ),
        edge(
            "rel:tests",
            "test:create-payment",
            RelationshipKind.TESTS,
            "function:createPayment",
            evidence=(proof("ev:tests", "test_payments.py", 4, "python_test_body_call"),),
        ),
        edge(
            "rel:defines",
            "module:app",
            RelationshipKind.DEFINES,
            "endpoint:post-payments",
            confidence=Confidence.PROVEN,
            score=1.0,
        ),
        edge(
            "rel:imports",
            "module:app",
            RelationshipKind.IMPORTS,
            "import:persist",
            confidence=Confidence.PROVEN,
            score=1.0,
        ),
    ) + tuple(extra_edges)
    for relationship in relationships:
        graph.add_relationship(relationship)
    return graph


def synthetic_graph(entity_count, *, degree=3):
    """Deterministic many-entity graph for functional budget checks."""
    graph = CodeGraph()
    graph.add_entity(
        entity(
            "synthetic:module", EntityKind.MODULE, "synthetic", "synthetic.py", path="synthetic.py", language="python"
        )
    )
    for number in range(entity_count):
        graph.add_entity(
            entity(
                f"synthetic:function:{number:05d}",
                EntityKind.FUNCTION,
                f"paymentService{number:05d}",
                f"synthetic.py::paymentService{number:05d}",
                path="synthetic.py",
                start=number + 1,
                language="python",
                metadata=(("framework", "fastapi"), ("http_method", "POST"), ("route_path", f"/payments/{number}")),
            )
        )
    for number in range(entity_count):
        source = f"synthetic:function:{number:05d}"
        for offset in range(min(degree, entity_count)):
            target = f"synthetic:function:{(number + offset + 1) % entity_count:05d}"
            if target != source:
                graph.add_relationship(
                    edge(f"synthetic:rel:{number:05d}:{offset}", source, RelationshipKind.CALLS, target)
                )
    return graph
