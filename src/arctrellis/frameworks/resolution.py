"""Endpoint entities and evidence-backed handler edges from retained observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from arctrellis.core import CodeEntity, Confidence, EntityKind, Evidence, Relationship, RelationshipKind
from arctrellis.extraction import make_entity_id
from arctrellis.extraction.models import _entity_span
from arctrellis.extraction.source import _span_metadata
from arctrellis.graph import CodeGraph, GraphError

from .errors import FrameworkResolutionInvariantError
from .extraction import _constructor_import
from .ids import _identity, _observation_id
from .models import EndpointResolutionStatus as Status
from .models import Framework, FrameworkAnalysisResult, HttpEndpointResolution, HttpRouteObservation

if TYPE_CHECKING:
    from arctrellis.calls import CallResolutionResult
    from arctrellis.indexing import RepositoryIndexResult
    from arctrellis.resolution import ImportResolution, ImportResolutionResult


@dataclass(slots=True)
class _HandlerIndex:
    entities: dict[str, CodeEntity]
    functions: dict[tuple[str | None, str], list[CodeEntity]]
    bindings: dict[tuple[str | None, str], list[CodeEntity]]
    declarations: dict[tuple[str, int, int], list[CodeEntity]]
    imports: dict[str, ImportResolution]


def _validate_snapshots(
    index: RepositoryIndexResult, imports: ImportResolutionResult, calls: CallResolutionResult
) -> None:
    from arctrellis.calls import CallResolutionResult
    from arctrellis.calls.resolution import _edge
    from arctrellis.indexing import RepositoryIndexResult
    from arctrellis.resolution import ImportResolutionResult
    from arctrellis.resolution.imports import _import_edge

    if (
        not isinstance(index, RepositoryIndexResult)
        or not isinstance(imports, ImportResolutionResult)
        or not isinstance(calls, CallResolutionResult)
    ):
        raise TypeError("endpoint resolution requires repository/import/call snapshots")
    RepositoryIndexResult(
        index.inventory,
        index.graph,
        index.file_results,
        index.call_sites,
        index.route_observations,
        index.pre_handler_observations,
        index.router_prefix_observations,
        index.router_mount_observations,
        index.test_observations,
    )
    ImportResolutionResult(imports.graph, imports.resolutions)
    CallResolutionResult(calls.graph, calls.resolutions)
    entities = {e.id: e for e in index.graph.entities()}
    if imports.graph.entities() != index.graph.entities() or calls.graph.entities() != index.graph.entities():
        raise FrameworkResolutionInvariantError("analysis entities must match repository snapshot")
    expected_imports = {e.id: e for e in index.graph.relationships()}
    decisions = {d.import_entity_id: d for d in imports.resolutions}
    if set(decisions) != {e.id for e in entities.values() if e.kind is EntityKind.IMPORT}:
        raise FrameworkResolutionInvariantError("import decisions must match indexed sites")
    for decision in decisions.values():
        if any(c not in entities or entities[c].kind is not EntityKind.MODULE for c in decision.candidate_module_ids):
            raise FrameworkResolutionInvariantError("import candidates must be indexed modules")
        if decision.target_module_id is not None:
            edge = _import_edge(entities[decision.import_entity_id], decision.target_module_id)
            expected_imports[edge.id] = edge
    if imports.graph.relationships() != tuple(expected_imports[k] for k in sorted(expected_imports)):
        raise FrameworkResolutionInvariantError("import decisions and graph proof disagree")
    expected_calls = dict(expected_imports)
    sites = {s.id: s for s in index.call_sites}
    if tuple(r.call_site_id for r in calls.resolutions) != tuple(s.id for s in index.call_sites):
        raise FrameworkResolutionInvariantError("call decisions must match indexed site order")
    for call_decision in calls.resolutions:
        if call_decision.target_entity_id is not None:
            target = entities.get(call_decision.target_entity_id)
            if target is None or target.kind not in (EntityKind.FUNCTION, EntityKind.METHOD):
                raise FrameworkResolutionInvariantError("call target must be an indexed callable")
            edge = _edge(sites[call_decision.call_site_id], call_decision)
            expected_calls[edge.id] = edge
    if calls.graph.relationships() != tuple(expected_calls[k] for k in sorted(expected_calls)):
        raise FrameworkResolutionInvariantError("call decisions and graph proof disagree")


def _choose_reference(observation_id: str, candidates: list[CodeEntity], method: str) -> HttpEndpointResolution:
    ids = tuple(sorted(e.id for e in candidates))
    if len(ids) == 1:
        return HttpEndpointResolution(observation_id, Status.RESOLVED, ids[0], ids, "unique_handler", method)
    if len(ids) > 1:
        return HttpEndpointResolution(observation_id, Status.AMBIGUOUS, None, ids, "multiple_handler_witnesses")
    return HttpEndpointResolution(observation_id, Status.UNRESOLVED, None, (), "no_handler_candidate")


def _choose(route: HttpRouteObservation, candidates: list[CodeEntity], method: str) -> HttpEndpointResolution:
    return _choose_reference(route.id, candidates, method)


def _handler(route: HttpRouteObservation, symbols: _HandlerIndex) -> HttpEndpointResolution:
    if route.route_path is None or not route.http_methods:
        return HttpEndpointResolution(route.id, Status.UNSUPPORTED, None, (), "unsupported_path_or_methods")
    if route.framework is not Framework.EXPRESS:
        span = route.handler_declaration_span
        candidates = [] if span is None else symbols.declarations.get((route.path, span.start_byte, span.end_byte), [])
        candidates = [e for e in candidates if (e.name,) == route.handler_reference]
        return _choose(route, candidates, route.framework.value + "_decorated_handler")
    return _reference_handler(
        route.id,
        route.owner_module_id,
        route.handler_reference,
        route.handler_binding_supported,
        route.framework,
        symbols,
    )


def _reference_handler(
    observation_id: str,
    owner_module_id: str,
    reference: tuple[str, ...],
    supported: bool,
    framework: Framework,
    symbols: _HandlerIndex,
) -> HttpEndpointResolution:
    from arctrellis.resolution import ImportResolutionStatus

    if not supported or not reference or len(reference) > 2:
        return HttpEndpointResolution(observation_id, Status.UNRESOLVED, None, (), "unsupported_handler_reference")
    functions = symbols.functions.get((owner_module_id, reference[0]), []) if len(reference) == 1 else []
    bindings = symbols.bindings.get((owner_module_id, reference[0]), [])
    if functions and bindings or len(bindings) > 1:
        return _choose_reference(observation_id, functions + bindings, framework.value + "_local_handler_resolution")
    if functions:
        return _choose_reference(observation_id, functions, framework.value + "_local_handler_resolution")
    if not bindings:
        return _choose_reference(observation_id, [], framework.value + "_local_handler_resolution")
    site = bindings[0]
    metadata = dict(site.metadata)
    decision = symbols.imports[site.id]
    if metadata.get("is_type_only") == "true" or decision.status is not ImportResolutionStatus.RESOLVED:
        return HttpEndpointResolution(observation_id, Status.UNRESOLVED, None, (), "non_runtime_or_unresolved_import")
    form = metadata.get("import_form")
    if len(reference) == 1 and form in ("named", "from"):
        name = metadata.get("imported_name", "")
    elif len(reference) == 2 and form in ("namespace", "require", "import"):
        name = reference[1]
    else:
        return HttpEndpointResolution(observation_id, Status.UNRESOLVED, None, (), "unsupported_handler_import")
    if form == "import" and not metadata.get("alias") and metadata.get("module") != metadata.get("binding"):
        return HttpEndpointResolution(observation_id, Status.UNRESOLVED, None, (), "unsupported_dotted_import")
    candidates = symbols.functions.get((decision.target_module_id, name), [])
    # Express imports require an explicit directly exported declaration. Re-export
    # lists/default exports and CommonJS export assignments are not resolved here.
    if framework is Framework.EXPRESS:
        candidates = [
            e
            for e in candidates
            if dict(e.metadata).get("is_exported") == "true" and dict(e.metadata).get("is_default_export") != "true"
        ]
    return _choose_reference(observation_id, candidates, framework.value + "_imported_handler_resolution")


def _endpoint(route: HttpRouteObservation, method: str) -> CodeEntity:
    assert route.route_path is not None
    qualified = f"{route.path}::http:{method}:{route.route_path}@{route.span.start_byte}"
    metadata = _span_metadata(route.span) + (
        ("framework", route.framework.value),
        ("http_method", method),
        ("route_path", route.route_path),
        ("registration_kind", route.registration_kind),
        ("path_completeness", route.binding.path_completeness),
        ("pre_handler_argument_count", str(route.pre_handler_argument_count)),
    )
    return CodeEntity(
        make_entity_id(
            language=route.language,
            path=route.path,
            kind=EntityKind.API_ENDPOINT,
            qualified_name=qualified,
            start_byte=route.span.start_byte,
            end_byte=route.span.end_byte,
        ),
        EntityKind.API_ENDPOINT,
        f"{method} {route.route_path}",
        qualified,
        route.location,
        route.owner_module_id,
        route.language.value,
        metadata,
    )


def _relationship(
    route: HttpRouteObservation, endpoint: CodeEntity, decision: HttpEndpointResolution | None
) -> Relationship:
    if decision is None:
        kind, source, target = RelationshipKind.DEFINES, route.owner_module_id, endpoint.id
        method = (
            "express_route_registration"
            if route.framework is Framework.EXPRESS
            else route.framework.value + "_route_declaration"
        )
        confidence, score = Confidence.PROVEN, 1.0
    else:
        assert decision.handler_entity_id is not None and decision.resolution_method is not None
        kind, source, target = RelationshipKind.EXPOSES, endpoint.id, decision.handler_entity_id
        method = decision.resolution_method
        confidence = Confidence.LIKELY if route.framework is Framework.EXPRESS else Confidence.PROVEN
        score = (
            (0.75 if method == "express_imported_handler_resolution" else 0.85)
            if confidence is Confidence.LIKELY
            else 1.0
        )
    coordinates = _span_metadata(route.span)
    evidence = Evidence(
        _identity("arctrellis-http-evidence-v1", kind.value, source, target, route.id, method, coordinates),
        route.location,
        method,
        coordinates,
    )
    return Relationship(
        _identity("arctrellis-http-edge-v1", kind.value, source, target, route.id, method),
        source,
        kind,
        target,
        confidence,
        score,
        (evidence,),
    )


def _handler_index(index: RepositoryIndexResult, imports: ImportResolutionResult) -> _HandlerIndex:
    entities = {e.id: e for e in index.graph.entities()}
    symbols = _HandlerIndex(entities, {}, {}, {}, {r.import_entity_id: r for r in imports.resolutions})
    for entity in entities.values():
        if entity.kind is EntityKind.FUNCTION:
            symbols.functions.setdefault((entity.parent_id, entity.name), []).append(entity)
        if entity.kind in (EntityKind.FUNCTION, EntityKind.METHOD):
            span = _entity_span(entity)
            assert entity.location is not None
            symbols.declarations.setdefault((entity.location.file_path, span.start_byte, span.end_byte), []).append(
                entity
            )
        elif entity.kind is EntityKind.IMPORT:
            name = dict(entity.metadata).get("binding", "")
            if name:
                symbols.bindings.setdefault((entity.parent_id, name), []).append(entity)
    return symbols


def resolve_http_endpoints(
    index: RepositoryIndexResult, imports: ImportResolutionResult, calls: CallResolutionResult
) -> FrameworkAnalysisResult:
    """Add endpoint/handler proof to an independent graph without source rereads.

    Handler counts refer to observations, not the expanded HTTP-method endpoints.
    Unresolved/ambiguous static registrations still receive endpoint entities.
    """
    from arctrellis.resolution import ImportResolutionStatus

    try:
        _validate_snapshots(index, imports, calls)
        entities = {e.id: e for e in index.graph.entities()}
        inventory_paths = {file.path for file in index.inventory.supported_files}
        symbols = _handler_index(index, imports)
        graph = CodeGraph()
        for entity in calls.graph.entities():
            graph.add_entity(entity)
        for relationship in calls.graph.relationships():
            graph.add_relationship(relationship)
        outcomes, endpoints = [], []
        for route in index.route_observations:
            witness = entities.get(route.binding.import_entity_id)
            constructor = None if witness is None else _constructor_import(witness)
            if (
                witness is None
                or witness.kind is not EntityKind.IMPORT
                or witness.parent_id != route.owner_module_id
                or constructor is None
                or constructor[0] is not route.framework
                or route.id != _observation_id(route)
                or route.binding.constructor
                not in (("express", "Router") if route.framework is Framework.EXPRESS else (constructor[1],))
            ):
                raise FrameworkResolutionInvariantError("route constructor provenance/identity is invalid")
            dependency = symbols.imports[route.binding.import_entity_id]
            module_name = route.framework.value
            internal_paths = (
                {f"{prefix}{module_name}{suffix}" for prefix in ("", "src/") for suffix in (".py", "/__init__.py")}
                if route.framework is not Framework.EXPRESS
                else set()
            )
            if dependency.status is not ImportResolutionStatus.UNRESOLVED or internal_paths & inventory_paths:
                outcome = HttpEndpointResolution(
                    route.id, Status.UNSUPPORTED, None, (), "internal_framework_name_collision"
                )
            else:
                outcome = _handler(route, symbols)
            outcomes.append(outcome)
            if outcome.status is Status.UNSUPPORTED:
                continue
            for method in route.http_methods:
                endpoint = _endpoint(route, method)
                endpoints.append(endpoint)
                graph.add_entity(endpoint)
                graph.add_relationship(_relationship(route, endpoint, None))
                if outcome.status is Status.RESOLVED:
                    graph.add_relationship(_relationship(route, endpoint, outcome))
        return FrameworkAnalysisResult(graph, index.route_observations, tuple(endpoints), tuple(outcomes))
    except (GraphError, TypeError, ValueError) as error:
        raise FrameworkResolutionInvariantError("invalid snapshot for framework resolution") from error
