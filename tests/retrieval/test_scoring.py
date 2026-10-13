"""BM25 arithmetic, field weighting and exact-match boost policy."""

import unittest
from math import isfinite, log

from arctrellis.core import EntityKind
from arctrellis.retrieval import (
    BM25_B,
    BM25_K1,
    EXACT_NAME_BOOST,
    EXACT_NORMALIZED_NAME_BOOST,
    EXACT_QUALIFIED_NAME_BOOST,
    EXACT_ROUTE_BOOST,
    NAME_PREFIX_BOOST,
    ExactMatchTier,
    LexicalSearchIndex,
    build_search_index,
)
from arctrellis.retrieval.errors import RetrievalInvariantError
from arctrellis.retrieval.scoring import (
    DEFAULT_FIELD_WEIGHT,
    FIELD_WEIGHTS,
    bm25_score,
    exact_match_boost,
    exact_match_tiers,
    field_weight,
    weighted_document_length,
    weighted_term_frequency,
)
from tests.retrieval.fixtures import entity, payment_graph


def document(identifier, name, qualified_name, **metadata):
    graph = payment_graph()
    graph.add_entity(
        entity(
            identifier,
            EntityKind.FUNCTION,
            name,
            qualified_name,
            path=qualified_name.split("::")[0],
            language="python",
            metadata=tuple(metadata.items()),
        )
    )
    return build_search_index(graph).document(identifier)


class Bm25ArithmeticTests(unittest.TestCase):
    def reference(self, document_count, document_frequency, term_frequency, document_length, average_length):
        idf = log(1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5))
        normalization = BM25_K1 * (1 - BM25_B + BM25_B * (document_length / average_length))
        return idf * (term_frequency * (BM25_K1 + 1)) / (term_frequency + normalization)

    def test_single_term_score_matches_the_reference_formula(self):
        found = document("m", "payment", "payments.py::payment")
        index_document = weighted_document_length(found)
        frequency = weighted_term_frequency(found, "payment")
        expected = self.reference(1, 1, frequency, index_document, index_document)
        self.assertAlmostEqual(
            bm25_score(found, index_document, index_document, 1, {"payment": frequency}, {"payment": 1}),
            expected,
            places=12,
        )

    def test_multi_document_score_matches_the_reference_formula(self):
        found = document("m", "payment", "payments.py::payment")
        index_document = weighted_document_length(found)
        frequency = weighted_term_frequency(found, "payment")
        expected = self.reference(4, 2, frequency, index_document, 3.5)
        self.assertAlmostEqual(
            bm25_score(found, index_document, 3.5, 4, {"payment": frequency}, {"payment": 2}),
            expected,
            places=12,
        )

    def test_smoothing_keeps_idf_positive_for_ubiquitous_terms(self):
        found = document("m", "payment", "payments.py::payment")
        length = weighted_document_length(found)
        ubiquitous = bm25_score(found, length, length, 100, {"payment": 1.0}, {"payment": 100})
        self.assertGreater(ubiquitous, 0.0)

    def test_missing_terms_and_empty_corpus_score_zero(self):
        found = document("m", "payment", "payments.py::payment")
        length = weighted_document_length(found)
        self.assertEqual(bm25_score(found, length, length, 1, {}, {"payment": 1}), 0.0)
        self.assertEqual(bm25_score(found, length, 5.0, 0, {"payment": 1.0}, {"payment": 1}), 0.0)
        self.assertEqual(bm25_score(found, length, 5.0, 3, {"absent": 1.0}, {}), 0.0)

    def test_zero_average_length_drops_length_normalization_instead_of_dividing_by_zero(self):
        found = document("m", "payment", "payments.py::payment")
        frequency = weighted_term_frequency(found, "payment")
        expected = log(1 + (1 - 1 + 0.5) / 1.5) * (BM25_K1 + 1)
        self.assertAlmostEqual(
            bm25_score(found, 0.0, 0.0, 1, {"payment": frequency}, {"payment": 1}), expected, places=12
        )
        self.assertEqual(bm25_score(found, 0.0, 0.0, 0, {"payment": frequency}, {"payment": 1}), 0.0)

    def test_scores_are_always_finite_for_very_large_term_frequencies(self):
        found = document("m", "payment", "payments.py::payment")
        length = weighted_document_length(found)
        for frequency in (1.0, 1e3, 1e9):
            with self.subTest(frequency=frequency):
                score = bm25_score(found, length, length * 1000, 5, {"payment": frequency}, {"payment": 5})
                self.assertTrue(isfinite(score))
                self.assertGreater(score, 0.0)

    def test_invalid_parameters_are_rejected(self):
        found = document("m", "payment", "payments.py::payment")
        length = weighted_document_length(found)
        for k1 in (-1.0, float("nan"), float("inf")):
            with self.subTest(k1=k1), self.assertRaises(ValueError):
                bm25_score(found, length, length, 1, {"payment": 1.0}, {"payment": 1}, k1=k1)
        for b in (-0.1, 1.1, float("nan")):
            with self.subTest(b=b), self.assertRaises(ValueError):
                bm25_score(found, length, length, 1, {"payment": 1.0}, {"payment": 1}, b=b)
        with self.assertRaises(TypeError):
            bm25_score(found, length, length, 1, {"payment": 1.0}, {"payment": 1}, k1="1.2")

    def test_non_finite_result_is_an_invariant_failure(self):
        found = document("m", "payment", "payments.py::payment")
        length = weighted_document_length(found)
        with self.assertRaises(RetrievalInvariantError):
            bm25_score(found, length, 1e-320, 2, {"payment": 1e308}, {"payment": 1})

    def test_parameters_are_the_documented_defaults(self):
        self.assertEqual((BM25_K1, BM25_B), (1.2, 0.75))


class FieldWeightTests(unittest.TestCase):
    def test_every_projected_field_name_has_a_documented_weight(self):
        from arctrellis.retrieval import (
            FIELD_ENTITY_KIND,
            FIELD_LANGUAGE,
            FIELD_NAME,
            FIELD_PATH,
            FIELD_QUALIFIED_NAME,
            SEARCHABLE_METADATA_KEYS,
        )

        covered = {FIELD_ENTITY_KIND, FIELD_LANGUAGE, FIELD_NAME, FIELD_PATH, FIELD_QUALIFIED_NAME}
        self.assertEqual(set(FIELD_WEIGHTS), covered | set(SEARCHABLE_METADATA_KEYS))
        self.assertEqual(field_weight("unlisted"), DEFAULT_FIELD_WEIGHT)

    def test_weights_are_exact_binary_fractions(self):
        for name, weight in FIELD_WEIGHTS.items():
            with self.subTest(field=name):
                self.assertEqual(weight * 2, round(weight * 2))

    def test_name_outweighs_path_for_the_same_token(self):
        found = document("m", "payment", "payments.py::payment")
        weighted = weighted_term_frequency(found, "payment")
        by_field = {item.name: item.tokens.count("payment") for item in found.fields if "payment" in item.tokens}
        self.assertEqual(
            weighted,
            FIELD_WEIGHTS["name"] * by_field["name"] + FIELD_WEIGHTS["qualified_name"] * by_field["qualified_name"],
        )
        self.assertGreater(FIELD_WEIGHTS["name"], FIELD_WEIGHTS["repository_relative_path"])
        self.assertEqual(
            weighted_document_length(found), sum(FIELD_WEIGHTS[item.name] * len(item.tokens) for item in found.fields)
        )


class ExactMatchTests(unittest.TestCase):
    def test_qualified_name_exact_match_is_the_strongest_tier(self):
        found = document("m", "handler", "payments.py::createPayment")
        tiers = exact_match_tiers(found, "payments.py::createPayment")
        self.assertIn((ExactMatchTier.EXACT_QUALIFIED_NAME, "exact:qualified_name"), tiers)
        boost, tier = exact_match_boost(found, "payments.py::createPayment", tiers)
        self.assertEqual((boost, tier), (EXACT_QUALIFIED_NAME_BOOST, ExactMatchTier.EXACT_QUALIFIED_NAME))

    def test_name_exact_match_beats_route_and_normalized_tiers(self):
        found = document("m", "createPayment", "payments.py::createPayment")
        tiers = exact_match_tiers(found, "createPayment")
        self.assertEqual(max(tier for tier, _ in tiers), ExactMatchTier.EXACT_NAME)
        self.assertEqual(exact_match_boost(found, "createPayment", tiers)[0], EXACT_NAME_BOOST)
        self.assertEqual(exact_match_boost(found, "CREATEPAYMENT", tiers)[0], EXACT_NAME_BOOST)

    def test_route_method_and_path_exact_match(self):
        found = document(
            "m",
            "payments",
            "api.py::payments",
            http_method="POST",
            route_path="/payments",
        )
        tiers = exact_match_tiers(found, "POST /payments")
        self.assertEqual(tiers, ((ExactMatchTier.EXACT_ROUTE, "exact:route"),))
        self.assertEqual(exact_match_boost(found, "POST /payments", tiers)[0], EXACT_ROUTE_BOOST)
        self.assertEqual(exact_match_boost(found, "post /payments", tiers)[0], EXACT_ROUTE_BOOST)

    def test_canonical_endpoint_name_and_route_both_report_every_satisfied_rule(self):
        index = build_search_index(payment_graph())
        endpoint = index.document("endpoint:post-payments")
        tiers = exact_match_tiers(endpoint, "POST /payments")
        self.assertIn(ExactMatchTier.EXACT_NAME, [tier for tier, _ in tiers])
        self.assertIn(ExactMatchTier.EXACT_ROUTE, [tier for tier, _ in tiers])
        self.assertEqual(max(tier for tier, _ in tiers), ExactMatchTier.EXACT_NAME)
        self.assertEqual(exact_match_boost(endpoint, "POST /payments", tiers)[0], EXACT_NAME_BOOST)

    def test_separator_spelling_still_matches_the_name(self):
        found = document("m", "POST /payments", "api.py::POST /payments")
        self.assertIn(
            ExactMatchTier.EXACT_NORMALIZED_NAME, [tier for tier, _ in exact_match_tiers(found, "POST/payments")]
        )

    def test_name_prefix_boost(self):
        found = document("m", "PaymentService", "payments.py::PaymentService")
        tiers = exact_match_tiers(found, "Payment")
        self.assertEqual(tiers, ((ExactMatchTier.NAME_PREFIX, "prefix:name"),))
        self.assertEqual(exact_match_boost(found, "Payment", tiers), (NAME_PREFIX_BOOST, ExactMatchTier.NAME_PREFIX))

    def test_very_short_prefixes_do_not_boost(self):
        found = document("m", "PaymentService", "payments.py::PaymentService")
        self.assertEqual(exact_match_tiers(found, "Pay"), ())
        self.assertEqual(exact_match_tiers(found, ""), ())

    def test_unrelated_queries_produce_no_exact_tier(self):
        found = document("m", "createPayment", "payments.py::createPayment")
        self.assertEqual(exact_match_tiers(found, "refund"), ())
        self.assertEqual(exact_match_boost(found, "refund", ()), (0.0, ExactMatchTier.NONE))

    def test_only_the_strongest_tier_is_applied_but_all_are_reported(self):
        found = document("m", "createPayment", "payments.py::createPayment")
        tiers = exact_match_tiers(found, "createPayment")
        self.assertGreaterEqual(len(tiers), 2)
        self.assertEqual(exact_match_boost(found, "createPayment", tiers)[0], EXACT_NAME_BOOST)

    def test_boosts_strictly_decrease_with_priority(self):
        from arctrellis.retrieval import GRAPH_CONTEXT_BOOST_CAP

        ordered = [
            EXACT_QUALIFIED_NAME_BOOST,
            EXACT_NAME_BOOST,
            EXACT_ROUTE_BOOST,
            EXACT_NORMALIZED_NAME_BOOST,
            NAME_PREFIX_BOOST,
        ]
        self.assertEqual(ordered, sorted(ordered, reverse=True))
        self.assertGreater(NAME_PREFIX_BOOST, 0.0)
        self.assertLess(GRAPH_CONTEXT_BOOST_CAP, EXACT_NORMALIZED_NAME_BOOST)


class DocumentLengthTests(unittest.TestCase):
    def test_index_lengths_match_the_weighted_projection(self):
        index: LexicalSearchIndex = build_search_index(payment_graph())
        for item in index.documents:
            with self.subTest(entity=item.entity_id):
                self.assertAlmostEqual(index.document_lengths[item.entity_id], weighted_document_length(item))
                self.assertGreater(index.document_lengths[item.entity_id], 0.0)

    def test_posting_frequencies_are_weighted(self):
        index = build_search_index(payment_graph())
        item = index.document("class:PaymentService")
        for token in item.distinct_tokens:
            with self.subTest(token=token):
                stored = dict(index.postings[token])["class:PaymentService"]
                self.assertEqual(stored, weighted_term_frequency(item, token))


if __name__ == "__main__":
    unittest.main()
