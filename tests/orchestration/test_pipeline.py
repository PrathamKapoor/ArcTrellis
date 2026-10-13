"""Full analysis orchestration: real stage order, snapshot and partial behaviour."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from arctrellis.core import EntityKind, RelationshipKind
from arctrellis.indexing import index_repository
from arctrellis.ingestion import InvalidRepositoryPathError, RepositoryAccessError
from arctrellis.orchestration import (
    AnalysisCounts,
    AnalysisSnapshot,
    OrchestrationInvariantError,
    QueryIntent,
    QueryRequest,
    analyze_repository,
    run_query,
)
from arctrellis.query import AnalysisCompleteness

from .repository import MIXED, PARTIAL_SOURCE, PLAIN_SOURCE, analyze, write_sources


class EmptyRepositoryTests(unittest.TestCase):
    def test_empty_repository_produces_an_empty_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            snapshot = analyze_repository(Path(raw))
        self.assertEqual(snapshot.counts.entity_count, 0)
        self.assertEqual(snapshot.counts.relationship_count, 0)
        self.assertEqual(snapshot.retrieval.document_count, 0)
        self.assertTrue(snapshot.counts.fully_analyzed)
        self.assertEqual(snapshot.documents(), ())

    def test_missing_path_is_rejected_by_existing_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            missing = Path(raw) / "absent"
            with self.assertRaises((InvalidRepositoryPathError, RepositoryAccessError, FileNotFoundError)):
                analyze_repository(missing)

    def test_file_instead_of_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "a.txt"
            target.write_text("x", encoding="utf-8")
            with self.assertRaises((InvalidRepositoryPathError, RepositoryAccessError)):
                analyze_repository(target)


class SnapshotContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls._temporary.name)
        write_sources(cls.root, MIXED)
        cls.snapshot = analyze_repository(cls.root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_counts_are_measured_from_the_final_graph(self) -> None:
        counts = self.snapshot.counts
        entities = self.snapshot.graph.entities()
        self.assertEqual(counts.entity_count, len(entities))
        self.assertEqual(counts.relationship_count, self.snapshot.graph.relationship_count)
        self.assertEqual(counts.endpoint_count, sum(1 for e in entities if e.kind is EntityKind.API_ENDPOINT))
        self.assertEqual(counts.test_count, sum(1 for e in entities if e.kind is EntityKind.TEST))
        self.assertEqual(
            counts.database_operation_count,
            sum(1 for e in entities if e.kind is EntityKind.DATABASE_OPERATION),
        )
        self.assertEqual(counts.retrieval_document_count, self.snapshot.retrieval.document_count)
        self.assertEqual(counts.retrieval_term_count, self.snapshot.retrieval.term_count)

    def test_retrieval_index_covers_exactly_the_final_graph(self) -> None:
        self.assertEqual(
            set(self.snapshot.retrieval.documents_by_id),
            {entity.id for entity in self.snapshot.graph.entities()},
        )

    def test_snapshot_holds_the_database_and_test_enriched_graph(self) -> None:
        kinds = {relationship.kind for relationship in self.snapshot.graph.relationships()}
        self.assertIn(RelationshipKind.WRITES_DATABASE, kinds)
        self.assertIn(RelationshipKind.READS_DATABASE, kinds)
        self.assertIn(RelationshipKind.TESTS, kinds)
        self.assertIn(RelationshipKind.EXPOSES, kinds)

    def test_completeness_derives_from_indexed_file_outcomes(self) -> None:
        index = index_repository(self.root)
        self.assertIs(self.snapshot.analysis_completeness, AnalysisCompleteness.COMPLETE)
        self.assertEqual(self.snapshot.counts.complete_file_count, index.complete_file_count)
        self.assertEqual(self.snapshot.counts.partial_file_count, index.partial_file_count)
        self.assertEqual(self.snapshot.counts.failed_file_count, index.failed_file_count)

    def test_snapshot_identity_is_a_content_digest_not_a_revision(self) -> None:
        again = analyze_repository(self.root)
        self.assertEqual(again.snapshot_id, self.snapshot.snapshot_id)

    def test_snapshot_lookups_are_sorted_and_exhaustive(self) -> None:
        for name in self.snapshot.entities_with_qualified_name("payments.py::createPayment"):
            self.assertIsNotNone(self.snapshot.document(name))
        self.assertEqual(self.snapshot.entities_with_qualified_name("absent"), ())
        self.assertEqual(self.snapshot.entities_with_route("GET", "/absent"), ())
        routes = self.snapshot.entities_with_route("POST", "/payments")
        self.assertEqual(list(routes), sorted(routes))

    def test_snapshot_dict_is_json_serializable(self) -> None:
        payload = self.snapshot.to_dict()
        json.dumps(payload)
        self.assertEqual(payload["snapshot_id"], self.snapshot.snapshot_id)
        self.assertEqual(payload["counts"]["entity_count"], self.snapshot.counts.entity_count)

    def test_snapshot_rejects_a_retrieval_index_from_another_graph(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            other = analyze(Path(raw), PLAIN_SOURCE)
        with self.assertRaises(OrchestrationInvariantError):
            AnalysisSnapshot(
                counts=self.snapshot.counts,
                analysis_completeness=self.snapshot.analysis_completeness,
                graph=self.snapshot.graph,
                retrieval=other.retrieval,
            )

    def test_snapshot_counts_reject_negative_values(self) -> None:
        with self.assertRaises(OrchestrationInvariantError):
            AnalysisCounts(
                supported_file_count=-1,
                complete_file_count=0,
                partial_file_count=0,
                failed_file_count=0,
                entity_count=0,
                relationship_count=0,
                endpoint_count=0,
                test_count=0,
                database_operation_count=0,
                retrieval_document_count=0,
                retrieval_term_count=0,
            )


class PartialAnalysisTests(unittest.TestCase):
    def test_partial_file_is_reported_and_completeness_is_not_complete(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            snapshot = analyze(Path(raw), PARTIAL_SOURCE)
        self.assertGreater(snapshot.counts.partial_file_count, 0)
        self.assertFalse(snapshot.counts.fully_analyzed)
        self.assertIsNot(snapshot.analysis_completeness, AnalysisCompleteness.COMPLETE)
        self.assertGreater(snapshot.counts.complete_file_count, 0, "the good file must still be analyzed")

    def test_failed_file_is_counted_not_hidden(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            root.joinpath("broken.py").write_bytes(b"\xff\xfe\x00\x00def (\n")
            snapshot = analyze_repository(root)
        self.assertGreaterEqual(snapshot.counts.partial_file_count + snapshot.counts.failed_file_count, 1)
        self.assertIsNot(snapshot.analysis_completeness, AnalysisCompleteness.COMPLETE)

    def test_partial_analysis_still_builds_a_usable_retrieval_index(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            snapshot = analyze(Path(raw), PARTIAL_SOURCE)
        self.assertGreater(snapshot.retrieval.document_count, 0)
        bundle = run_query(snapshot, QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="goodFunction"))
        self.assertTrue(bundle.search_hits)


class ReproducibilityTests(unittest.TestCase):
    def test_two_analyses_of_equal_content_are_equal(self) -> None:
        payloads = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as raw:
                snapshot = analyze(Path(raw), MIXED)
                payloads.append(json.dumps(snapshot.to_dict(), sort_keys=True))
        self.assertEqual(payloads[0], payloads[1])

    def test_two_runs_over_one_snapshot_are_equal(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            snapshot = analyze(Path(raw), MIXED)
            endpoint = next(
                identifier
                for identifier in snapshot.entities_with_route("POST", "/payments")
                if snapshot.document(identifier).repository_relative_path == "app.py"  # type: ignore[union-attr]
            )
            request = QueryRequest(intent=QueryIntent.TRACE_ENDPOINT_TO_DATABASE, entity_id=endpoint)
            first = json.dumps(run_query(snapshot, request).to_dict(), sort_keys=True)
            second = json.dumps(run_query(snapshot, request).to_dict(), sort_keys=True)
        self.assertEqual(first, second)

    def test_analysis_does_not_touch_the_target_repository_except_for_reads(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            write_sources(root, MIXED)
            before = {path: path.stat().st_mtime_ns for path in sorted(root.rglob("*")) if path.is_file()}
            analyze_repository(root)
            after = {path: path.stat().st_mtime_ns for path in sorted(root.rglob("*")) if path.is_file()}
        self.assertEqual(before, after)
        self.assertTrue(before)


class EmptyGraphQueryTests(unittest.TestCase):
    def test_structural_query_on_an_empty_repository_reports_no_known_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            snapshot = analyze_repository(Path(raw))
        bundle = run_query(snapshot, QueryRequest(intent=QueryIntent.LIST_ENDPOINTS))
        self.assertEqual(bundle.status.value, "NO_KNOWN_PATH")
        json.dumps(bundle.to_dict())

    def test_search_on_an_empty_repository_is_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            snapshot = analyze_repository(Path(raw))
        bundle = run_query(snapshot, QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="anything"))
        self.assertEqual(bundle.selection.status.value, "NOT_FOUND")
        json.dumps(bundle.to_dict())


if __name__ == "__main__":
    unittest.main()
