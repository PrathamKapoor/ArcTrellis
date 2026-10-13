"""Execution of a validated plan using only existing structural-query functions.

This module dispatches to ``arctrellis.query``; it never re-implements traversal,
never adds an edge and never re-ranks graph facts. Retrieval relevance selected
the candidate entity, and it never changes a stored CALLS/EXPOSES/database/TESTS
confidence, evidence record or relationship identity (D-144).
"""

from __future__ import annotations

from dataclasses import dataclass

from arctrellis.core import CodeEntity
from arctrellis.query import (
    AnalysisCompleteness,
    EntityQueryResult,
    EvidencePath,
    PathQueryResult,
    TraversalDirection,
    find_callers,
    find_direct_tests_for_symbol,
    find_potentially_affected_endpoints,
    get_direct_database_operations,
    list_direct_database_callers,
    list_endpoints,
    trace_callable_to_database,
    trace_endpoint_to_database,
)

from .errors import OrchestrationInvariantError
from .models import QueryIntent, QueryPlan
from .pipeline import AnalysisSnapshot


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    """Raw structural or inventory result, still preserving upstream semantics.

    The upstream ``PathQueryResult`` / ``EntityQueryResult`` is retained so a
    caller can inspect the original truncation reasons, direction and confidence
    summary without going through the bundle projection.
    """

    intent: QueryIntent
    paths: tuple[EvidencePath, ...] = ()
    entities: tuple[CodeEntity, ...] = ()
    path_result: PathQueryResult | None = None
    entity_result: EntityQueryResult | None = None
    analysis_completeness: AnalysisCompleteness = AnalysisCompleteness.UNKNOWN
    graph_truncation: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.intent, QueryIntent):
            raise OrchestrationInvariantError("execution outcome requires a QueryIntent")
        for name in ("paths", "entities"):
            if not isinstance(getattr(self, name), tuple):
                raise OrchestrationInvariantError(f"{name} must be a tuple")
        if not isinstance(self.graph_truncation, tuple) or self.graph_truncation != tuple(
            sorted(set(self.graph_truncation))
        ):
            raise OrchestrationInvariantError("graph_truncation must be a sorted unique tuple")
        if self.path_result is not None and self.paths != tuple(self.path_result.paths):
            raise OrchestrationInvariantError("paths must be exactly the originating path result's paths")
        if self.path_result is None and self.paths:
            raise OrchestrationInvariantError("paths require an originating path result")
        if self.entity_result is not None and self.entities != tuple(self.entity_result.entities):
            raise OrchestrationInvariantError("entities must be exactly the originating entity result's entities")
        if self.entity_result is None and self.entities:
            raise OrchestrationInvariantError("entities require an originating entity result")
        if self.analysis_completeness != (
            self.path_result.analysis_completeness
            if self.path_result
            else self.entity_result.analysis_completeness
            if self.entity_result
            else self.analysis_completeness
        ):
            raise OrchestrationInvariantError("analysis completeness must match the originating result")


def traversal_direction(result: PathQueryResult | None) -> str:
    """Return the stored traversal direction label for reporting."""
    if result is None:
        return TraversalDirection.FORWARD.value
    return result.direction.value


def execute_plan(snapshot: AnalysisSnapshot, plan: QueryPlan, entity_id: str | None) -> ExecutionOutcome:
    """Run the structural query named by the plan against the final analysis graph.

    ``entity_id`` must already be canonically resolved by the selection step. The
    graph is read only; no relationship, evidence record or confidence value is
    created, altered or removed here. Each branch forwards the request's own
    validated budgets and analysis completeness unchanged, so upstream
    truncation reasons survive into the bundle.
    """
    if not isinstance(snapshot, AnalysisSnapshot):
        raise OrchestrationInvariantError("execute_plan requires an AnalysisSnapshot")
    if not isinstance(plan, QueryPlan):
        raise OrchestrationInvariantError("execute_plan requires a QueryPlan")
    if plan.structural_query is None:
        raise OrchestrationInvariantError("plan does not name a structural query")
    request = plan.request
    completeness = snapshot.analysis_completeness
    graph = snapshot.graph
    query = plan.structural_query
    if query == "list_endpoints":
        result = list_endpoints(
            graph,
            http_method=request.http_method,
            framework=request.framework,
            route_path=request.route_path,
            scope=request.endpoint_scope,
            max_results=request.max_paths,
            max_expansions=request.max_expansions,
            analysis_completeness=completeness,
        )
        return ExecutionOutcome(
            request.intent,
            entities=tuple(result.entities),
            entity_result=result,
            analysis_completeness=completeness,
            graph_truncation=result.truncation_reasons,
        )
    if query == "list_direct_database_callers":
        inventory = list_direct_database_callers(
            graph,
            operation_kinds=frozenset(request.operation_kinds),
            max_paths=request.max_paths,
            max_expansions=request.max_expansions,
            analysis_completeness=completeness,
        )
        return ExecutionOutcome(
            request.intent,
            paths=tuple(inventory.paths),
            path_result=inventory,
            analysis_completeness=completeness,
            graph_truncation=inventory.truncation_reasons,
        )
    if entity_id is None:
        raise OrchestrationInvariantError(f"{query} requires a resolved canonical source entity")
    traced: PathQueryResult
    if query == "trace_endpoint_to_database":
        traced = trace_endpoint_to_database(
            graph,
            entity_id,
            operation_kinds=frozenset(request.operation_kinds),
            max_depth=request.max_depth,
            max_paths=request.max_paths,
            max_expansions=request.max_expansions,
            analysis_completeness=completeness,
        )
    elif query == "trace_callable_to_database":
        traced = trace_callable_to_database(
            graph,
            entity_id,
            operation_kinds=frozenset(request.operation_kinds),
            max_depth=request.max_depth,
            max_paths=request.max_paths,
            max_expansions=request.max_expansions,
            analysis_completeness=completeness,
        )
    elif query == "get_direct_database_operations":
        traced = get_direct_database_operations(
            graph,
            entity_id,
            operation_kinds=frozenset(request.operation_kinds),
            max_paths=request.max_paths,
            max_expansions=request.max_expansions,
            analysis_completeness=completeness,
        )
    elif query == "find_direct_tests_for_symbol":
        traced = find_direct_tests_for_symbol(
            graph,
            entity_id,
            max_paths=request.max_paths,
            max_expansions=request.max_expansions,
            analysis_completeness=completeness,
        )
    elif query == "find_callers":
        traced = find_callers(
            graph,
            entity_id,
            transitive=request.transitive_callers,
            max_depth=request.max_depth,
            max_paths=request.max_paths,
            max_expansions=request.max_expansions,
            analysis_completeness=completeness,
        )
    elif query == "find_potentially_affected_endpoints":
        traced = find_potentially_affected_endpoints(
            graph,
            entity_id,
            max_depth=request.max_depth,
            max_paths=request.max_paths,
            max_expansions=request.max_expansions,
            analysis_completeness=completeness,
        )
    else:
        raise OrchestrationInvariantError(f"unknown structural query: {query}")
    return ExecutionOutcome(
        request.intent,
        paths=tuple(traced.paths),
        path_result=traced,
        analysis_completeness=completeness,
        graph_truncation=traced.truncation_reasons,
    )
