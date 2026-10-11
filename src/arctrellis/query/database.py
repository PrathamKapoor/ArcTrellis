"""Potential static database capability paths; no runtime success/commit claims."""

from arctrellis.core import CodeEntity, EntityKind, Relationship
from arctrellis.core import RelationshipKind as RK
from arctrellis.graph import CodeGraph

from .errors import QueryGraphInvariantError
from .models import AnalysisCompleteness, PathQueryResult
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
