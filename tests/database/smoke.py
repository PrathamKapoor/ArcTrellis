"""Measured static mixed-language extraction and evidence paths; targets never run."""

from pathlib import Path
from tempfile import TemporaryDirectory

from arctrellis.core import EntityKind
from arctrellis.core import RelationshipKind as RK
from arctrellis.database import DatabaseOperationKind
from tests.database.test_graph import PYTHON, TYPESCRIPT, pipeline


def main():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "app.py").write_text(PYTHON, encoding="utf-8")
        (root / "app.ts").write_text(TYPESCRIPT, encoding="utf-8")
        index, _, result = pipeline(root)
        assert index.is_complete
        providers = dict(result.provider_counts)
        print("SQLAlchemy observations:", providers.get("sqlalchemy", 0))
        print("Prisma observations:", providers.get("prisma", 0))
        print("Database operation entities:", len(result.operation_entities))
        print("READS_DATABASE edges:", sum(e.kind is RK.READS_DATABASE for e in result.relationships))
        print("WRITES_DATABASE edges:", sum(e.kind is RK.WRITES_DATABASE for e in result.relationships))
        print("Staged observations:", result.staged_observation_count)
        print("Unmaterialized observations:", result.unmaterialized_observation_count)
        print("Observations without database edges:", result.unlinked_observation_count)
        print("Unknown operations:", dict(result.operation_counts).get(DatabaseOperationKind.UNKNOWN, 0))
        again = pipeline(root)[2]
        deterministic = (result.graph.entities(), result.graph.relationships()) == (
            again.graph.entities(),
            again.graph.relationships(),
        )
        print("Deterministic:", deterministic)
        assert deterministic
        for path in ("app.py", "app.ts"):
            endpoint = next(
                e
                for e in result.graph.entities()
                if e.kind is EntityKind.API_ENDPOINT and e.name == "POST /payments" and e.location.file_path == path
            )
            operation = next(
                e
                for e in result.operation_entities
                if e.location.file_path == path
                and dict(e.metadata).get("effect_stage") in ("statement_execution", "client_request")
                and dict(e.metadata)["operation_kind"] == "write"
            )
            trace = result.graph.shortest_path(
                endpoint.id, operation.id, relationship_kinds=frozenset((RK.EXPOSES, RK.CALLS, RK.WRITES_DATABASE))
            )
            assert trace is not None
            print("Endpoint:", trace.entities[0].name)
            print("Handler:", trace.entities[1].name)
            print("Service:", trace.entities[2].name)
            print("Database operation:", trace.entities[-1].qualified_name)
            for edge in trace.relationships:
                source = result.graph.get_entity(edge.source_entity_id)
                target = result.graph.get_entity(edge.target_entity_id)
                print(source.name, edge.kind.value, target.name)
                print("Classification:", edge.confidence.value, "score=", edge.confidence_score)
                for evidence in edge.evidence:
                    location = evidence.location
                    print(
                        f"Evidence: {location.file_path}:{location.start_line}-{location.end_line} "
                        f"method={evidence.analysis_method}"
                    )


if __name__ == "__main__":
    main()
