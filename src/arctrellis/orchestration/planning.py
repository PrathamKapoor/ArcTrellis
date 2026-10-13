"""Deterministic request-to-plan translation; no execution, no inference."""

from __future__ import annotations

from .models import PlanStep, QueryIntent, QueryPlan, QueryRequest, SelectorForm, intent_spec


def build_plan(request: QueryRequest) -> QueryPlan:
    """Translate a validated request into its intended operation sequence.

    The plan is pure data. It contains no callable, no graph, no timestamp and no
    random value, so equal requests always produce equal plans (D-142). A
    free-form ``search_text`` only ever produces a search plan; it can never
    imply an architectural intent.
    """
    if not isinstance(request, QueryRequest):
        raise TypeError("build_plan requires a validated QueryRequest")
    spec = intent_spec(request.intent)
    steps: list[PlanStep] = []
    if request.intent is QueryIntent.SEARCH_ENTITIES:
        steps.append(PlanStep.SEARCH_CANDIDATES)
    elif spec.source_kinds:
        if request.selector_form is SelectorForm.SEARCH_TEXT:
            steps.append(PlanStep.SEARCH_CANDIDATES)
            steps.append(PlanStep.SELECT_CANONICAL_ENTITY)
        else:
            steps.append(PlanStep.SELECT_CANONICAL_ENTITY)
    if spec.structural_query is not None:
        steps.append(PlanStep.EXECUTE_STRUCTURAL_QUERY)
    steps.append(PlanStep.ASSEMBLE_EVIDENCE)
    if request.intent is QueryIntent.SEARCH_ENTITIES:
        planned_output = "ranked_entity_candidates"
    elif request.intent is QueryIntent.LIST_ENDPOINTS:
        planned_output = "endpoint_inventory"
    elif request.intent is QueryIntent.LIST_DATABASE_CALLERS:
        planned_output = "database_owner_inventory"
    else:
        planned_output = "evidence_paths"
    return QueryPlan(
        request=request,
        steps=tuple(steps),
        source_kinds=spec.source_kinds,
        structural_query=spec.structural_query,
        planned_output=planned_output,
    )
