"""Existing endpoint registration inventory; metadata is authoritative, never names."""

from arctrellis.core import CodeEntity, EntityKind
from arctrellis.graph import CodeGraph

from .models import AnalysisCompleteness, EntityQueryResult, validate_limits


def list_endpoints(
    graph: CodeGraph,
    *,
    http_method: str | None = None,
    framework: str | None = None,
    route_path: str | None = None,
    scope: str | None = None,
    max_results: int = 1000,
    max_expansions: int = 10000,
    analysis_completeness: AnalysisCompleteness = AnalysisCompleteness.UNKNOWN,
) -> EntityQueryResult:
    """Filter canonical metadata; scope is local/declared/effective/application or None.

    effective includes router configuration paths as well as application mounts;
    inspect composition_scope to distinguish them. Neither proves public deployment.
    No registration sites are merged or names parsed to fill absent metadata.
    """
    validate_limits(1, max_results, max_expansions)
    for value in (http_method, framework, route_path, scope):
        if value is not None and not isinstance(value, str):
            raise TypeError("endpoint filters must be strings or None")
    if scope not in (None, "local", "declared", "effective", "application"):
        raise ValueError("scope must be local, declared, effective, application or None")
    entities: list[CodeEntity] = []
    reasons: set[str] = set()
    expansions = 0
    for entity in graph.entities():
        if expansions == max_expansions:
            reasons.add("max_expansions")
            break
        expansions += 1
        if entity.kind is not EntityKind.API_ENDPOINT:
            continue
        metadata = dict(entity.metadata)
        if scope == "application" and metadata.get("composition_scope") != "application":
            continue
        if any(
            value is not None and metadata.get(key) != value
            for key, value in (
                ("http_method", http_method),
                ("framework", framework),
                ("route_path", route_path),
                ("path_completeness", "effective" if scope == "application" else scope),
            )
        ):
            continue
        if len(entities) == max_results:
            reasons.add("max_results")
            break
        entities.append(entity)
    return EntityQueryResult(
        "endpoints",
        tuple(entities),
        max_results,
        max_expansions,
        expansions,
        tuple(sorted(reasons)),
        analysis_completeness,
    )
