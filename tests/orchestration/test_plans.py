"""Deterministic plan translation: same request, same plan, no hidden behaviour."""

from __future__ import annotations

import json
import unittest

from arctrellis.core import EntityKind
from arctrellis.orchestration import (
    InvalidQueryRequestError,
    PlanStep,
    QueryIntent,
    QueryPlan,
    QueryRequest,
    build_plan,
    plan_query,
)

SEARCH = QueryIntent.SEARCH_ENTITIES
TRACE = QueryIntent.TRACE_ENDPOINT_TO_DATABASE


class QueryPlanTests(unittest.TestCase):
    def test_search_plan_searches_then_assembles_evidence(self) -> None:
        plan = build_plan(QueryRequest(intent=SEARCH, search_text="payment creation"))
        self.assertEqual(plan.steps, (PlanStep.SEARCH_CANDIDATES, PlanStep.ASSEMBLE_EVIDENCE))
        self.assertIsNone(plan.structural_query)
        self.assertEqual(plan.source_kinds, frozenset())
        self.assertEqual(plan.planned_output, "ranked_entity_candidates")
        self.assertFalse(plan.requires_selection)

    def test_endpoint_plan_selects_then_executes(self) -> None:
        plan = build_plan(QueryRequest(intent=TRACE, http_method="POST", route_path="/payments"))
        self.assertEqual(
            plan.steps,
            (
                PlanStep.SELECT_CANONICAL_ENTITY,
                PlanStep.EXECUTE_STRUCTURAL_QUERY,
                PlanStep.ASSEMBLE_EVIDENCE,
            ),
        )
        self.assertEqual(plan.source_kinds, frozenset((EntityKind.API_ENDPOINT,)))
        self.assertEqual(plan.structural_query, "trace_endpoint_to_database")
        self.assertTrue(plan.requires_selection)

    def test_free_form_text_cannot_plan_a_structural_query(self) -> None:
        plan = plan_query(QueryRequest(intent=SEARCH, search_text="show me what happens on payment"))
        self.assertNotIn(PlanStep.EXECUTE_STRUCTURAL_QUERY, plan.steps)
        self.assertIsNone(plan.structural_query)

    def test_inventory_plans_report_their_own_output(self) -> None:
        self.assertEqual(
            build_plan(QueryRequest(intent=QueryIntent.LIST_ENDPOINTS)).planned_output,
            "endpoint_inventory",
        )
        self.assertEqual(
            build_plan(QueryRequest(intent=QueryIntent.LIST_DATABASE_CALLERS)).planned_output,
            "database_owner_inventory",
        )

    def test_plan_is_deterministic_and_serializable(self) -> None:
        request = QueryRequest(intent=TRACE, qualified_name="app.py::handler", max_depth=4, max_paths=7)
        first = build_plan(request)
        second = build_plan(QueryRequest(intent=TRACE, qualified_name="app.py::handler", max_depth=4, max_paths=7))
        self.assertEqual(first, second)
        self.assertEqual(first.to_dict(), second.to_dict())
        json.dumps(first.to_dict())

    def test_plan_carries_no_callable_or_environment_state(self) -> None:
        payload = build_plan(QueryRequest(intent=TRACE, http_method="POST", route_path="/payments")).to_dict()
        json.dumps(payload)
        serialized = json.dumps(payload, sort_keys=True)
        self.assertNotIn(str(id(self)), serialized)
        self.assertEqual(
            sorted(payload),
            [
                "intent",
                "limits",
                "planned_output",
                "required_source_kinds",
                "selector_form",
                "steps",
                "structural_query",
            ],
        )

    def test_plan_reflects_requested_limits(self) -> None:
        plan = build_plan(QueryRequest(intent=TRACE, entity_id="abc", max_paths=3, max_expansions=50))
        self.assertEqual(plan.to_dict()["limits"]["max_paths"], 3)
        self.assertEqual(plan.to_dict()["limits"]["max_expansions"], 50)

    def test_plan_rejects_a_broken_contract(self) -> None:
        with self.assertRaises(TypeError):
            build_plan("not a request")  # type: ignore[arg-type]
        with self.assertRaises(InvalidQueryRequestError):
            QueryPlan(
                request=QueryRequest(intent=SEARCH, search_text="x"),
                steps=(PlanStep.SEARCH_CANDIDATES,),
                source_kinds=frozenset(),
                structural_query=None,
                planned_output="ranked_entity_candidates",
            )

    def test_public_plan_query_is_the_same_translation(self) -> None:
        request = QueryRequest(intent=SEARCH, search_text="payment")
        self.assertEqual(plan_query(request), build_plan(request))


if __name__ == "__main__":
    unittest.main()
