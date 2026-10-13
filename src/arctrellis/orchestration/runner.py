"""The single request execution order: plan, select, query, bundle."""

from __future__ import annotations

from arctrellis.retrieval import SearchHit

from .errors import OrchestrationInvariantError
from .evidence import build_bundle
from .execution import execute_plan
from .models import EvidenceBundle, QueryIntent, QueryPlan, QueryRequest, SelectionStatus, SelectorForm
from .pipeline import AnalysisSnapshot
from .planning import build_plan
from .selection import search_candidates, select_canonical_entity


def run_query(snapshot: AnalysisSnapshot, request: QueryRequest) -> EvidenceBundle:
    """Execute one structured request against a completed analysis snapshot.

    The order is fixed and observable:

    1. validate the request (already done by :class:`QueryRequest`);
    2. plan it deterministically;
    3. resolve the canonical source entity, or produce ranked candidates;
    4. run the existing structural query only when the plan's own source
       requirement is satisfied by an exact selection;
    5. assemble one evidence bundle.

    A free-form ``search_text`` only ever performs retrieval. It never implies an
    architectural intent, and a lexically well-ranked candidate is never used as
    the target of a structural query (D-143).
    """
    if not isinstance(snapshot, AnalysisSnapshot):
        raise OrchestrationInvariantError("run_query requires an AnalysisSnapshot")
    if not isinstance(request, QueryRequest):
        raise OrchestrationInvariantError("run_query requires a validated QueryRequest")
    plan: QueryPlan = build_plan(request)
    search_hits: tuple[SearchHit, ...] = ()
    retrieval_truncation: tuple[str, ...] = ()
    if request.intent is QueryIntent.SEARCH_ENTITIES:
        found = search_candidates(snapshot, request)
        selection = found.selection
        search_hits = found.result.hits
        retrieval_truncation = found.result.truncation_reasons
    else:
        selection = select_canonical_entity(snapshot, request, plan.source_kinds)
    execution = None
    if plan.structural_query is not None:
        needs_source = bool(plan.source_kinds)
        if needs_source and selection.selected_entity_id is not None:
            execution = execute_plan(snapshot, plan, selection.selected_entity_id)
        elif not needs_source and selection.status in (
            SelectionStatus.RESOLVED,
            SelectionStatus.NOT_REQUIRED,
        ):
            execution = execute_plan(snapshot, plan, None)
        elif selection.status is SelectionStatus.CANDIDATES and request.selector_form is SelectorForm.SEARCH_TEXT:
            raise OrchestrationInvariantError("search text cannot drive a structural query without an exact entity ID")
    return build_bundle(
        snapshot,
        plan,
        selection,
        execution,
        retrieval_truncation=retrieval_truncation,
        search_hits=search_hits,
    )
