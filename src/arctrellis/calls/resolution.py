"""Indexed lexical and import-assisted target matching, without source I/O."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from arctrellis.core import CodeEntity, Confidence, EntityKind, Evidence, Relationship, RelationshipKind
from arctrellis.extraction.source import _span_metadata
from arctrellis.graph import CodeGraph, GraphError

from .errors import CallResolutionInvariantError
from .ids import _identity
from .models import CalleeKind, CallResolution, CallResolutionResult, CallResolutionStatus, CallSite

if TYPE_CHECKING:
    from arctrellis.indexing import RepositoryIndexResult
    from arctrellis.resolution.models import ImportResolution, ImportResolutionResult


@dataclass(slots=True)
class _Symbols:
    entities: dict[str, CodeEntity]
    functions: dict[tuple[str | None, str], list[CodeEntity]]
    methods: dict[tuple[str | None, str], list[CodeEntity]]
    imports: dict[tuple[str | None, str], list[CodeEntity]]
    import_decisions: dict[str, ImportResolution]


def _choose(site: CallSite, candidates: list[CodeEntity], method: str, reason: str) -> CallResolution:
    ids = tuple(sorted(e.id for e in candidates))
    if len(ids) == 1:
        return CallResolution(site.id, CallResolutionStatus.RESOLVED, ids[0], ids, reason, method)
    if ids:
        return CallResolution(site.id, CallResolutionStatus.AMBIGUOUS, None, ids, "multiple_" + reason)
    return CallResolution(site.id, CallResolutionStatus.UNRESOLVED, None, (), "no_" + reason)


def _unresolved(site: CallSite, reason: str) -> CallResolution:
    return CallResolution(site.id, CallResolutionStatus.UNRESOLVED, None, (), reason)


def _ancestors(owner: CodeEntity, symbols: _Symbols) -> list[CodeEntity]:
    scopes = []
    seen = set()
    current: CodeEntity | None = owner
    while current is not None:
        if current.id in seen:
            raise CallResolutionInvariantError("cyclic lexical parentage")
        seen.add(current.id)
        scopes.append(current)
        if current.kind is EntityKind.MODULE:
            break
        if current.parent_id is None or current.parent_id not in symbols.entities:
            raise CallResolutionInvariantError("dangling lexical parentage")
        current = symbols.entities[current.parent_id]
    return scopes


def _imported(site: CallSite, bindings: list[CodeEntity], symbols: _Symbols, prefix: str) -> CallResolution:
    from arctrellis.resolution.models import ImportResolutionStatus

    if len(bindings) > 1:
        return _choose(site, bindings, "", "visible_bindings")
    binding = bindings[0]
    metadata = dict(binding.metadata)
    if metadata.get("is_type_only") == "true":
        return _unresolved(site, "type_only_import")
    decision = symbols.import_decisions[binding.id]
    if decision.status is not ImportResolutionStatus.RESOLVED:
        return _unresolved(site, "import_" + decision.status.value)
    form = metadata.get("import_form")
    if site.callee_kind is CalleeKind.NAME:
        if form not in ("from", "named") or metadata.get("imported_name") in (None, "", "*"):
            return _unresolved(site, "unsupported_callable_import")
        name = metadata["imported_name"]
        method = prefix + "_imported_symbol_call_resolution"
    else:
        if form not in ("import", "namespace", "require"):
            return _unresolved(site, "unsupported_module_binding")
        if form == "import" and not metadata.get("alias") and metadata.get("module") != metadata.get("binding"):
            return _unresolved(site, "unaliased_dotted_module_binding")
        name = site.callee_parts[1]
        method = prefix + "_imported_module_member_resolution"
    return _choose(site, symbols.functions.get((decision.target_module_id, name), []), method, "imported_function")


def _resolve(site: CallSite, symbols: _Symbols) -> CallResolution:
    owner = symbols.entities[site.owner_entity_id]
    prefix = "python" if site.language.value == "python" else "ecmascript"
    if len(site.callee_parts) > 2:
        return _unresolved(site, "long_member_chain")
    root = site.callee_parts[0]
    special = ("self", "cls") if prefix == "python" else ("this",)
    if site.callee_kind is CalleeKind.MEMBER and root in special:
        parent = symbols.entities.get(owner.parent_id) if owner.parent_id else None
        if owner.kind is not EntityKind.METHOD or parent is None or parent.kind is not EntityKind.CLASS:
            return _unresolved(site, "not_direct_method_scope")
        return _choose(
            site,
            symbols.methods.get((parent.id, site.callee_parts[1]), []),
            prefix + "_same_class_method_resolution",
            "same_class_method",
        )
    if root == "super":
        return _unresolved(site, "super_dispatch_deferred")
    for scope in _ancestors(owner, symbols):
        if scope.kind is EntityKind.CLASS:
            # Class declarations do not establish function closures; static-block
            # locals likewise are not visible to ECMAScript methods.
            continue
        functions = symbols.functions.get((scope.id, root), []) if site.callee_kind is CalleeKind.NAME else []
        bindings = symbols.imports.get((scope.id, root), [])
        if functions and bindings:
            return _choose(site, functions + bindings, "", "visible_bindings")
        if functions:
            return _choose(site, functions, prefix + "_lexical_call_resolution", "lexical_function")
        if bindings:
            return _imported(site, bindings, symbols, prefix)
    return _unresolved(site, "no_visible_callable_binding")


def _edge(site: CallSite, decision: CallResolution) -> Relationship:
    method, target = decision.resolution_method, decision.target_entity_id
    assert method is not None and target is not None
    coordinates = _span_metadata(site.span)
    evidence = Evidence(
        _identity("arctrellis-call-evidence-v1", site.id, target, method, coordinates),
        site.location,
        method,
        coordinates,
    )
    return Relationship(
        _identity(
            "arctrellis-call-edge-v1", RelationshipKind.CALLS.value, site.owner_entity_id, target, site.id, method
        ),
        site.owner_entity_id,
        RelationshipKind.CALLS,
        target,
        Confidence.LIKELY,
        0.75 if "_imported_" in method else 0.85,
        (evidence,),
    )


def resolve_calls(index: RepositoryIndexResult, imports: ImportResolutionResult) -> CallResolutionResult:
    """Return independent graph and decisions; no parsing, reads or import rerun.

    Lexical/same-class edges are LIKELY/0.85; import-assisted edges LIKELY/0.75.
    Unknown and ambiguous targets have no graph edge. Assignment/parameter
    shadowing and runtime mutation are not modeled; these are static heuristics.
    """
    # Runtime import here avoids indexing -> observation API -> resolver -> indexing cycles.
    from arctrellis.indexing import RepositoryIndexResult
    from arctrellis.resolution.imports import _import_edge
    from arctrellis.resolution.models import ImportResolutionResult

    if not isinstance(index, RepositoryIndexResult) or not isinstance(imports, ImportResolutionResult):
        raise TypeError("call resolution requires repository and import result snapshots")
    try:
        RepositoryIndexResult(
            index.inventory,
            index.graph,
            index.file_results,
            index.call_sites,
            index.route_observations,
            index.pre_handler_observations,
            index.router_prefix_observations,
            index.router_mount_observations,
        )
        ImportResolutionResult(imports.graph, imports.resolutions)
        entities = {e.id: e for e in index.graph.entities()}
        if imports.graph.entities() != index.graph.entities():
            raise CallResolutionInvariantError("import graph does not match repository entities")
        if any(
            not imports.graph.has_relationship(e.id) or imports.graph.get_relationship(e.id) != e
            for e in index.graph.relationships()
        ):
            raise CallResolutionInvariantError("import graph does not preserve repository relationships")
        base_ids = {e.id for e in index.graph.relationships()}
        if any(e.kind is not RelationshipKind.IMPORTS for e in imports.graph.relationships() if e.id not in base_ids):
            raise CallResolutionInvariantError("import graph contains non-import analysis edges")
        decisions = {r.import_entity_id: r for r in imports.resolutions}
        if set(decisions) != {e.id for e in entities.values() if e.kind is EntityKind.IMPORT}:
            raise CallResolutionInvariantError("import decisions do not match indexed sites")
        expected_edges = set()
        for d in decisions.values():
            for candidate in d.candidate_module_ids:
                module = entities.get(candidate)
                if module is None or module.kind is not EntityKind.MODULE:
                    raise CallResolutionInvariantError("import candidate must be an indexed module")
            if d.target_module_id is not None:
                target = entities.get(d.target_module_id)
                if target is None or target.kind is not EntityKind.MODULE:
                    raise CallResolutionInvariantError("import resolution target must be an indexed module")
                expected = _import_edge(entities[d.import_entity_id], d.target_module_id)
                if (
                    not imports.graph.has_relationship(expected.id)
                    or imports.graph.get_relationship(expected.id) != expected
                ):
                    raise CallResolutionInvariantError("import decisions do not match import-site evidence")
                expected_edges.add(expected.id)
        if expected_edges != {e.id for e in imports.graph.relationships() if e.id not in base_ids}:
            raise CallResolutionInvariantError("import graph does not match resolved site count")
        symbols = _Symbols(entities, {}, {}, {}, decisions)
        for entity in entities.values():
            if entity.kind is EntityKind.FUNCTION:
                symbols.functions.setdefault((entity.parent_id, entity.name), []).append(entity)
            elif entity.kind is EntityKind.METHOD:
                symbols.methods.setdefault((entity.parent_id, entity.name), []).append(entity)
            elif entity.kind is EntityKind.IMPORT:
                binding = dict(entity.metadata).get("binding", "")
                if binding:
                    symbols.imports.setdefault((entity.parent_id, binding), []).append(entity)
        graph = CodeGraph()
        for entity in imports.graph.entities():
            graph.add_entity(entity)
        for relationship in imports.graph.relationships():
            graph.add_relationship(relationship)
        outcomes = []
        for site in index.call_sites:
            outcome = _resolve(site, symbols)
            outcomes.append(outcome)
            if outcome.status is CallResolutionStatus.RESOLVED:
                graph.add_relationship(_edge(site, outcome))
        return CallResolutionResult(graph, tuple(outcomes))
    except (GraphError, TypeError, ValueError) as error:
        raise CallResolutionInvariantError("invalid snapshot for call resolution") from error
