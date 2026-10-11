"""Reverse CALLS evidence only; no import/definition/test association inference."""

from arctrellis.core import CodeEntity, Relationship
from arctrellis.core import RelationshipKind as RK
from arctrellis.graph import CodeGraph

from .models import AnalysisCompleteness, PathQueryResult, TraversalDirection
from .traversal import CALLABLE_KINDS, require_entity, search


def find_callers(
    graph: CodeGraph,
    target_callable_id: str,
    *,
    transitive: bool = False,
    max_depth: int = 12,
    max_paths: int = 25,
    max_expansions: int = 10000,
    analysis_completeness: AnalysisCompleteness = AnalysisCompleteness.UNKNOWN,
) -> PathQueryResult:
    """Direct or transitive callable callers. TEST/MODULE execution owners are omitted.

    Returned paths run caller -> target in original edge direction. Every nonempty
    simple reverse CALLS prefix is a candidate; transitive mode continues beyond it.
    Direct mode is exactly one edge, irrespective of the (validated) depth budget.
    """
    require_entity(graph, target_callable_id, CALLABLE_KINDS)
    if type(transitive) is not bool:
        raise TypeError("transitive must be bool")

    def transition(state: int, edge: Relationship, node: CodeEntity) -> int | None:
        if edge.kind is RK.CALLS and node.kind in CALLABLE_KINDS and (transitive or state == 0):
            return state + 1
        return None

    return search(
        graph,
        target_callable_id,
        query_kind="callers",
        transition=transition,
        terminal=lambda state, node: state > 0,
        direction=TraversalDirection.REVERSE,
        stop_at_terminal=not transitive,
        max_depth=max_depth,
        max_paths=max_paths,
        max_expansions=max_expansions,
        analysis_completeness=analysis_completeness,
    )
