"""Repeatable static smoke; synthetic target files are never executed."""

from arctrellis.core import RelationshipKind
from tests.test_semantics.test_analysis import analyze


def main() -> None:
    sources = {
        "service.py": "def create_payment():\n    return True\n",
        "test_service.py": (
            "from service import create_payment\ndef test_create_payment():\n    assert create_payment()\n"
        ),
        "service.js": "export function validate() { return true; }\n",
        "service.test.js": 'import { validate } from "./service";\ntest("validates", () => {\n    validate();\n});\n',
    }
    result = analyze(sources)[2]
    print(f"Test observations: {len(result.observations)}")
    print(f"Test entities: {result.test_count}")
    print(f"Linked tests: {result.linked_test_count}")
    print(f"Unlinked tests: {result.unlinked_test_count}")
    print(f"TESTS edges: {result.resolved_test_relationship_count}")
    for edge in result.graph.relationships():
        if edge.kind is not RelationshipKind.TESTS:
            continue
        print(result.graph.get_entity(edge.source_entity_id).qualified_name)
        print("    TESTS")
        print(result.graph.get_entity(edge.target_entity_id).qualified_name)
        for proof in edge.evidence:
            print(f"Evidence: {proof.location.file_path}:{proof.location.start_line}-{proof.location.end_line}")
            print(f"method={proof.analysis_method}")
            print(f"classification={edge.confidence.value}")
            print(f"score={edge.confidence_score}")
    rerun = analyze(sources)[2]
    print(f"Deterministic: {result.graph.relationships() == rerun.graph.relationships()}")


if __name__ == "__main__":
    main()
