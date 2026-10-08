"""Conservative module dependency edges; no imported-symbol resolution."""

from arctrellis.core import CodeEntity, Confidence, EntityKind, Evidence, Relationship, RelationshipKind
from arctrellis.graph import CodeGraph, GraphError
from arctrellis.indexing import RepositoryIndexInvariantError, RepositoryIndexResult
from arctrellis.indexing.ids import _stable_id

from .catalog import _catalog, _python_candidates, _script_candidates
from .models import ImportResolution, ImportResolutionResult, ImportResolutionStatus


def _import_edge(site: CodeEntity, target: str) -> Relationship:
    if site.parent_id is None or site.location is None:
        raise RepositoryIndexInvariantError("indexed import requires lexical owner and source evidence")
    method = "python_static_import_resolution" if site.language == "python" else "ecmascript_relative_import_resolution"
    coordinates = tuple(
        (k, v)
        for k, v in site.metadata
        if k in ("start_byte", "end_byte", "start_line", "start_column", "end_line", "end_column")
    )
    evidence = Evidence(
        _stable_id("arctrellis-import-evidence-v1", method, site.id, site.parent_id, target, coordinates),
        site.location,
        method,
        coordinates,
    )
    return Relationship(
        _stable_id("arctrellis-import-edge-v1", RelationshipKind.IMPORTS.value, site.parent_id, target, site.id),
        site.parent_id,
        RelationshipKind.IMPORTS,
        target,
        Confidence.LIKELY,
        0.90,
        (evidence,),
    )


def resolve_imports(index: RepositoryIndexResult) -> ImportResolutionResult:
    """Return new graph and one explicit decision per import, sorted by site ID.

    Uses indexed source paths/metadata only. Successful static matches are LIKELY,
    never runtime proof. Bare JS aliases and ambiguous candidates emit no edge.
    """
    if not isinstance(index, RepositoryIndexResult):
        raise TypeError("index must be RepositoryIndexResult")
    graph = CodeGraph()
    decisions = []
    try:
        RepositoryIndexResult(index.inventory, index.graph, index.file_results)
        for entity in index.graph.entities():
            graph.add_entity(entity)
        for edge in index.graph.relationships():
            graph.add_relationship(edge)
        modules = tuple(e for e in graph.entities() if e.kind is EntityKind.MODULE)
        python, script = _catalog(modules)
        for site in (e for e in graph.entities() if e.kind is EntityKind.IMPORT):
            if site.parent_id is None or site.location is None:
                raise RepositoryIndexInvariantError("indexed import lacks owner/evidence")
            owner = graph.get_entity(site.parent_id)
            if owner.kind not in (EntityKind.MODULE, EntityKind.CLASS, EntityKind.FUNCTION, EntityKind.METHOD):
                raise RepositoryIndexInvariantError("indexed import has invalid lexical owner")
            if site.language == "python":
                candidates, reason = _python_candidates(site, python)
            elif site.language in ("javascript", "typescript"):
                candidates, reason = _script_candidates(site, script)
            else:
                candidates, reason = (), "unsupported_language"
            if len(candidates) == 1:
                target = candidates[0]
                decisions.append(
                    ImportResolution(site.id, ImportResolutionStatus.RESOLVED, target, candidates, "unique_module")
                )
                graph.add_relationship(_import_edge(site, target))
            elif candidates:
                decisions.append(
                    ImportResolution(site.id, ImportResolutionStatus.AMBIGUOUS, None, candidates, "multiple_modules")
                )
            else:
                decisions.append(ImportResolution(site.id, ImportResolutionStatus.UNRESOLVED, None, (), reason))
    except (GraphError, TypeError, ValueError) as error:
        raise RepositoryIndexInvariantError("invalid repository index for import resolution") from error
    return ImportResolutionResult(graph, tuple(decisions))
