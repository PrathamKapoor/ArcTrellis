"""Bounded behaviour on a large, ambiguous, cyclic and high-degree repository.

These tests assert bounds, statuses and determinism, never wall-clock timing. A
repository that grows by a factor changes the measured sizes but must not change
any contract.
"""

from __future__ import annotations

import json
import tempfile
import unittest
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
from tests.scale.fixtures import build_large_repository


class LargeRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls._temporary.name)
        for name, text in build_large_repository().items():
            path = cls.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        cls.snapshot = analyze_repository(cls.root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def run_request(self, **kwargs):
        intent = kwargs.pop("intent")
        return run_query(self.snapshot, QueryRequest(intent=intent, **kwargs))

    def qualified_name(self, name: str) -> str:
        return f"mod000.py::{name}"

    def test_the_fixture_is_actually_large(self) -> None:
        self.assertGreater(self.snapshot.counts.entity_count, 900)
        self.assertGreater(self.snapshot.counts.relationship_count, 900)
        self.assertGreater(self.snapshot.retrieval.document_count, 900)

    def test_repeated_function_names_stay_ambiguous(self) -> None:
        matches = self.snapshot.entities_with_qualified_name(self.qualified_name("handler0"))
        self.assertEqual(len(matches), 1, "the fixture repeats names across modules, not within one")
        bundle = self.run_request(intent=QueryIntent.FIND_CALLERS, qualified_name=self.qualified_name("handler0"))
        self.assertIn(bundle.status, (BundleStatus.EVIDENCE_PATHS, BundleStatus.NO_KNOWN_PATH))

    def test_the_same_name_in_many_modules_is_lexically_ambiguous(self) -> None:
        bundle = self.run_request(intent=QueryIntent.SEARCH_ENTITIES, search_text="handler1", top_k=50)
        self.assertIs(bundle.selection.status, SelectionStatus.CANDIDATES)
        names = {candidate.name for candidate in bundle.candidate_entities}
        self.assertEqual(names, {"handler1"})
        paths = {candidate.repository_relative_path for candidate in bundle.candidate_entities}
        self.assertGreater(len(paths), 1, "the same name must exist in many modules")
        self.assertIsNone(bundle.selected_entity)

    def test_repeated_endpoint_registrations_are_ambiguous(self) -> None:
        matches = self.snapshot.entities_with_route("POST", "/payments")
        self.assertGreater(len(matches), 1)
        bundle = self.run_request(
            intent=QueryIntent.TRACE_ENDPOINT_TO_DATABASE, http_method="POST", route_path="/payments"
        )
        self.assertIs(bundle.status, BundleStatus.AMBIGUOUS_SOURCE)
        self.assertIsNone(bundle.selected_entity)
        candidates = [candidate.entity_id for candidate in bundle.candidate_entities]
        self.assertEqual(candidates, sorted(matches[: len(candidates)]))
        self.assertLessEqual(len(candidates), 25, "candidate output must stay bounded")
        self.assertEqual(
            bundle.selection.truncated,
            len(matches) > len(candidates),
            "a bounded candidate list must report that it is bounded",
        )

    def test_high_degree_traversal_respects_the_path_budget(self) -> None:
        hub = next(
            document.entity_id
            for document in self.snapshot.documents()
            if document.name == "hub" and document.qualified_name == "scale/hub.py::hub"
        )
        bounded = self.run_request(intent=QueryIntent.FIND_CALLERS, entity_id=hub, max_paths=5)
        unbounded = self.run_request(intent=QueryIntent.FIND_CALLERS, entity_id=hub, max_paths=200)
        self.assertLessEqual(len(bounded.paths), 5)
        self.assertGreater(len(unbounded.paths), len(bounded.paths))
        self.assertIn("max_paths", bounded.graph_truncation)
        self.assertIn("structural_query_budget_truncated_enumeration", bounded.limitations)
        self.assertEqual(bounded.graph_truncation, ("max_paths",))

    def test_cycles_terminate_within_the_depth_budget(self) -> None:
        node = next(
            document.entity_id
            for document in self.snapshot.documents()
            if document.name == "node0" and document.qualified_name == "scale/cycle.py::node0"
        )
        bundle = self.run_request(intent=QueryIntent.FIND_CALLERS, entity_id=node, max_depth=3)
        self.assertIn(bundle.status, (BundleStatus.EVIDENCE_PATHS, BundleStatus.NO_KNOWN_PATH))
        for path in bundle.paths:
            self.assertLessEqual(len(path.relationships), 3)

    def test_retrieval_budget_bounds_reported_candidates(self) -> None:
        bounded = self.run_request(
            intent=QueryIntent.SEARCH_ENTITIES, search_text="handler", top_k=100, max_examined_postings=5
        )
        unbounded = self.run_request(intent=QueryIntent.SEARCH_ENTITIES, search_text="handler", top_k=100)
        self.assertTrue(bounded.retrieval_truncation)
        self.assertTrue(bounded.truncated)
        self.assertGreater(len(unbounded.search_hits), len(bounded.search_hits))
        self.assertIn("retrieval_budget_truncated_candidate_examination", bounded.limitations)

    def test_top_k_bounds_the_reported_result(self) -> None:
        for limit in (1, 5, 25):
            with self.subTest(limit=limit):
                bundle = self.run_request(intent=QueryIntent.SEARCH_ENTITIES, search_text="handler", top_k=limit)
                self.assertLessEqual(len(bundle.search_hits), limit)

    def test_every_bundle_stays_within_a_bounded_json_size(self) -> None:
        requests = (
            {"intent": QueryIntent.SEARCH_ENTITIES, "search_text": "handler", "top_k": 100},
            {"intent": QueryIntent.LIST_ENDPOINTS},
            {"intent": QueryIntent.LIST_DATABASE_CALLERS},
            {
                "intent": QueryIntent.TRACE_ENDPOINT_TO_DATABASE,
                "http_method": "POST",
                "route_path": "/payments",
            },
            {"intent": QueryIntent.FIND_AFFECTED_ENDPOINTS, "qualified_name": "mod000.py::handler0"},
        )
        for request in requests:
            with self.subTest(intent=request["intent"]):
                bundle = run_query(self.snapshot, QueryRequest(**request))
                serialized = json.dumps(bundle.to_dict())
                self.assertLess(len(serialized), 8 * 1024 * 1024, "a bundle must stay bounded")
                self.assertLessEqual(len(bundle.paths), 200)

    def test_results_are_deterministic_across_repeated_runs(self) -> None:
        request = QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="handler", top_k=40)
        first = json.dumps(run_query(self.snapshot, request).to_dict(), sort_keys=True)
        second = json.dumps(run_query(self.snapshot, request).to_dict(), sort_keys=True)
        self.assertEqual(first, second)

    def test_analysis_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            other = Path(raw)
            for name, text in build_large_repository().items():
                path = other / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            second = analyze_repository(other)
        self.assertEqual(second.snapshot_id, self.snapshot.snapshot_id)
        self.assertEqual(second.counts, self.snapshot.counts)

    def test_queries_do_not_mutate_the_snapshot(self) -> None:
        before = (
            len(self.snapshot.graph.entities()),
            self.snapshot.graph.relationship_count,
            self.snapshot.snapshot_id,
        )
        for request in (
            QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="handler", top_k=50),
            QueryRequest(intent=QueryIntent.LIST_ENDPOINTS),
            QueryRequest(intent=QueryIntent.LIST_DATABASE_CALLERS),
            QueryRequest(intent=QueryIntent.TRACE_ENDPOINT_TO_DATABASE, http_method="POST", route_path="/payments"),
        ):
            run_query(self.snapshot, request)
        self.assertEqual(
            (len(self.snapshot.graph.entities()), self.snapshot.graph.relationship_count, self.snapshot.snapshot_id),
            before,
        )

    def test_invalid_requests_fail_the_same_way_at_scale(self) -> None:
        from arctrellis.orchestration import InvalidQueryLimitError, UnsupportedIntentError

        with self.assertRaises(InvalidQueryLimitError):
            QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="handler", top_k=0)
        with self.assertRaises(UnsupportedIntentError):
            QueryRequest(
                intent=QueryIntent.TRACE_ENDPOINT_TO_DATABASE,
                entity_id="x",
                include_graph_context=True,
            )
        self.assertIsNot(self.snapshot.analysis_completeness.value, "unknown")

    def test_unknown_entities_stay_not_found_at_scale(self) -> None:
        bundle = self.run_request(intent=QueryIntent.FIND_CALLERS, entity_id="00000000-0000-0000-0000-000000000000")
        self.assertIs(bundle.status, BundleStatus.NOT_FOUND_SOURCE)
        self.assertEqual(bundle.paths, ())

    def test_no_bundle_discloses_an_absolute_path(self) -> None:
        for request in (
            QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="handler", top_k=100),
            QueryRequest(intent=QueryIntent.LIST_ENDPOINTS),
            QueryRequest(intent=QueryIntent.LIST_DATABASE_CALLERS),
        ):
            serialized = json.dumps(run_query(self.snapshot, request).to_dict())
            self.assertNotIn(str(self.root), serialized)
            self.assertNotIn(":\\", serialized)

    def test_every_language_in_the_fixture_is_analyzed(self) -> None:
        languages = {document.language for document in self.snapshot.documents() if document.language is not None}
        self.assertEqual(languages, {"python", "javascript"})
        self.assertGreater(
            sum(1 for document in self.snapshot.documents() if document.entity_kind is EntityKind.FUNCTION),
            800,
        )


if __name__ == "__main__":
    unittest.main()
