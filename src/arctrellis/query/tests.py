"""Direct static TESTS lookup, not runtime coverage or transitive test inference."""

from arctrellis.core import CodeEntity, EntityKind, Relationship
from arctrellis.core import RelationshipKind as RK
from arctrellis.graph import CodeGraph

from .errors import QueryGraphInvariantError
from .models import AnalysisCompleteness, PathQueryResult, TraversalDirection
from .traversal import CALLABLE_KINDS, require_entity, search


def find_direct_tests_for_symbol(
    graph: CodeGraph,
    symbol_entity_id: str,
    *,
    max_paths: int = 25,
    max_expansions: int = 10000,
    analysis_completeness: AnalysisCompleteness = AnalysisCompleteness.UNKNOWN,
) -> PathQueryResult:
    """One-hop incoming TESTS to FUNCTION/METHOD, retaining each proof site.

    Empty means no known direct static test relationship. A directly tested handler
    is not proof of HTTP client coverage; no transitive relationships are fabricated.
    """
    require_entity(graph, symbol_entity_id, CALLABLE_KINDS)

    def transition(state: int, edge: Relationship, node: CodeEntity) -> int | None:
        if edge.kind is not RK.TESTS:
            return None
        if node.kind is not EntityKind.TEST:
            raise QueryGraphInvariantError("TESTS must originate at TEST")
        return 1

    return search(
        graph,
        symbol_entity_id,
        query_kind="direct_tests",
        transition=transition,
        terminal=lambda state, node: state == 1,
        direction=TraversalDirection.REVERSE,
        max_depth=1,
        max_paths=max_paths,
        max_expansions=max_expansions,
        analysis_completeness=analysis_completeness,
    )
