"""Read-only constrained simple-path enumeration using public graph APIs."""

from collections import deque
from collections.abc import Callable

from arctrellis.core import CodeEntity, EntityKind, Relationship, RelationshipKind
from arctrellis.graph import CodeGraph
from arctrellis.graph.errors import GraphError, UnknownEntityError

from .errors import InvalidQuerySourceError, QueryGraphInvariantError, UnknownQueryEntityError
from .models import AnalysisCompleteness, EvidencePath, PathQueryResult, TraversalDirection, path_order, validate_limits

type Transition = Callable[[int, Relationship, CodeEntity], int | None]
type Terminal = Callable[[int, CodeEntity], bool]
CALLABLE_KINDS = frozenset((EntityKind.FUNCTION, EntityKind.METHOD))


def require_entity(graph: CodeGraph, identifier: str, kinds: frozenset[EntityKind] | None = None) -> CodeEntity:
    try:
        entity = graph.get_entity(identifier)
    except UnknownEntityError as error:
        raise UnknownQueryEntityError(f"unknown query entity: {identifier!r}") from error
    if kinds is not None and entity.kind not in kinds:
        raise InvalidQuerySourceError(f"unsupported query source kind: {entity.kind.value}")
    return entity


def search(
    graph: CodeGraph,
    source_id: str,
    *,
    query_kind: str,
    transition: Transition,
    terminal: Terminal,
    direction: TraversalDirection = TraversalDirection.FORWARD,
    max_depth: int = 12,
    max_paths: int = 25,
    max_expansions: int = 10000,
    analysis_completeness: AnalysisCompleteness = AnalysisCompleteness.UNKNOWN,
    stop_at_terminal: bool = True,
) -> PathQueryResult:
    validate_limits(max_depth, max_paths, max_expansions)
    if not isinstance(analysis_completeness, AnalysisCompleteness) or not isinstance(direction, TraversalDirection):
        raise TypeError("completeness/direction must be canonical query enums")
    source = require_entity(graph, source_id)
    queue: deque[tuple[tuple[CodeEntity, ...], tuple[Relationship, ...], int]] = deque([((source,), (), 0)])
    paths: list[EvidencePath] = []
    reasons: set[str] = set()
    expansions = 0
    reverse = direction is TraversalDirection.REVERSE
    stop = False
    while queue and not stop:
        entities, edges, state = queue.popleft()
        current = entities[-1]
        if edges and terminal(state, current):
            if len(paths) == max_paths:
                reasons.add("max_paths")
                break
            paths.append(
                EvidencePath.from_graph(
                    graph, entities[::-1] if reverse else entities, edges[::-1] if reverse else edges
                )
            )
            if stop_at_terminal:
                continue
        try:
            adjacent = graph.incoming(current.id) if reverse else graph.outgoing(current.id)
            for edge in adjacent:
                if expansions == max_expansions:
                    reasons.add("max_expansions")
                    stop = True
                    break
                expansions += 1
                anchor = edge.target_entity_id if reverse else edge.source_entity_id
                neighbor_id = edge.source_entity_id if reverse else edge.target_entity_id
                if anchor != current.id or graph.get_relationship(edge.id) != edge:
                    raise QueryGraphInvariantError("adjacency disagrees with stored relationship")
                neighbor = graph.get_entity(neighbor_id)
                next_state = transition(state, edge, neighbor)
                if next_state is None or neighbor_id in {e.id for e in entities}:
                    continue
                if len(edges) == max_depth:
                    reasons.add("max_depth")
                    continue
                queue.append((entities + (neighbor,), edges + (edge,), next_state))
        except GraphError as error:
            raise QueryGraphInvariantError("graph contains missing query references") from error
    return PathQueryResult(
        query_kind,
        source_id,
        tuple(sorted(paths, key=path_order)),
        direction,
        max_depth,
        max_paths,
        max_expansions,
        expansions,
        tuple(sorted(reasons)),
        analysis_completeness,
    )


def find_paths(
    graph: CodeGraph,
    source_entity_id: str,
    target_entity_id: str,
    *,
    relationship_kinds: frozenset[RelationshipKind],
    direction: TraversalDirection = TraversalDirection.FORWARD,
    max_depth: int = 12,
    max_paths: int = 25,
    max_expansions: int = 10000,
    analysis_completeness: AnalysisCompleteness = AnalysisCompleteness.UNKNOWN,
) -> PathQueryResult:
    """Enumerate nonempty bounded paths through explicitly selected kinds only."""
    require_entity(graph, target_entity_id)
    if not isinstance(relationship_kinds, frozenset) or any(
        not isinstance(k, RelationshipKind) for k in relationship_kinds
    ):
        raise TypeError("relationship_kinds must be a frozenset of RelationshipKind")
    return search(
        graph,
        source_entity_id,
        query_kind="paths",
        direction=direction,
        transition=lambda state, edge, node: state if edge.kind in relationship_kinds else None,
        terminal=lambda state, node: node.id == target_entity_id,
        max_depth=max_depth,
        max_paths=max_paths,
        max_expansions=max_expansions,
        analysis_completeness=analysis_completeness,
    )
