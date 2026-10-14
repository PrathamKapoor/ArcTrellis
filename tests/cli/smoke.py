"""Mandatory full-product smoke: analyze, snapshot, query, bundle, CLI equivalence.

Run with `.venv\\Scripts\\python.exe -m tests.cli.smoke`. Every printed value is
measured from the run; nothing is asserted or formatted from an expectation. The
script fails loudly if the programmatic result and the CLI result disagree on
canonical evidence.
"""

from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path

from arctrellis.core import EntityKind
from arctrellis.orchestration import (
    BundleStatus,
    QueryIntent,
    QueryRequest,
    SelectionStatus,
    analyze_repository,
    run_query,
)
from tests.orchestration.repository import MIXED, write_sources

TRACE = QueryIntent.TRACE_ENDPOINT_TO_DATABASE


def _cli(*argv: str) -> tuple[int, str, str]:
    from arctrellis.cli.main import main

    out, err = io.StringIO(), io.StringIO()
    try:
        status = main(list(argv), stdout=out, stderr=err)
    except SystemExit as exit_request:
        code = exit_request.code
        status = 0 if code is None else code if isinstance(code, int) else 2
    return status, out.getvalue(), err.getvalue()


def _selection_counts(bundles: list) -> tuple[int, int, int]:
    resolved = sum(1 for bundle in bundles if bundle.selection.status is SelectionStatus.RESOLVED)
    ambiguous = sum(1 for bundle in bundles if bundle.selection.status is SelectionStatus.AMBIGUOUS)
    not_found = sum(1 for bundle in bundles if bundle.selection.status is SelectionStatus.NOT_FOUND)
    return resolved, ambiguous, not_found


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        write_sources(root, MIXED)

        snapshot = analyze_repository(root)
        counts = snapshot.counts
        print("Indexed support files:", counts.supported_file_count)
        print("Complete files:", counts.complete_file_count)
        print("Partial files:", counts.partial_file_count)
        print("Failed files:", counts.failed_file_count)
        print("Entities:", counts.entity_count)
        print("Relationships:", counts.relationship_count)
        print("Endpoints:", counts.endpoint_count)
        print("Tests:", counts.test_count)
        print("Database operations:", counts.database_operation_count)
        print("Retrieval documents:", counts.retrieval_document_count)
        print("Retrieval terms:", counts.retrieval_term_count)
        print("Analysis completeness:", snapshot.analysis_completeness.value)
        print("Snapshot id:", snapshot.snapshot_id)

        # One endpoint registration per (method, path, file) so the Python and the
        # JavaScript registration of POST /payments are never confused.
        def endpoint_id(file_name: str) -> str:
            document = next(
                item
                for item in snapshot.documents()
                if item.entity_kind is EntityKind.API_ENDPOINT
                and item.repository_relative_path == file_name
                and item.field_value("route_path") == "/payments"
                and item.field_value("http_method") == "POST"
            )
            return document.entity_id

        python_endpoint = endpoint_id("app.py")
        callable_id = next(
            document.entity_id
            for document in snapshot.documents()
            if document.qualified_name == "payments.py::createPayment"
        )

        requests = [
            QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="list payments"),
            QueryRequest(intent=QueryIntent.LIST_ENDPOINTS, http_method="POST"),
            QueryRequest(intent=QueryIntent.LIST_DATABASE_CALLERS),
            QueryRequest(intent=TRACE, entity_id=python_endpoint),
            QueryRequest(intent=QueryIntent.TRACE_CALLABLE_TO_DATABASE, entity_id=callable_id),
            QueryRequest(intent=QueryIntent.DIRECT_DATABASE_OPERATIONS, entity_id=callable_id),
            QueryRequest(intent=QueryIntent.FIND_DIRECT_TESTS, entity_id=callable_id),
            QueryRequest(intent=QueryIntent.FIND_CALLERS, entity_id=callable_id),
            QueryRequest(intent=QueryIntent.FIND_AFFECTED_ENDPOINTS, entity_id=callable_id),
            QueryRequest(intent=TRACE, http_method="POST", route_path="/payments"),
            QueryRequest(intent=TRACE, http_method="GET", route_path="/reports"),
            QueryRequest(intent=TRACE, entity_id="00000000-0000-0000-0000-000000000000"),
            QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="payment", max_examined_postings=1),
        ]
        bundles = [run_query(snapshot, request) for request in requests]
        resolved, ambiguous, not_found = _selection_counts(bundles)
        print("Query requests:", len(requests))
        print("Resolved selections:", resolved)
        print("Ambiguous selections:", ambiguous)
        print("Not-found selections:", not_found)
        print("Evidence bundles:", len(bundles))
        print("Bundles with evidence paths:", sum(1 for b in bundles if b.status is BundleStatus.EVIDENCE_PATHS))
        print("No-known-path bundles:", sum(1 for b in bundles if b.status is BundleStatus.NO_KNOWN_PATH))
        print("Inventory bundles:", sum(1 for b in bundles if b.status is BundleStatus.INVENTORY))
        print("Search bundles:", sum(1 for b in bundles if b.status is BundleStatus.SEARCH_RESULTS))
        print("Truncated results:", sum(1 for b in bundles if b.truncated))
        print("JSON-serializable bundles:", sum(1 for b in bundles if json.dumps(b.to_dict())))

        trace_bundle = bundles[3]
        print()
        print("Source endpoint: POST /payments [app.py]")
        print(
            "Selected canonical ID:", trace_bundle.selected_entity.entity_id if trace_bundle.selected_entity else None
        )
        assert trace_bundle.status is BundleStatus.EVIDENCE_PATHS, trace_bundle.status
        path = trace_bundle.paths[0]
        for index, relationship in enumerate(path.relationships):
            print()
            print(f"{relationship.relationship_kind} edge:")
            print("  relationship ID:", relationship.relationship_id)
            print("  source:", path.entities[index].entity_id, path.entities[index].name)
            print("  target:", path.entities[index + 1].entity_id, path.entities[index + 1].name)
            for detail in relationship.evidence:
                print(
                    "  evidence:",
                    detail.analysis_method,
                    detail.file_path,
                    f"lines {detail.start_line}-{detail.end_line}",
                )
            print("  confidence:", relationship.confidence, relationship.confidence_score)
        print()
        print("Analysis completeness:", trace_bundle.analysis_completeness.value)
        print("Query limits:", json.dumps(trace_bundle.plan["limits"], sort_keys=True))
        print("Retrieval truncation:", trace_bundle.retrieval_truncation)
        print("Query truncation:", trace_bundle.graph_truncation)
        print("Limitations:", trace_bundle.limitations)

        # The CLI must produce the same canonical evidence for the same request.
        status, out, err = _cli("trace", str(root), "--entity-id", python_endpoint, "--json")
        assert status == 0, (status, err)
        cli_payload = json.loads(out)
        api_payload = trace_bundle.to_dict()
        print()
        print("CLI exit status:", status)
        print("CLI/API status agree:", cli_payload["status"] == api_payload["status"])
        print(
            "CLI/API selected entity agree:",
            cli_payload["selected_entity"]["entity_id"] == api_payload["selected_entity"]["entity_id"],
        )
        print(
            "CLI/API relationship IDs agree:",
            [[item["relationship_id"] for item in path_item["relationships"]] for path_item in cli_payload["paths"]]
            == [[item["relationship_id"] for item in path_item["relationships"]] for path_item in api_payload["paths"]],
        )
        assert cli_payload["status"] == api_payload["status"]
        assert cli_payload["paths"] == api_payload["paths"]

        # Determinism: the same request over the same snapshot twice.
        again = run_query(snapshot, requests[3]).to_dict()
        print("Deterministic rerun:", json.dumps(again, sort_keys=True) == json.dumps(api_payload, sort_keys=True))
        assert json.dumps(again, sort_keys=True) == json.dumps(api_payload, sort_keys=True)

        # Ambiguity must be visible through the CLI with a distinct status.
        ambiguous_status, ambiguous_out, ambiguous_err = _cli(
            "query",
            str(root),
            "--intent",
            "trace-endpoint-to-database",
            "--method",
            "POST",
            "--path",
            "/payments",
            "--json",
        )
        print("CLI ambiguous exit status:", ambiguous_status)
        print("CLI ambiguous stdout is JSON:", json.loads(ambiguous_out)["status"] == "AMBIGUOUS_SOURCE")
        print("CLI ambiguous stderr explains:", "supply --entity-id" in ambiguous_err)
        assert ambiguous_status == 3

        # The graph must be unchanged by all of the above.
        after = analyze_repository(root)
        print("Graph unchanged:", after.counts == counts and after.snapshot_id == snapshot.snapshot_id)
        assert after.snapshot_id == snapshot.snapshot_id
        assert after.counts == counts

    print("Smoke complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
