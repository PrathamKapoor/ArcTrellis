"""Lexical relevance, typed filters, deterministic ranking and JSON output."""

import json
import unittest

from arctrellis.core import EntityKind
from arctrellis.retrieval import (
    ExactMatchTier,
    LexicalSearchIndex,
    MatchBasis,
    SearchFilters,
    SearchResult,
    build_search_index,
    search_database_operations,
    search_endpoints,
    search_symbols,
    search_tests,
)
from arctrellis.retrieval.errors import InvalidSearchLimitError, InvalidSearchQueryError
from tests.retrieval.fixtures import empty_graph, entity, payment_graph


class LexicalRelevanceTests(unittest.TestCase):
    def setUp(self):
        self.index = build_search_index(payment_graph())

    def rank(self, query, **options):
        return search_symbols(self.index, query, **options)

    def test_exact_symbol_name_search_ranks_the_symbol_first(self):
        result = self.rank("createPayment")
        self.assertEqual(result.hits[0].entity_id, "function:createPayment")
        self.assertEqual(result.hits[0].match_basis, MatchBasis.LEXICAL)
        self.assertEqual(result.hits[0].exact_match_priority, ExactMatchTier.EXACT_NAME)
        self.assertEqual(result.hits[0].matched_terms, ("create", "payment"))
        self.assertEqual(result.hits[0].matched_fields, ("name", "qualified_name"))

    def test_qualified_name_search(self):
        result = self.rank("payments.py::createPayment")
        self.assertEqual(result.hits[0].entity_id, "function:createPayment")
        self.assertEqual(result.hits[0].exact_match_priority, ExactMatchTier.EXACT_QUALIFIED_NAME)

    def test_camel_case_and_snake_case_queries_share_results(self):
        camel = self.rank("createPayment")
        snake = self.rank("create_payment")
        kebab = self.rank("create-payment")
        self.assertEqual(camel.entity_ids(), snake.entity_ids())
        self.assertEqual(camel.entity_ids(), kebab.entity_ids())
        self.assertEqual(camel.hits[0].name, "createPayment")

    def test_http_method_and_path_query(self):
        result = self.rank("POST /payments")
        hit = result.hits[0]
        self.assertEqual(hit.entity_id, "endpoint:post-payments")
        self.assertEqual(hit.entity_kind, EntityKind.API_ENDPOINT)
        self.assertIn("post", hit.matched_terms)
        self.assertIn("payments", hit.matched_terms)

    def test_framework_filtered_endpoint_query(self):
        result = search_endpoints(self.index, "payments", filters=SearchFilters(frameworks=frozenset({"express"})))
        self.assertEqual(result.hits, ())
        allowed = search_endpoints(self.index, "payments", filters=SearchFilters(frameworks=frozenset({"fastapi"})))
        self.assertEqual([hit.entity_id for hit in allowed.hits], ["endpoint:post-payments"])

    def test_prisma_style_provider_filtered_query(self):
        graph = payment_graph(
            extra_entities=(
                entity(
                    "db:prisma",
                    EntityKind.DATABASE_OPERATION,
                    "prisma:payment.create@204",
                    "service.ts::database:prisma:payment.create@204",
                    path="service.ts",
                    start=204,
                    language="typescript",
                    metadata=(
                        ("provider", "prisma"),
                        ("operation_kind", "write"),
                        ("operation_name", "create"),
                        ("target_name", "payment"),
                    ),
                ),
            )
        )
        index = build_search_index(graph)
        result = search_database_operations(
            index, "payment create", filters=SearchFilters(providers=frozenset({"prisma"}))
        )
        self.assertEqual([hit.entity_id for hit in result.hits], ["db:prisma"])
        self.assertEqual(result.hits[0].entity_kind, EntityKind.DATABASE_OPERATION)

    def test_sqlalchemy_style_operation_query(self):
        result = search_database_operations(self.index, "sqlalchemy payment insert")
        self.assertEqual([hit.entity_id for hit in result.hits], ["db:insert"])
        self.assertEqual(
            search_database_operations(
                self.index, "sqlalchemy", filters=SearchFilters(operation_kinds=frozenset({"read"}))
            ).hits,
            (),
        )

    def test_test_name_query(self):
        result = search_tests(self.index, "test_create_payment")
        self.assertEqual([hit.entity_id for hit in result.hits], ["test:create-payment"])
        self.assertEqual(result.hits[0].entity_kind, EntityKind.TEST)

    def test_module_and_path_query(self):
        result = self.rank("test_payments")
        self.assertEqual(result.hits[0].entity_id, "test:create-payment")
        self.assertIn("repository_relative_path", result.hits[0].matched_fields)

    def test_repeated_token_query_matches_a_single_token_query(self):
        repeated = self.rank("payment payment payment")
        single = self.rank("payment")
        self.assertEqual(repeated.query_tokens, ("payment", "payment", "payment"))
        self.assertEqual(set(repeated.entity_ids()), set(single.entity_ids()))
        scores = {hit.entity_id: hit.bm25_score for hit in repeated.hits}
        self.assertEqual(scores, {hit.entity_id: hit.bm25_score for hit in single.hits})

    def test_unknown_token_query_returns_no_hits_without_inventing_results(self):
        result = self.rank("zzzznotpresent")
        self.assertEqual(result.hits, ())
        self.assertEqual(result.matched_candidate_count, 0)
        self.assertEqual(result.eligible_candidate_count, 0)
        self.assertFalse(result.truncated)

    def test_empty_corpus_returns_an_empty_result(self):
        result = search_symbols(build_search_index(empty_graph()), "payment")
        self.assertEqual(result.hits, ())
        self.assertEqual(result.index_document_count, 0)
        self.assertEqual(result.examined_postings, 0)

    def test_blank_queries_are_rejected(self):
        for query in ("", "   ", "\t\n", "...", "///"):
            with self.subTest(query=query), self.assertRaises(InvalidSearchQueryError):
                self.rank(query)

    def test_over_long_queries_are_rejected(self):
        with self.assertRaises(InvalidSearchQueryError):
            self.rank("payment " * 200)
        with self.assertRaises(InvalidSearchQueryError):
            self.rank("payment" * 200)

    def test_too_many_query_tokens_are_rejected(self):
        with self.assertRaises(InvalidSearchQueryError):
            self.rank(" ".join(f"token{number}" for number in range(30)))
        self.assertEqual(self.rank(" ".join(["payment"] * 24)).query_tokens, ("payment",) * 24)

    def test_unicode_queries_rank_deterministically(self):
        result = self.rank("ＰＡＹＭＥＮＴ")
        self.assertEqual(result.entity_ids(), self.rank("payment").entity_ids())
        self.assertEqual(result.normalized_query, "payment")

    def test_identical_scores_break_ties_by_exact_priority_then_entity_id(self):
        result = self.rank("payment")
        scores = [hit.relevance_score for hit in result.hits]
        self.assertEqual(scores, sorted(scores, reverse=True))
        for first, second in zip(result.hits, result.hits[1:], strict=False):
            if (
                first.relevance_score == second.relevance_score
                and first.exact_match_priority == second.exact_match_priority
            ):
                self.assertLess(first.entity_id, second.entity_id)

    def test_repeated_runs_are_identical(self):
        first = self.rank("payment service", top_k=5)
        second = search_symbols(build_search_index(payment_graph()), "payment service", top_k=5)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_top_k_is_enforced_after_filtering(self):
        result = self.rank("payment", top_k=2)
        self.assertEqual(len(result.hits), 2)
        self.assertEqual(result.top_k, 2)
        self.assertGreater(result.eligible_candidate_count, len(result.hits))

    def test_top_k_applies_to_filtered_results_not_the_unfiltered_list(self):
        unfiltered = self.rank("payments", top_k=3)
        filtered = search_endpoints(self.index, "payments", top_k=3)
        self.assertGreater(len(unfiltered.hits), len(filtered.hits))
        self.assertEqual([hit.entity_id for hit in filtered.hits], ["endpoint:post-payments"])
        endpoint_in_unfiltered = next(hit for hit in unfiltered.hits if hit.entity_id == "endpoint:post-payments")
        self.assertEqual(filtered.hits[0].relevance_score, endpoint_in_unfiltered.relevance_score)
        self.assertEqual(filtered.eligible_candidate_count, 1)

    def test_filters_are_applied_before_ranking(self):
        result = search_endpoints(self.index, "payments", top_k=5)
        self.assertTrue(all(hit.entity_kind is EntityKind.API_ENDPOINT for hit in result.hits))
        self.assertLess(result.eligible_candidate_count, self.rank("payments").eligible_candidate_count)
        self.assertEqual(result.hits[0].entity_id, "endpoint:post-payments")
        unfiltered_first = next(hit for hit in self.rank("payments").hits if hit.entity_id == "endpoint:post-payments")
        self.assertEqual(result.hits[0].relevance_score, unfiltered_first.relevance_score)

    def test_language_and_path_prefix_filters(self):
        by_language = self.rank("python", filters=SearchFilters(languages=frozenset({"typescript"})))
        self.assertEqual(by_language.hits, ())
        by_prefix = self.rank("payments", filters=SearchFilters(path_prefixes=("test_",)))
        self.assertEqual([hit.entity_id for hit in by_prefix.hits], ["test:create-payment"])
        self.assertEqual(
            self.rank("payments", filters=SearchFilters(path_prefixes=("app", "test_"))).hits[0].entity_id,
            "endpoint:post-payments",
        )

    def test_http_method_filter(self):
        self.assertEqual(
            search_endpoints(self.index, "users", filters=SearchFilters(http_methods=frozenset({"GET"})))
            .hits[0]
            .entity_id,
            "endpoint:get-users-id",
        )
        self.assertEqual(
            search_endpoints(self.index, "users", filters=SearchFilters(http_methods=frozenset({"POST"}))).hits, ()
        )

    def test_invalid_limits_are_rejected(self):
        for value in (True, False, 0, -1, 1.5, "10", None):
            with self.subTest(value=value), self.assertRaises(InvalidSearchLimitError):
                self.rank("payment", top_k=value)
        with self.assertRaises(InvalidSearchLimitError):
            self.rank("payment", top_k=101)
        with self.assertRaises(InvalidSearchLimitError):
            self.rank("payment", max_examined_postings=0)
        with self.assertRaises(InvalidSearchLimitError):
            self.rank("payment", max_graph_neighbors=0)

    def test_every_exposed_score_component_is_finite_and_sums_correctly(self):
        for hit in self.rank("payment creation", include_graph_context=True, top_k=10).hits:
            with self.subTest(entity=hit.entity_id):
                for component in (hit.bm25_score, hit.exact_match_boost, hit.prefix_boost, hit.graph_context_boost):
                    self.assertGreaterEqual(component, 0.0)
                    self.assertEqual(component, component)  # not NaN
                self.assertAlmostEqual(
                    hit.relevance_score,
                    hit.bm25_score + hit.exact_match_boost + hit.prefix_boost + hit.graph_context_boost,
                    places=12,
                )

    def test_result_and_hit_serialization_is_json_primitive(self):
        result = self.rank("payment", include_graph_context=True, top_k=3)
        payload = result.to_dict()
        self.assertEqual(json.loads(json.dumps(payload)), payload)
        for value in self.walk(payload):
            self.assertIn(type(value), (dict, list, str, int, float, bool, type(None)))
        self.assertEqual(payload["index_snapshot_id"], self.index.snapshot_id)
        self.assertEqual(
            sorted(payload)[:4], ["analysis_completeness", "eligible_candidate_count", "examined_postings", "filters"]
        )

    @staticmethod
    def walk(value):
        pending = [value]
        while pending:
            current = pending.pop()
            yield current
            if isinstance(current, dict):
                pending.extend(current.values())
            elif isinstance(current, (tuple, list)):
                pending.extend(current)

    def test_invalid_filter_contracts(self):
        with self.assertRaises(TypeError):
            SearchFilters(entity_kinds=frozenset({"FUNCTION"}))
        with self.assertRaises(ValueError):
            SearchFilters(entity_kinds=frozenset())
        with self.assertRaises(TypeError):
            SearchFilters(languages=frozenset({1}))
        with self.assertRaises(ValueError):
            SearchFilters(path_prefixes=("b", "a"))
        with self.assertRaises(TypeError):
            search_symbols(self.index, "payment", filters="kind=function")

    def test_search_requires_a_real_index_and_result_contract(self):
        with self.assertRaises(InvalidSearchQueryError):
            search_symbols("not an index", "payment")
        result = self.rank("payment")
        self.assertIsInstance(result, SearchResult)
        with self.assertRaises(TypeError):
            search_symbols(self.index, "payment", include_graph_context="yes")
        self.assertIsInstance(self.index, LexicalSearchIndex)

    def test_analysis_completeness_is_callable_context_not_a_claim(self):
        default = self.rank("payment")
        self.assertEqual(default.analysis_completeness.value, "unknown")
        from arctrellis.query import AnalysisCompleteness

        self.assertEqual(
            self.rank("payment", analysis_completeness=AnalysisCompleteness.PARTIAL).analysis_completeness,
            AnalysisCompleteness.PARTIAL,
        )
        with self.assertRaises(TypeError):
            self.rank("payment", analysis_completeness="complete")
