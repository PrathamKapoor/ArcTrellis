"""Potential static database capability paths; no runtime success/commit claims."""

from arctrellis.core import CodeEntity, EntityKind, Relationship
from arctrellis.core import RelationshipKind as RK
from arctrellis.graph import CodeGraph
from arctrellis.graph.errors import GraphError

from .errors import QueryGraphInvariantError
from .models import AnalysisCompleteness, EvidencePath, PathQueryResult, TraversalDirection, path_order, validate_limits
from .traversal import CALLABLE_KINDS, require_entity, search

DATABASE_KINDS = frozenset(("read", "write", "delete"))


def database_operation(edge: Relationship, target: CodeEntity, operation_kinds: frozenset[str]) -> bool:
    if edge.kind not in (RK.READS_DATABASE, RK.WRITES_DATABASE):
        return False
    metadata = dict(target.metadata)
    operation = metadata.get("operation_kind")
    expected = RK.READS_DATABASE if operation == "read" else RK.WRITES_DATABASE
    if target.kind is not EntityKind.DATABASE_OPERATION or operation not in DATABASE_KINDS or edge.kind is not expected:
        raise QueryGraphInvariantError("invalid database relationship target/category")
    if metadata.get("effect_stage") in ("staged_mutation", "transaction_control", "unknown"):
        raise QueryGraphInvariantError("non-executing observation has database capability edge")
    return operation in operation_kinds


def validate_operations(operation_kinds: frozenset[str]) -> None:
    if not isinstance(operation_kinds, frozenset) or not operation_kinds <= DATABASE_KINDS:
        raise ValueError("operation_kinds must be a frozenset subset of read/write/delete")


def _trace(
    graph: CodeGraph,
    source_id: str,
    *,
    endpoint: bool,
    operation_kinds: frozenset[str],
    max_depth: int,
    max_paths: int,
    max_expansions: int,
    analysis_completeness: AnalysisCompleteness,
) -> PathQueryResult:
    require_entity(graph, source_id, frozenset((EntityKind.API_ENDPOINT,)) if endpoint else CALLABLE_KINDS)
    validate_operations(operation_kinds)

    def transition(state: int, edge: Relationship, node: CodeEntity) -> int | None:
        if endpoint and state == 0:
            if edge.kind is not RK.EXPOSES:
                return None
            if node.kind not in CALLABLE_KINDS:
                raise QueryGraphInvariantError("EXPOSES must target a callable")
            return 1
        if edge.kind is RK.CALLS:
            return 1 if node.kind in CALLABLE_KINDS else None
        return 2 if database_operation(edge, node, operation_kinds) else None

    return search(
        graph,
        source_id,
        query_kind="endpoint_to_database" if endpoint else "callable_to_database",
        transition=transition,
        terminal=lambda state, node: state == 2,
        max_depth=max_depth,
        max_paths=max_paths,
        max_expansions=max_expansions,
        analysis_completeness=analysis_completeness,
    )


def trace_endpoint_to_database(
    graph: CodeGraph,
    endpoint_id: str,
    *,
    operation_kinds: frozenset[str] = DATABASE_KINDS,
    max_depth: int = 12,
    max_paths: int = 25,
    max_expansions: int = 10000,
    analysis_completeness: AnalysisCompleteness = AnalysisCompleteness.UNKNOWN,
) -> PathQueryResult:
    """EXPOSES -> CALLS* -> READS_DATABASE/WRITES_DATABASE, registration ID authoritative.

    The selected endpoint retains its local/effective identity; no route merging.
    DELETE is filtered by operation metadata, even though its edge is WRITES_DATABASE.
    """
    return _trace(
        graph,
        endpoint_id,
        endpoint=True,
        operation_kinds=operation_kinds,
        max_depth=max_depth,
        max_paths=max_paths,
        max_expansions=max_expansions,
        analysis_completeness=analysis_completeness,
    )


def trace_callable_to_database(
    graph: CodeGraph,
    callable_entity_id: str,
    *,
    operation_kinds: frozenset[str] = DATABASE_KINDS,
    max_depth: int = 12,
    max_paths: int = 25,
    max_expansions: int = 10000,
    analysis_completeness: AnalysisCompleteness = AnalysisCompleteness.UNKNOWN,
) -> PathQueryResult:
    """CALLS* -> database edge; direct operations are valid one-hop paths."""
    return _trace(
        graph,
        callable_entity_id,
        endpoint=False,
        operation_kinds=operation_kinds,
        max_depth=max_depth,
        max_paths=max_paths,
        max_expansions=max_expansions,
        analysis_completeness=analysis_completeness,
    )


def get_direct_database_operations(
    graph: CodeGraph,
    owner_entity_id: str,
    *,
    operation_kinds: frozenset[str] = DATABASE_KINDS,
    max_paths: int = 25,
    max_expansions: int = 10000,
    analysis_completeness: AnalysisCompleteness = AnalysisCompleteness.UNKNOWN,
) -> PathQueryResult:
    """Direct DB edges only; MODULE owners allowed as in existing materialization.

    Each path retains owner, operation metadata (provider/category) and original proof.
    No CALLS traversal. Use trace_callable_to_database for transitive capability.
    """
    require_entity(graph, owner_entity_id, CALLABLE_KINDS | frozenset((EntityKind.MODULE,)))
    validate_operations(operation_kinds)
    return search(
        graph,
        owner_entity_id,
        query_kind="direct_database_operations",
        transition=lambda state, edge, node: 1 if database_operation(edge, node, operation_kinds) else None,
        terminal=lambda state, node: state == 1,
        max_depth=1,
        max_paths=max_paths,
        max_expansions=max_expansions,
        analysis_completeness=analysis_completeness,
    )


def list_direct_database_callers(
    graph: CodeGraph,
    *,
    operation_kinds: frozenset[str] = DATABASE_KINDS,
    max_paths: int = 1000,
    max_expansions: int = 10000,
    analysis_completeness: AnalysisCompleteness = AnalysisCompleteness.UNKNOWN,
) -> PathQueryResult:
    """One-hop DB paths for FUNCTION/METHOD owners; parallel operation sites survive.

    source_entity_id is None for this graph-wide inventory. Group paths by their
    first entity ID to list owners; target records retain provider/category details.
    """
    validate_limits(1, max_paths, max_expansions)
    validate_operations(operation_kinds)
    paths: list[EvidencePath] = []
    reasons: set[str] = set()
    expansions = 0
    for edge in graph.relationships():
        if expansions == max_expansions:
            reasons.add("max_expansions")
            break
        expansions += 1
        if edge.kind not in (RK.READS_DATABASE, RK.WRITES_DATABASE):
            continue
        try:
            owner = graph.get_entity(edge.source_entity_id)
            target = graph.get_entity(edge.target_entity_id)
            if graph.get_relationship(edge.id) != edge:
                raise QueryGraphInvariantError("database inventory relationship disagrees with graph")
        except GraphError as error:
            raise QueryGraphInvariantError("database inventory contains missing references") from error
        if not database_operation(edge, target, operation_kinds) or owner.kind not in CALLABLE_KINDS:
            continue
        if len(paths) == max_paths:
            reasons.add("max_paths")
            break
        paths.append(EvidencePath.from_graph(graph, (owner, target), (edge,)))
    return PathQueryResult(
        "direct_database_callers",
        None,
        tuple(sorted(paths, key=path_order)),
        TraversalDirection.FORWARD,
        1,
        max_paths,
        max_expansions,
        expansions,
        tuple(sorted(reasons)),
        analysis_completeness,
    )
