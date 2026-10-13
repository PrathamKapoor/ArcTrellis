"""Golden retrieval evaluation against real analysis output and independent judgments."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from arctrellis.core import EntityKind
from arctrellis.retrieval import SearchFilters, build_search_index, search_endpoints, search_symbols
from arctrellis.retrieval.evaluation import (
    BASELINE,
    BM25,
    GRAPH,
    RelevanceJudgment,
    RetrievalEvaluationError,
    evaluate_retrieval,
    exact_substring_baseline,
)
from arctrellis.retrieval.evaluation import ExpectedEntity as E
from tests.retrieval.judgments import CONCEPTUAL_QUERIES, JUDGED_QUERIES, JUDGMENTS
from tests.retrieval.repository import MIXED, analysis_context, pipeline, write_repository


class GoldenRetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._directory = TemporaryDirectory()
        root = Path(cls._directory.name)
        write_repository(root, MIXED)
        index, _, _, database = pipeline(root)
        cls.completeness = analysis_context(index)
        cls.index = build_search_index(database.graph, analysis_completeness=cls.completeness)
        cls.graph = database.graph
        cls.evaluation = evaluate_retrieval(cls.index, JUDGMENTS, k=5)

    @classmethod
    def tearDownClass(cls):
        cls._directory.cleanup()

    def metric(self, mode, name):
        for evaluation in self.evaluation.metrics:
            if evaluation.metrics.mode == mode:
                return getattr(evaluation.metrics, f"{name}_at_k")
        raise AssertionError(f"missing mode {mode}")

    def outcome(self, mode, query):
        for evaluation in self.evaluation.metrics:
            if evaluation.metrics.mode != mode:
                continue
            for item in evaluation.outcomes:
                if item.query == query:
                    return item
        raise AssertionError(f"missing outcome for {mode} {query!r}")

    def test_every_judgment_selector_resolves_to_a_real_canonical_entity(self):
        self.assertEqual(self.evaluation.unresolved_judgment_labels, ())
        for judgment in JUDGMENTS:
            with self.subTest(query=judgment.query):
                resolved, missing = judgment.resolve(self.index)
                self.assertEqual(missing, ())
                if judgment.expected:
                    self.assertTrue(resolved)

    def test_unjudgeable_query_is_skipped_and_reported(self):
        unjudgeable = next(item for item in JUDGMENTS if not item.expected)
        self.assertIn(unjudgeable.query, CONCEPTUAL_QUERIES)
        for evaluation in self.evaluation.metrics:
            with self.subTest(mode=evaluation.metrics.mode):
                self.assertEqual(evaluation.metrics.skipped_queries, 1)
                self.assertEqual(evaluation.metrics.evaluated_queries, len(JUDGED_QUERIES))

    def test_measured_metrics_are_pinned_for_regression_detection(self):
        self.assertAlmostEqual(self.metric(BASELINE, "recall"), 0.8246, places=4)
        self.assertAlmostEqual(self.metric(BASELINE, "precision"), 0.3158, places=4)
        self.assertAlmostEqual(self.metric(BASELINE, "mrr"), 0.7298, places=4)
        self.assertAlmostEqual(self.metric(BASELINE, "hit_rate"), 0.8947, places=4)
        self.assertAlmostEqual(self.metric(BM25, "recall"), 0.8860, places=4)
        self.assertAlmostEqual(self.metric(BM25, "precision"), 0.3474, places=4)
        self.assertAlmostEqual(self.metric(BM25, "mrr"), 0.8070, places=4)
        self.assertAlmostEqual(self.metric(GRAPH, "recall"), 0.8860, places=4)
        self.assertAlmostEqual(self.metric(GRAPH, "precision"), 0.3211, places=4)
        self.assertAlmostEqual(self.metric(GRAPH, "mrr"), 0.8553, places=4)
        self.assertAlmostEqual(self.metric(GRAPH, "hit_rate"), 0.9474, places=4)

    def test_bm25_and_graph_context_beat_the_exact_baseline_on_measured_rr(self):
        self.assertGreater(self.metric(BM25, "mrr"), self.metric(BASELINE, "mrr"))
        self.assertGreater(self.metric(GRAPH, "mrr"), self.metric(BASELINE, "mrr"))
        self.assertGreater(self.metric(BM25, "recall"), self.metric(BASELINE, "recall"))
        self.assertGreater(self.metric(GRAPH, "recall"), self.metric(BASELINE, "recall"))
        self.assertGreater(self.metric(GRAPH, "mrr"), self.metric(BM25, "mrr"))
        self.assertGreaterEqual(self.metric(GRAPH, "recall"), self.metric(BM25, "recall"))

    def test_graph_context_improves_rank_but_not_every_metric(self):
        """Measured finding: graph context raises MRR while lowering precision."""
        self.assertGreater(self.metric(GRAPH, "mrr"), self.metric(BM25, "mrr"))
        self.assertLess(self.metric(GRAPH, "precision"), self.metric(BM25, "precision"))
        self.assertEqual(self.metric(GRAPH, "hit_rate"), self.metric(BM25, "hit_rate"))

    def test_graph_context_helps_some_queries_and_hurts_others(self):
        graph_mode = next(item for item in self.evaluation.metrics if item.metrics.mode == GRAPH)
        self.assertEqual(self.outcome(BASELINE, "payment creation").reciprocal_rank, 0.0)
        self.assertEqual(self.outcome(BM25, "payment creation").reciprocal_rank, 0.5)
        self.assertEqual(self.outcome(GRAPH, "payment creation").reciprocal_rank, 0.25)
        self.assertIn("payment creation", graph_mode.improved_over_baseline)
        self.assertIn("test payment", graph_mode.regressed_versus_baseline)
        self.assertEqual(self.outcome(BASELINE, "test payment").reciprocal_rank, 1.0)
        self.assertEqual(self.outcome(BM25, "test payment").reciprocal_rank, 0.5)
        self.assertEqual(self.outcome(GRAPH, "test payment").reciprocal_rank, 0.5)
        self.assertIsNone(self.outcome(GRAPH, "payment refund endpoint").first_relevant_rank)

    def test_repeated_evaluation_is_deterministic(self):
        again = evaluate_retrieval(self.index, JUDGMENTS, k=5)
        self.assertEqual(again.to_dict(), self.evaluation.to_dict())

    def test_rebuilding_the_index_reproduces_the_same_evaluation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_repository(root, MIXED)
            index, _, _, database = pipeline(root)
            rebuilt = build_search_index(database.graph, analysis_completeness=analysis_context(index))
            self.assertEqual(rebuilt.snapshot_id, self.index.snapshot_id)
            self.assertEqual(evaluate_retrieval(rebuilt, JUDGMENTS, k=5).to_dict(), self.evaluation.to_dict())

    def test_evaluation_payload_is_json_primitive(self):
        payload = self.evaluation.to_dict()
        self.assertEqual(json.loads(json.dumps(payload)), payload)
        self.assertEqual(payload["k"], 5)
        self.assertEqual(payload["judgment_count"], len(JUDGMENTS))
        self.assertEqual(
            sorted(payload),
            [
                "bm25_lexical",
                "bm25_with_graph_context",
                "exact_substring_baseline",
                "judgment_count",
                "k",
                "unresolved_judgment_labels",
            ],
        )

    def test_exact_symbol_queries_return_the_symbol_first(self):
        for query in ("PaymentService", "stagePayment", "auditPayment", "refundPayment", "persistPaymentRoute"):
            with self.subTest(query=query):
                result = search_symbols(self.index, query)
                self.assertEqual(result.hits[0].name, query)

    def test_reused_symbol_names_keep_distinct_identities(self):
        result = search_symbols(self.index, "persistPayment", top_k=25)
        functions = sorted(
            item
            for item in result.entity_ids()
            if self.index.document(item).entity_kind is EntityKind.FUNCTION
            and self.index.document(item).name == "persistPayment"
        )
        self.assertEqual(len(functions), 2)
        self.assertEqual(
            {self.index.document(item).repository_relative_path for item in functions},
            {"js/service.js", "ts/service.ts"},
        )

    def test_duplicate_routes_remain_distinct_results(self):
        result = search_endpoints(self.index, "POST /payments", top_k=25)
        identifiers = result.entity_ids()
        paths = [self.index.document(item).repository_relative_path for item in identifiers]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertGreaterEqual(paths.count("ts/app.ts"), 2)
        self.assertGreaterEqual(len(paths), 4)
        self.assertGreater(len(paths), len(set(paths)), "duplicate registrations must stay separate results")

    def test_framework_filtered_endpoint_query_uses_canonical_metadata(self):
        result = search_endpoints(self.index, "payments", filters=SearchFilters(frameworks=frozenset({"express"})))
        self.assertTrue(result.hits)
        for hit in result.hits:
            self.assertEqual(hit.entity_kind, EntityKind.API_ENDPOINT)
            self.assertEqual(self.index.document(hit.entity_id).field_value("framework"), "express")

    def test_database_operations_are_retrievable_by_provider_and_target(self):
        result = search_symbols(
            self.index,
            "prisma payment create",
            filters=SearchFilters(
                entity_kinds=frozenset({EntityKind.DATABASE_OPERATION}),
                providers=frozenset({"prisma"}),
            ),
            top_k=25,
        )
        self.assertEqual(len(result.hits), 4)
        operations = {self.index.document(item).field_value("operation_name") for item in result.entity_ids()}
        for hit in result.hits:
            document = self.index.document(hit.entity_id)
            self.assertEqual(document.field_value("provider"), "prisma")
            self.assertEqual(document.field_value("target_name"), hit.name.split(":", 1)[1].split(".")[0])
            self.assertIn("payment", hit.matched_terms)
        self.assertEqual(operations, {"create", "findMany"})
        self.assertEqual(
            sorted({self.index.document(item).repository_relative_path for item in result.entity_ids()}),
            ["js/app.js", "js/service.js", "ts/service.ts"],
        )

    def test_tests_are_retrievable_by_name(self):
        result = search_symbols(
            self.index,
            "test payment",
            filters=SearchFilters(entity_kinds=frozenset({EntityKind.TEST})),
            top_k=25,
        )
        judged = {
            "test_create_payment@test_payments.py",
            "persists a payment@js/service.test.js",
            "persists a payment@ts/service.test.ts",
        }
        returned = [f"{hit.name}@{hit.repository_relative_path}" for hit in result.hits]
        self.assertTrue(judged.issubset(set(returned)))
        self.assertEqual(len(result.hits), 4)
        self.assertEqual(returned[0], "test_create_payment@test_payments.py")
        for hit in result.hits:
            self.assertIs(hit.entity_kind, EntityKind.TEST)

    def test_graph_context_surfaces_the_exposing_endpoint_for_a_symbol_query(self):
        result = search_endpoints(self.index, "createRefund", include_graph_context=True, top_k=25)
        self.assertIn("app.py", {self.index.document(item).repository_relative_path for item in result.entity_ids()})
        for hit in result.hits:
            self.assertEqual(hit.entity_kind, EntityKind.API_ENDPOINT)
            if hit.match_basis.value == "graph_neighbor":
                self.assertTrue(hit.context_support)

    def test_baseline_is_independent_of_bm25_components(self):
        identifiers = exact_substring_baseline(self.index, "createPayment", top_k=10)
        self.assertTrue(identifiers)
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertEqual(exact_substring_baseline(self.index, "createPayment", top_k=3), identifiers[:3])
        with self.assertRaises(RetrievalEvaluationError):
            exact_substring_baseline(self.index, "   ", top_k=5)

    def test_evaluation_input_contracts(self):
        for k in (0, -1, True, 1.5, "5", None):
            with self.subTest(k=k), self.assertRaises(RetrievalEvaluationError):
                evaluate_retrieval(self.index, JUDGMENTS, k=k)
        with self.assertRaises(RetrievalEvaluationError):
            evaluate_retrieval(self.index, "payment")
        with self.assertRaises(RetrievalEvaluationError):
            evaluate_retrieval(self.index, [JUDGMENTS[0], JUDGMENTS[0]])
        with self.assertRaises(RetrievalEvaluationError):
            evaluate_retrieval(self.index, [object()])
        with self.assertRaises(TypeError):
            RelevanceJudgment(query="x", expected=("FUNCTION:y",))
        with self.assertRaises(ValueError):
            RelevanceJudgment(query="", expected=())
        with self.assertRaises(TypeError):
            RelevanceJudgment(query="x", expected=(E("FUNCTION", "y"),))
        with self.assertRaises(ValueError):
            E(EntityKind.FUNCTION, 5)
        with self.assertRaises(ValueError):
            RelevanceJudgment(query="x", expected=(), category="exact")
        with self.assertRaises(ValueError):
            RelevanceJudgment(
                query="x",
                expected=(E(EntityKind.FUNCTION, "y"), E(EntityKind.METHOD, "y")),
                category="exact",
            )
        with self.assertRaises(ValueError):
            RelevanceJudgment(query="x", expected=(E(EntityKind.FUNCTION, "y"),), category="unknown")
        with self.assertRaises(ValueError):
            RelevanceJudgment(
                query="x",
                expected=(E(EntityKind.FUNCTION, "y"), E(EntityKind.FUNCTION, "y")),
            )

    def test_unresolved_selectors_are_reported_not_hidden(self):
        judgment = RelevanceJudgment(
            query="absent",
            category="conceptual",
            expected=(E(EntityKind.FUNCTION, "doesNotExist", "nowhere.py"),),
        )
        result = evaluate_retrieval(self.index, [judgment], k=5)
        self.assertEqual(result.unresolved_judgment_labels, ("absent -> FUNCTION:doesNotExist@nowhere.py",))
        self.assertEqual(result.baseline.metrics.evaluated_queries, 0)
        self.assertEqual(result.baseline.metrics.recall_at_k, 0.0)

    def test_evaluation_applies_typed_filters_consistently(self):
        filtered = evaluate_retrieval(
            self.index,
            JUDGMENTS,
            k=5,
            filters=SearchFilters(entity_kinds=frozenset({EntityKind.API_ENDPOINT})),
        )
        for outcome in filtered.bm25.outcomes:
            for identifier in outcome.retrieved_ids:
                with self.subTest(query=outcome.query, entity=identifier):
                    self.assertIs(self.index.document(identifier).entity_kind, EntityKind.API_ENDPOINT)


if __name__ == "__main__":
    unittest.main()
