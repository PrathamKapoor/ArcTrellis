"""Candidate examination budgets, query limits and honest truncation reporting."""

import unittest

from arctrellis.core import EntityKind, RelationshipKind
from arctrellis.retrieval import (
    DEFAULT_MAX_EXAMINED_POSTINGS,
    MAX_ACCEPTED_TOP_K,
    MAX_QUERY_LENGTH,
    MAX_QUERY_TOKENS,
    SearchFilters,
    build_search_index,
    search_symbols,
)
from arctrellis.retrieval.context import DEFAULT_MAX_CONTEXT_NEIGHBORS
from arctrellis.retrieval.errors import InvalidSearchLimitError, InvalidSearchQueryError
from arctrellis.retrieval.search import TRUNCATION_REASONS
from tests.retrieval.fixtures import edge, entity, payment_graph, synthetic_graph


class ResourceLimitTests(unittest.TestCase):
    def test_posting_examination_budget_is_enforced_and_reported(self):
        index = build_search_index(payment_graph())
        exhaustive = search_symbols(index, "payment")
        bounded = search_symbols(index, "payment", max_examined_postings=2)
        self.assertFalse(exhaustive.truncated)
        self.assertEqual(exhaustive.examined_postings, exhaustive.matched_candidate_count)
        self.assertTrue(bounded.truncated)
        self.assertEqual(bounded.truncation_reasons, ("posting_budget",))
        self.assertEqual(bounded.examined_postings, 2)
        self.assertLess(bounded.matched_candidate_count, exhaustive.matched_candidate_count)
        self.assertLessEqual(len(bounded.hits), 2)

    def test_budget_bounds_only_the_records_it_actually_counts(self):
        index = build_search_index(synthetic_graph(400))
        exhaustive = search_symbols(index, "payment")
        self.assertEqual(exhaustive.examined_postings, 400)
        self.assertFalse(exhaustive.truncated)
        result = search_symbols(index, "payment", max_examined_postings=150)
        self.assertEqual(result.examined_postings, 150)
        self.assertTrue(result.truncated)
        self.assertEqual(result.matched_candidate_count, 150)
        self.assertEqual(result.eligible_candidate_count, 150)

    def test_filtered_records_still_consume_the_posting_budget(self):
        index = build_search_index(payment_graph())
        unfiltered = search_symbols(index, "payment", max_examined_postings=100)
        filtered = search_symbols(
            index,
            "payment",
            max_examined_postings=100,
            filters=SearchFilters(entity_kinds=frozenset({EntityKind.API_ENDPOINT})),
        )
        self.assertEqual(unfiltered.examined_postings, filtered.examined_postings)
        self.assertGreater(filtered.matched_candidate_count, filtered.eligible_candidate_count)

    def test_graph_seed_budget_is_enforced_and_reported(self):
        index = build_search_index(payment_graph())
        result = search_symbols(index, "payment", include_graph_context=True, max_graph_seeds=1)
        self.assertTrue(result.truncated)
        self.assertIn("graph_seed_budget", result.truncation_reasons)
        self.assertEqual(result.graph_seed_budget, 1)

    def test_graph_neighbor_budget_is_enforced_and_reported(self):
        index = build_search_index(payment_graph(), max_context_neighbors=64)
        result = search_symbols(index, "payment", include_graph_context=True, max_graph_neighbors=1)
        self.assertTrue(result.truncated)
        self.assertIn("graph_neighbor_budget", result.truncation_reasons)
        for hit in result.hits:
            self.assertLessEqual(len(hit.context_support), 1)

    def test_untruncated_results_report_no_reasons(self):
        index = build_search_index(payment_graph())
        result = search_symbols(index, "payment", include_graph_context=True)
        self.assertEqual(result.truncation_reasons, ())
        self.assertFalse(result.truncated)

    def test_truncation_reason_vocabulary_is_closed(self):
        self.assertEqual(TRUNCATION_REASONS, ("graph_neighbor_budget", "graph_seed_budget", "posting_budget"))

    def test_documented_defaults_and_caps(self):
        self.assertEqual(MAX_QUERY_LENGTH, 512)
        self.assertEqual(MAX_QUERY_TOKENS, 24)
        self.assertEqual(MAX_ACCEPTED_TOP_K, 100)
        self.assertEqual(DEFAULT_MAX_EXAMINED_POSTINGS, 50000)
        self.assertEqual(DEFAULT_MAX_CONTEXT_NEIGHBORS, 16)
        self.assertEqual(DEFAULT_MAX_CONTEXT_NEIGHBORS, 16)

    def test_top_k_caps_are_enforced_at_the_boundary(self):
        index = build_search_index(payment_graph())
        self.assertEqual(search_symbols(index, "payment", top_k=1).top_k, 1)
        self.assertEqual(search_symbols(index, "payment", top_k=MAX_ACCEPTED_TOP_K).top_k, MAX_ACCEPTED_TOP_K)
        with self.assertRaises(InvalidSearchLimitError):
            search_symbols(index, "payment", top_k=MAX_ACCEPTED_TOP_K + 1)

    def test_query_length_and_token_limits_are_enforced(self):
        index = build_search_index(payment_graph())
        self.assertEqual(len("a" * MAX_QUERY_LENGTH), MAX_QUERY_LENGTH)
        with self.assertRaises(InvalidSearchQueryError):
            search_symbols(index, "a" * (MAX_QUERY_LENGTH + 1))
        self.assertEqual(
            search_symbols(index, " ".join(["ab"] * MAX_QUERY_TOKENS)).query_tokens, ("ab",) * MAX_QUERY_TOKENS
        )
        with self.assertRaises(InvalidSearchQueryError):
            search_symbols(index, " ".join(["ab"] * (MAX_QUERY_TOKENS + 1)))

    def test_oversized_metadata_value_is_bounded_at_index_build(self):
        huge = entity(
            "entity:huge",
            EntityKind.FUNCTION,
            "hugeHandler",
            "huge.py::hugeHandler",
            path="huge.py",
            start=1,
            language="python",
            metadata=(("module", "m-5000-" * 500), ("alias", "x" * 300)),
        )
        index = build_search_index(payment_graph(extra_entities=(huge,)))
        document = index.document("entity:huge")
        self.assertEqual(len(document.field_value("module")), 512)
        self.assertEqual(len(document.field_tokens("module")), 32)
        self.assertEqual(len(document.field_value("alias")), 300)
        self.assertEqual(search_symbols(index, "hugeHandler").hits[0].entity_id, "entity:huge")

    def test_context_neighbor_cap_is_a_build_time_reported_limit(self):
        entities = tuple(
            entity(
                f"function:caller{number:03d}",
                EntityKind.FUNCTION,
                f"caller{number:03d}",
                f"hub.py::caller{number:03d}",
                path="hub.py",
                start=number + 1,
                language="python",
            )
            for number in range(50)
        )
        edges = tuple(
            edge(
                f"rel:hub{number:03d}", f"function:caller{number:03d}", RelationshipKind.CALLS, "function:createPayment"
            )
            for number in range(50)
        )
        index = build_search_index(payment_graph(extra_entities=entities, extra_edges=edges), max_context_neighbors=5)
        self.assertEqual(index.context.max_neighbors_per_entity, 5)
        self.assertGreater(index.context_capped_list_count, 0)
        self.assertEqual(len(index.context.incoming["function:createPayment"]), 5)
        result = search_symbols(index, "caller000", include_graph_context=True)
        self.assertIn("graph_seed_budget", result.truncation_reasons)
        self.assertTrue(result.truncated)

    def test_a_large_corpus_remains_deterministic_and_bounded(self):
        for size in (10, 200, 1500):
            with self.subTest(size=size):
                first = search_symbols(build_search_index(synthetic_graph(size)), "payment", top_k=10)
                second = search_symbols(build_search_index(synthetic_graph(size)), "payment", top_k=10)
                self.assertEqual(first.to_dict(), second.to_dict())
                self.assertLessEqual(len(first.hits), 10)
                self.assertGreater(first.index_document_count, size)

    def test_graph_context_on_a_large_corpus_stays_within_declared_bounds(self):
        index = build_search_index(synthetic_graph(1500), max_context_neighbors=8)
        result = search_symbols(
            index,
            "paymentService01000",
            include_graph_context=True,
            top_k=25,
            max_graph_seeds=5,
            max_graph_neighbors=8,
        )
        self.assertEqual(result.graph_seed_budget, 5)
        self.assertLessEqual(
            result.eligible_candidate_count,
            result.matched_candidate_count + 5 * 8,
        )
        for hit in result.hits:
            self.assertLessEqual(len(hit.context_support), 8)


if __name__ == "__main__":
    unittest.main()
