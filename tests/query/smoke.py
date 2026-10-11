"""Reproducible end-to-end static query measurements; no target code executes."""

from pathlib import Path
from tempfile import TemporaryDirectory

from arctrellis.core import EntityKind
from arctrellis.core import RelationshipKind as RK
from arctrellis.query import (
    AnalysisSummary,
    QueryStatus,
    find_direct_tests_for_symbol,
    find_potentially_affected_endpoints,
    list_direct_database_callers,
    list_endpoints,
    trace_endpoint_to_database,
)
from tests.query.fixtures import MIXED, pipeline, write_repository


def print_path(path):
    print("Path ID:", path.path_id)
    print("Chain:", " -> ".join(e.name for e in path.entities))
    for edge in path.relationships:
        print("relationship_id:", edge.id)
        print("kind:", edge.kind.value)
        print("source:", edge.source_entity_id)
        print("target:", edge.target_entity_id)
        print("confidence:", edge.confidence.value, "score:", edge.confidence_score)
        for proof in edge.evidence:
            location = proof.location
            print(f"evidence: {location.file_path}:{location.start_line}-{location.end_line}")
            print("analysis_method:", proof.analysis_method)


def main():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        write_repository(root, MIXED)
        index, _, _, database = pipeline(root)
        graph = database.graph
        summary = AnalysisSummary(index.complete_file_count, index.partial_file_count, index.failed_file_count)
        before = graph.entities(), graph.relationships()
        endpoints = list_endpoints(graph, analysis_completeness=summary.completeness)
        traces = [
            trace_endpoint_to_database(graph, e.id, analysis_completeness=summary.completeness)
            for e in endpoints.entities
        ]
        direct = list_direct_database_callers(graph, analysis_completeness=summary.completeness)
        callables = [e for e in graph.entities() if e.kind in (EntityKind.FUNCTION, EntityKind.METHOD)]
        tests = [find_direct_tests_for_symbol(graph, e.id) for e in callables]
        helper = next(e for e in callables if e.name == "persist_payment")
        impact = find_potentially_affected_endpoints(graph, helper.id, analysis_completeness=summary.completeness)
        bounded = trace_endpoint_to_database(
            graph, next(e.id for e in endpoints.entities if e.name == "POST /payments"), max_depth=1
        )
        print("Indexed files:", len(index.file_results))
        print("Complete files:", index.complete_file_count)
        print("Partial files:", index.partial_file_count)
        print("Failed files:", index.failed_file_count)
        print("Endpoints:", len(endpoints.entities))
        print("Database operations:", len(database.operation_entities))
        print("TESTS relationships:", sum(e.kind is RK.TESTS for e in graph.relationships()))
        print("Endpoint-to-database paths:", sum(len(r.paths) for r in traces))
        print("Direct DB callers:", len({p.entity_ids[0] for p in direct.paths}))
        print("Direct test relationships:", sum(len(r.paths) for r in tests))
        print("Potentially affected endpoints:", len({p.entity_ids[0] for p in impact.paths}))
        print("No-known-path results:", sum(r.status is QueryStatus.NO_KNOWN_PATH for r in traces))
        print("Truncated queries:", sum(r.truncated for r in [endpoints, direct, impact, bounded, *traces, *tests]))
        print("Analysis completeness:", summary.completeness.value)
        trace = next(
            r
            for r in traces
            if r.source_entity_id == next(e.id for e in endpoints.entities if e.name == "POST /payments")
        )
        print("Verified forward trace:")
        print_path(trace.paths[0])
        print("Verified reverse impact (stored forward edges, direction=reverse):")
        print_path(impact.paths[0])
        again = pipeline(root)[3].graph
        deterministic = all(
            r.to_dict()
            == trace_endpoint_to_database(
                again, r.source_entity_id, analysis_completeness=summary.completeness
            ).to_dict()
            for r in traces
        )
        unchanged = before == (graph.entities(), graph.relationships())
        print("Deterministic:", deterministic)
        print("Graph unchanged:", unchanged)
        assert deterministic and unchanged and bounded.truncated


if __name__ == "__main__":
    main()
