"""Typed request contracts: which selectors, options and limits each intent accepts."""

from __future__ import annotations

import unittest

from arctrellis.core import EntityKind
from arctrellis.orchestration import (
    InvalidQueryLimitError,
    InvalidQueryRequestError,
    QueryIntent,
    QueryRequest,
    SelectorForm,
    UnsupportedIntentError,
    intent_spec,
)

STRUCTURAL = QueryIntent.TRACE_ENDPOINT_TO_DATABASE


class QueryRequestIntentTests(unittest.TestCase):
    def test_every_intent_has_a_specification(self) -> None:
        for intent in QueryIntent:
            spec = intent_spec(intent)
            self.assertIs(spec.intent, intent)
            self.assertIn(SelectorForm.NONE, spec.selector_forms | {SelectorForm.NONE})
            if spec.source_kinds:
                self.assertTrue(spec.structural_query, f"{intent} selects a source but names no query")

    def test_missing_required_selector_is_rejected(self) -> None:
        with self.assertRaisesRegex(InvalidQueryRequestError, "requires an explicit entity selector"):
            QueryRequest(intent=STRUCTURAL)

    def test_structural_intent_rejects_free_form_search_text_as_its_only_selector(self) -> None:
        with self.assertRaisesRegex(UnsupportedIntentError, "does not support selector"):
            QueryRequest(intent=STRUCTURAL, search_text="payment creation")

    def test_invalid_intent_is_rejected(self) -> None:
        with self.assertRaisesRegex(InvalidQueryRequestError, "intent must be a QueryIntent"):
            QueryRequest(intent="TRACE_ENDPOINT_TO_DATABASE")  # type: ignore[arg-type]

    def test_conflicting_selectors_are_rejected(self) -> None:
        with self.assertRaisesRegex(InvalidQueryRequestError, "exactly one selector form"):
            QueryRequest(intent=STRUCTURAL, entity_id="abc", qualified_name="app.py::handler")

    def test_partial_endpoint_selector_is_rejected(self) -> None:
        with self.assertRaisesRegex(InvalidQueryRequestError, "supplied together"):
            QueryRequest(intent=STRUCTURAL, http_method="POST")

    def test_callable_intent_rejects_endpoint_selector(self) -> None:
        with self.assertRaisesRegex(UnsupportedIntentError, "does not support selector"):
            QueryRequest(intent=QueryIntent.FIND_CALLERS, http_method="POST", route_path="/payments")

    def test_search_rejects_structural_only_options(self) -> None:
        with self.assertRaisesRegex(UnsupportedIntentError, "transitive_callers"):
            QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="payment", transitive_callers=True)
        with self.assertRaisesRegex(UnsupportedIntentError, "max_paths"):
            QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="payment", max_paths=3)
        with self.assertRaisesRegex(UnsupportedIntentError, "max_depth"):
            QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="payment", max_depth=3)

    def test_structural_intent_rejects_retrieval_only_options(self) -> None:
        with self.assertRaisesRegex(UnsupportedIntentError, "include_graph_context"):
            QueryRequest(intent=STRUCTURAL, entity_id="abc", include_graph_context=True)
        with self.assertRaisesRegex(UnsupportedIntentError, "does not support selector"):
            QueryRequest(intent=QueryIntent.FIND_DIRECT_TESTS, search_text="x")

    def test_transitive_is_only_valid_for_caller_queries(self) -> None:
        self.assertTrue(
            QueryRequest(intent=QueryIntent.FIND_CALLERS, entity_id="abc", transitive_callers=True).transitive_callers
        )
        with self.assertRaisesRegex(UnsupportedIntentError, "transitive_callers"):
            QueryRequest(
                intent=QueryIntent.FIND_AFFECTED_ENDPOINTS,
                entity_id="abc",
                transitive_callers=True,
            )

    def test_operation_filter_is_only_valid_where_the_query_uses_it(self) -> None:
        self.assertEqual(
            QueryRequest(
                intent=QueryIntent.TRACE_CALLABLE_TO_DATABASE,
                entity_id="abc",
                operation_kinds=frozenset(("read",)),
            ).operation_kinds,
            frozenset(("read",)),
        )
        self.assertEqual(
            QueryRequest(
                intent=QueryIntent.SEARCH_ENTITIES,
                search_text="payment",
                operation_kinds=frozenset(("write",)),
            ).operation_kinds,
            frozenset(("write",)),
        )
        with self.assertRaisesRegex(UnsupportedIntentError, "operation_kinds"):
            QueryRequest(
                intent=QueryIntent.FIND_DIRECT_TESTS,
                entity_id="abc",
                operation_kinds=frozenset(("write",)),
            )

    def test_unsupported_operation_kind_filter_is_rejected(self) -> None:
        with self.assertRaisesRegex(InvalidQueryRequestError, "operation_kinds"):
            QueryRequest(intent=STRUCTURAL, entity_id="abc", operation_kinds=frozenset(("drop",)))


class QueryRequestTextTests(unittest.TestCase):
    def test_empty_search_text_is_rejected(self) -> None:
        with self.assertRaisesRegex(InvalidQueryRequestError, "search_text"):
            QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="")

    def test_padded_search_text_is_rejected(self) -> None:
        with self.assertRaisesRegex(InvalidQueryRequestError, "surrounding whitespace"):
            QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text=" payment ")

    def test_control_characters_are_rejected(self) -> None:
        with self.assertRaisesRegex(InvalidQueryRequestError, "control characters"):
            QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="payment\ndetail")

    def test_excessively_long_search_text_is_rejected(self) -> None:
        with self.assertRaisesRegex(InvalidQueryRequestError, "search_text must not exceed"):
            QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="a" * 513)

    def test_excessively_long_identifier_is_rejected(self) -> None:
        with self.assertRaisesRegex(InvalidQueryRequestError, "entity_id must not exceed"):
            QueryRequest(intent=STRUCTURAL, entity_id="a" * 1025)

    def test_malformed_http_method_is_rejected(self) -> None:
        for method in ("post", " POST", "FETCH", ""):
            with self.subTest(method=method), self.assertRaises(InvalidQueryRequestError):
                QueryRequest(intent=STRUCTURAL, http_method=method, route_path="/payments")

    def test_unknown_http_method_is_rejected(self) -> None:
        with self.assertRaisesRegex(InvalidQueryRequestError, "http_method must be one of"):
            QueryRequest(intent=STRUCTURAL, http_method="PURGE", route_path="/payments")

    def test_unknown_endpoint_scope_is_rejected(self) -> None:
        with self.assertRaisesRegex(InvalidQueryRequestError, "endpoint_scope"):
            QueryRequest(intent=QueryIntent.LIST_ENDPOINTS, endpoint_scope="public")

    def test_unknown_entity_kind_is_rejected(self) -> None:
        with self.assertRaisesRegex(InvalidQueryRequestError, "entity_kind"):
            QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="payment", entity_kind="CLASS")


class QueryRequestLimitTests(unittest.TestCase):
    def test_boolean_limits_are_rejected(self) -> None:
        for field in ("top_k", "max_depth", "max_paths", "max_expansions", "max_examined_postings"):
            with self.subTest(field=field), self.assertRaisesRegex(InvalidQueryLimitError, "positive integer"):
                QueryRequest(intent=QueryIntent.LIST_ENDPOINTS, **{field: True})

    def test_non_integer_limits_are_rejected(self) -> None:
        with self.assertRaisesRegex(InvalidQueryLimitError, "positive integer"):
            QueryRequest(intent=QueryIntent.LIST_ENDPOINTS, max_paths=2.5)

    def test_non_positive_limits_are_rejected(self) -> None:
        for value in (0, -1):
            with self.subTest(value=value), self.assertRaisesRegex(InvalidQueryLimitError, "positive integer"):
                QueryRequest(intent=QueryIntent.LIST_ENDPOINTS, max_paths=value)

    def test_top_k_cap_is_enforced(self) -> None:
        with self.assertRaisesRegex(InvalidQueryLimitError, "top_k must not exceed"):
            QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="payment", top_k=1000)

    def test_boolean_flags_must_be_booleans(self) -> None:
        with self.assertRaisesRegex(InvalidQueryRequestError, "include_graph_context must be a boolean"):
            QueryRequest(
                intent=QueryIntent.SEARCH_ENTITIES,
                search_text="payment",
                include_graph_context=1,  # type: ignore[arg-type]
            )

    def test_request_is_immutable_and_serializable(self) -> None:
        request = QueryRequest(intent=STRUCTURAL, http_method="POST", route_path="/payments")
        with self.assertRaises(AttributeError):
            request.route_path = "/other"  # type: ignore[misc]
        payload = request.to_dict()
        self.assertEqual(payload["intent"], "TRACE_ENDPOINT_TO_DATABASE")
        self.assertEqual(payload["selector_form"], "ENDPOINT_METHOD_PATH")
        self.assertEqual(payload["operation_kinds"], ["delete", "read", "write"])

    def test_selector_form_property_reports_the_supplied_form(self) -> None:
        request = QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="payment")
        self.assertIs(request.selector_form, SelectorForm.SEARCH_TEXT)
        self.assertIs(QueryRequest(intent=QueryIntent.LIST_ENDPOINTS).selector_form, SelectorForm.NONE)

    def test_entity_kind_constraint_is_accepted_for_structural_intents(self) -> None:
        request = QueryRequest(intent=QueryIntent.FIND_CALLERS, entity_id="abc", entity_kind=EntityKind.METHOD)
        self.assertIs(request.entity_kind, EntityKind.METHOD)


if __name__ == "__main__":
    unittest.main()
