"""Independent framework-flow graphs, with occurrence-specific pre-handler proof."""

from __future__ import annotations

from typing import TYPE_CHECKING

from arctrellis.core import CodeEntity, Confidence, Evidence, Relationship, RelationshipKind
from arctrellis.extraction.source import _span_metadata
from arctrellis.graph import CodeGraph, GraphError

from .errors import FrameworkResolutionInvariantError
from .flow_models import FrameworkFlowResult, PreHandlerKind, PreHandlerObservation, _pre_id
from .ids import _identity
from .models import EndpointResolutionStatus as Status
from .models import Framework, FrameworkAnalysisResult, HttpEndpointResolution
from .resolution import (
    _choose_reference,
    _endpoint,
    _handler_index,
    _reference_handler,
    _relationship,
    _validate_snapshots,
)

if TYPE_CHECKING:
    from arctrellis.calls import CallResolutionResult
    from arctrellis.indexing import RepositoryIndexResult
    from arctrellis.resolution import ImportResolutionResult

    from .resolution import _HandlerIndex


def _validate_endpoints(
    index: RepositoryIndexResult, calls: CallResolutionResult, endpoints: FrameworkAnalysisResult
) -> None:
    if not isinstance(endpoints, FrameworkAnalysisResult):
        raise TypeError("framework flow requires endpoint analysis")
    FrameworkAnalysisResult(endpoints.graph, endpoints.observations, endpoints.endpoints, endpoints.resolutions)
    if endpoints.observations != index.route_observations:
        raise FrameworkResolutionInvariantError("endpoint observations differ from index")
    expected_entities = {e.id: e for e in calls.graph.entities()}
    expected_edges = {e.id: e for e in calls.graph.relationships()}
    expanded = []
    for route, decision in zip(endpoints.observations, endpoints.resolutions, strict=True):
        if decision.status is Status.UNSUPPORTED:
            continue
        for method in route.http_methods:
            endpoint = _endpoint(route, method)
            expanded.append(endpoint)
            expected_entities[endpoint.id] = endpoint
            relationship = _relationship(route, endpoint, None)
            expected_edges[relationship.id] = relationship
            if decision.status is Status.RESOLVED:
                relationship = _relationship(route, endpoint, decision)
                expected_edges[relationship.id] = relationship
    if (
        tuple(expanded) != endpoints.endpoints
        or endpoints.graph.entities() != tuple(expected_entities[k] for k in sorted(expected_entities))
        or endpoints.graph.relationships() != tuple(expected_edges[k] for k in sorted(expected_edges))
    ):
        raise FrameworkResolutionInvariantError("endpoint decisions and graph proof disagree")


def _pre_resolution(p: PreHandlerObservation, symbols: _HandlerIndex) -> HttpEndpointResolution:
    if p.semantic_kind is PreHandlerKind.REQUEST_HOOK:
        span = p.declaration_span
        assert span is not None
        candidates = [
            e
            for e in symbols.declarations.get((p.path, span.start_byte, span.end_byte), [])
            if e.parent_id == p.owner_module_id and (e.name,) == p.callable_reference
        ]
        return _choose_reference(p.id, candidates, "flask_before_request_hook")
    if not p.callable_reference:
        return HttpEndpointResolution(p.id, Status.UNSUPPORTED, None, (), "dynamic_pre_handler_expression")
    result = _reference_handler(
        p.id, p.owner_module_id, p.callable_reference, p.binding_supported, p.framework, symbols
    )
    if result.status is Status.RESOLVED:
        from dataclasses import replace

        assert result.resolution_method is not None
        imported = "_imported_" in result.resolution_method
        method = (
            p.framework.value
            + ("_imported_" if imported else "_local_")
            + ("route_middleware" if p.framework is Framework.EXPRESS else "dependency")
        )
        return replace(result, resolution_method=method)
    return result


def _pre_edge(p: PreHandlerObservation, endpoint: CodeEntity, decision: HttpEndpointResolution) -> Relationship:
    method, target = decision.resolution_method, decision.handler_entity_id
    assert method is not None and target is not None
    metadata = _span_metadata(p.span) + (
        ("semantic_kind", p.semantic_kind.value),
        ("order_index", str(p.order_index)),
        ("order_scope", "route" if p.route_observation_id else "file_app"),
        ("pre_handler_observation_id", p.id),
    )
    evidence = Evidence(
        _identity("arctrellis-pre-handler-evidence-v1", endpoint.id, target, p.id, method, metadata),
        p.location,
        method,
        metadata,
    )
    return Relationship(
        _identity("arctrellis-pre-handler-edge-v1", endpoint.id, target, p.id, method),
        endpoint.id,
        RelationshipKind.APPLIES_MIDDLEWARE,
        target,
        Confidence.PROVEN if p.semantic_kind is PreHandlerKind.REQUEST_HOOK else Confidence.LIKELY,
        1.0 if p.semantic_kind is PreHandlerKind.REQUEST_HOOK else (0.75 if "_imported_" in method else 0.85),
        (evidence,),
    )


def resolve_framework_flow(
    index: RepositoryIndexResult,
    imports: ImportResolutionResult,
    calls: CallResolutionResult,
    endpoints: FrameworkAnalysisResult,
) -> FrameworkFlowResult:
    """Add precise static pre-handler semantics to an independent endpoint graph.

    No source reads or framework execution. Local dependencies/middleware are
    LIKELY/.85, imported .75, exact same-app Flask hook association PROVEN/1.0.
    Ordering describes declaration order, never a global runtime execution plan.
    """
    from arctrellis.resolution import ImportResolutionStatus

    try:
        _validate_snapshots(index, imports, calls)
        _validate_endpoints(index, calls, endpoints)
        symbols = _handler_index(index, imports)
        routes = {r.id: r for r in endpoints.observations}
        decisions = {d.observation_id: d for d in endpoints.resolutions}
        by_route: dict[str, list[CodeEntity]] = {}
        by_app: dict[tuple[str, Framework, object], list[CodeEntity]] = {}
        for route in endpoints.observations:
            if decisions[route.id].status is not Status.UNSUPPORTED:
                values = [_endpoint(route, m) for m in route.http_methods]
                by_route[route.id] = values
                by_app.setdefault((route.owner_module_id, route.framework, route.binding), []).extend(values)
        graph = CodeGraph()
        for entity in endpoints.graph.entities():
            graph.add_entity(entity)
        for edge in endpoints.graph.relationships():
            graph.add_relationship(edge)
        outcomes = []
        for p in index.pre_handler_observations:
            if p.id != _pre_id(p):
                raise FrameworkResolutionInvariantError("pre-handler identity is invalid")
            if p.route_observation_id:
                route = routes[p.route_observation_id]
                eligible = by_route.get(route.id, [])
            else:
                eligible = by_app.get((p.owner_module_id, p.framework, p.binding), [])
            witness = symbols.imports[p.binding.import_entity_id]
            if not eligible or witness.status is not ImportResolutionStatus.UNRESOLVED:
                outcome = HttpEndpointResolution(p.id, Status.UNSUPPORTED, None, (), "unsupported_framework_or_route")
            else:
                outcome = _pre_resolution(p, symbols)
            outcomes.append(outcome)
            if outcome.status is Status.RESOLVED:
                for endpoint in eligible:
                    graph.add_relationship(_pre_edge(p, endpoint, outcome))
        analysis = FrameworkAnalysisResult(graph, endpoints.observations, endpoints.endpoints, endpoints.resolutions)
        return FrameworkFlowResult(analysis, index.pre_handler_observations, tuple(outcomes))
    except (GraphError, TypeError, ValueError) as error:
        raise FrameworkResolutionInvariantError("invalid snapshot for framework flow") from error
