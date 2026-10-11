"""Structural endpoint impact candidates, never predictions that changes break requests."""

from arctrellis.core import CodeEntity, EntityKind, Relationship
from arctrellis.core import RelationshipKind as RK
from arctrellis.graph import CodeGraph

from .errors import QueryGraphInvariantError
from .models import AnalysisCompleteness, PathQueryResult, TraversalDirection
from .traversal import CALLABLE_KINDS, require_entity, search


def find_potentially_affected_endpoints(
    graph: CodeGraph,
    changed_callable_id: str,
    *,
    max_depth: int = 12,
    max_paths: int = 25,
    max_expansions: int = 10000,
    analysis_completeness: AnalysisCompleteness = AnalysisCompleteness.UNKNOWN,
) -> PathQueryResult:
    """Reverse CALLS* then reverse EXPOSES; pre-handler impact deliberately omitted.

    Path entities run endpoint -> changed callable; original relationships retain
    direction, evidence and confidence. Depth includes EXPOSES. No known candidate
    means no available dependency path, never that a change is safe at runtime.
    """
    require_entity(graph, changed_callable_id, CALLABLE_KINDS)

    def transition(state: int, edge: Relationship, node: CodeEntity) -> int | None:
        if edge.kind is RK.CALLS and node.kind in CALLABLE_KINDS:
            return 0
        if edge.kind is RK.EXPOSES:
            if node.kind is not EntityKind.API_ENDPOINT:
                raise QueryGraphInvariantError("EXPOSES must originate at API_ENDPOINT")
            return 1
        return None

    return search(
        graph,
        changed_callable_id,
        query_kind="potentially_affected_endpoints",
        transition=transition,
        terminal=lambda state, node: state == 1,
        direction=TraversalDirection.REVERSE,
        max_depth=max_depth,
        max_paths=max_paths,
        max_expansions=max_expansions,
        analysis_completeness=analysis_completeness,
    )
