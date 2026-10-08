"""Bounded same-file path composition with multi-source proof and stable identity."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from arctrellis.core import CodeEntity, Confidence, EntityKind, Evidence, Relationship, RelationshipKind
from arctrellis.extraction.source import _location, _span_metadata
from arctrellis.graph import CodeGraph

from .composition_models import RouterMountObservation, RouterMountResolution, RouterPrefixObservation
from .flow_models import FrameworkFlowResult
from .ids import _identity
from .models import EndpointResolutionStatus as Status
from .models import Framework, FrameworkAnalysisResult

if TYPE_CHECKING:
    from arctrellis.indexing import RepositoryIndexResult
    from arctrellis.resolution import ImportResolutionResult


def join_http_paths(prefix: str, route: str) -> str:
    """Join boundary slashes only; preserve the route's trailing slash/parameters.

    No URL decoding, interior normalization or filesystem path interpretation.
    Prefix may be empty; route must start with slash.
    """
    if not isinstance(prefix, str) or not isinstance(route, str):
        raise TypeError("HTTP path components must be strings")
    if prefix and not prefix.startswith("/") or not route.startswith("/"):
        raise ValueError("HTTP paths must be slash-prefixed (prefix may be empty)")
    return prefix.rstrip("/") + "/" + route.lstrip("/")


def _proofs(prefix: RouterPrefixObservation, mount: RouterMountObservation | None) -> tuple[Evidence, ...]:
    framework = prefix.framework.value
    facts = [(prefix.path, prefix.span, framework + "_router_constructor")]
    if prefix.prefix_span is not None:
        facts.append((prefix.path, prefix.prefix_span, framework + "_router_prefix"))
    if mount is not None:
        facts.extend(
            (
                (mount.path, mount.binding.span, framework + "_application_constructor"),
                (mount.path, mount.span, framework + "_router_mount"),
            )
        )
    return tuple(
        Evidence(
            _identity(
                "arctrellis-router-proof-v1",
                prefix.id,
                None if mount is None else mount.id,
                method,
                _span_metadata(span),
            ),
            _location(path, span),
            method,
            _span_metadata(span),
        )
        for path, span, method in facts
    )


def _effective(
    local: CodeEntity, prefix: RouterPrefixObservation, mount: RouterMountObservation | None, route_path: str
) -> CodeEntity:
    registration = prefix if mount is None else mount
    meta = dict(local.metadata)
    method = meta["http_method"]
    qualified = f"{registration.path}::http:{method}:{route_path}:effective@{registration.span.start_byte}:{local.id}"
    identity = _identity(
        "arctrellis-effective-http-v1",
        prefix.framework.value,
        registration.language.value,
        registration.path,
        method,
        route_path,
        local.id,
        prefix.id,
        None if mount is None else mount.id,
    )
    metadata = (
        _span_metadata(registration.span)
        + tuple(
            (k, v)
            for k, v in local.metadata
            if k not in dict(_span_metadata(registration.span)) and k not in ("route_path", "path_completeness")
        )
        + (
            ("route_path", route_path),
            ("path_completeness", "effective"),
            ("composition_scope", "router" if mount is None else "application"),
            ("local_endpoint_id", local.id),
            ("router_prefix_observation_id", prefix.id),
            ("mount_observation_id", "" if mount is None else mount.id),
        )
    )
    return CodeEntity(
        identity,
        EntityKind.API_ENDPOINT,
        f"{method} {route_path}",
        qualified,
        registration.location,
        registration.owner_module_id,
        registration.language.value,
        metadata,
    )


def _derive(
    graph: CodeGraph,
    local: CodeEntity,
    prefix: RouterPrefixObservation,
    mount: RouterMountObservation | None,
    path: str,
    base: CodeGraph,
) -> CodeEntity:
    endpoint = _effective(local, prefix, mount, path)
    graph.add_entity(endpoint)
    proofs = _proofs(prefix, mount)
    defines = next(
        r for r in base.incoming(local.id, kind=RelationshipKind.DEFINES) if r.source_entity_id == local.parent_id
    )
    evidence = defines.evidence + proofs
    graph.add_relationship(
        Relationship(
            _identity("arctrellis-composed-defines-v1", endpoint.id, tuple(e.id for e in evidence)),
            endpoint.parent_id or "",
            RelationshipKind.DEFINES,
            endpoint.id,
            Confidence.PROVEN,
            1.0,
            evidence,
        )
    )
    for edge in base.outgoing(local.id):
        if edge.kind not in (RelationshipKind.EXPOSES, RelationshipKind.APPLIES_MIDDLEWARE):
            continue
        graph.add_relationship(
            replace(
                edge,
                id=_identity("arctrellis-composed-flow-v1", edge.id, endpoint.id),
                source_entity_id=endpoint.id,
                evidence=edge.evidence + proofs,
            )
        )
    return endpoint


def compose_router_paths(
    index: RepositoryIndexResult, imports: ImportResolutionResult, flow: FrameworkFlowResult
) -> FrameworkFlowResult:
    """Derive paths from static same-file witnesses; never recurse or read sources."""
    from arctrellis.resolution import ImportResolutionStatus

    import_decisions = {d.import_entity_id: d for d in imports.resolutions}
    inventory_paths = {f.path for f in index.inventory.supported_files}

    def supported(framework: Framework, import_id: str) -> bool:
        if import_decisions[import_id].status is not ImportResolutionStatus.UNRESOLVED:
            return False
        return framework is Framework.EXPRESS or not (
            {f"{start}fastapi{end}" for start in ("", "src/") for end in (".py", "/__init__.py")} & inventory_paths
        )

    by_name: dict[tuple[str, Framework, str], list[RouterPrefixObservation]] = {}
    route_endpoints: dict[tuple[str, Framework, object], list[CodeEntity]] = {}
    for p in index.router_prefix_observations:
        by_name.setdefault((p.owner_module_id, p.framework, p.binding.name), []).append(p)
    endpoints_by_site: dict[tuple[str | None, str | None, str | None], list[CodeEntity]] = {}
    for endpoint in flow.local_endpoints:
        metadata = dict(endpoint.metadata)
        endpoints_by_site.setdefault(
            (endpoint.parent_id, metadata.get("registration_kind"), metadata.get("start_byte")), []
        ).append(endpoint)
    for route in flow.route_observations:
        key = (route.owner_module_id, route.framework, route.binding)
        route_endpoints.setdefault(key, []).extend(
            endpoints_by_site.get((route.owner_module_id, route.registration_kind, str(route.span.start_byte)), [])
        )
    graph = CodeGraph()
    for entity in flow.graph.entities():
        graph.add_entity(entity)
    for edge in flow.graph.relationships():
        graph.add_relationship(edge)
    outcomes = []
    derived = []
    attempted: set[str] = set()
    for mount in index.router_mount_observations:
        candidates = (
            by_name.get((mount.owner_module_id, mount.framework, mount.router_reference[0]), [])
            if len(mount.router_reference) == 1
            else []
        )
        attempted.update(p.id for p in candidates)
        expected_constructor = "FastAPI" if mount.framework is Framework.FASTAPI else "express"
        ids = tuple(sorted(p.id for p in candidates))
        if (
            mount.binding.constructor != expected_constructor
            or mount.prefix is None
            or not supported(mount.framework, mount.binding.import_entity_id)
        ):
            decision = RouterMountResolution(mount.id, Status.UNSUPPORTED, None, (), "unsupported_mount_configuration")
        elif len(candidates) > 1:
            decision = RouterMountResolution(mount.id, Status.AMBIGUOUS, None, ids, "multiple_router_bindings")
        elif not candidates:
            decision = RouterMountResolution(mount.id, Status.UNRESOLVED, None, (), "no_same_file_router_binding")
        elif (
            candidates[0].prefix is None
            or candidates[0].span.end_byte > mount.span.start_byte
            or not supported(candidates[0].framework, candidates[0].binding.import_entity_id)
        ):
            decision = RouterMountResolution(mount.id, Status.UNSUPPORTED, None, (), "unsupported_router_configuration")
        else:
            p = candidates[0]
            decision = RouterMountResolution(mount.id, Status.RESOLVED, p.id, (p.id,), "unique_static_router_binding")
            assert p.prefix is not None and mount.prefix is not None
            for local in route_endpoints.get((p.owner_module_id, p.framework, p.binding), []):
                # Limit this static subset to declarations preceding include.
                # Framework-version lifecycle differences are not emulated.
                if (
                    mount.framework is Framework.FASTAPI
                    and int(dict(local.metadata)["end_byte"]) > mount.span.start_byte
                ):
                    continue
                local_path = dict(local.metadata)["route_path"]
                if local_path.startswith("//"):
                    continue
                route_path = join_http_paths(mount.prefix, join_http_paths(p.prefix, local_path))
                if route_path != dict(local.metadata)["route_path"]:
                    derived.append(_derive(graph, local, p, mount, route_path, flow.graph))
        outcomes.append(decision)
    for p in index.router_prefix_observations:
        if p.id in attempted or not p.prefix or not supported(p.framework, p.binding.import_entity_id):
            continue
        for local in route_endpoints.get((p.owner_module_id, p.framework, p.binding), []):
            local_path = dict(local.metadata)["route_path"]
            if local_path.startswith("//"):
                continue
            route_path = join_http_paths(p.prefix, local_path)
            if route_path != dict(local.metadata)["route_path"]:
                derived.append(_derive(graph, local, p, None, route_path, flow.graph))
    analysis = FrameworkAnalysisResult(
        graph, flow.route_observations, flow.local_endpoints + tuple(derived), flow.endpoint_resolutions
    )
    return FrameworkFlowResult(
        analysis,
        flow.pre_handler_observations,
        flow.pre_handler_resolutions,
        index.router_prefix_observations,
        index.router_mount_observations,
        tuple(outcomes),
    )
