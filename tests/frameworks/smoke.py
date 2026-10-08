"""Local reproducible HTTP indexing/trace smoke; executes no target source."""

from arctrellis.core import RelationshipKind

from .fixtures import http_sources
from .test_endpoints import analyze


def main() -> None:
    index, _, _, result = analyze(http_sources())
    repeated_index, _, _, repeated = analyze(http_sources())
    print(
        f"supported={index.supported_file_count} complete={index.complete_file_count} "
        f"partial={index.partial_file_count} failed={index.failed_file_count}"
    )
    print(
        f"observations={result.observation_count} endpoints={result.endpoint_count} "
        f"resolved_handlers={result.resolved_handler_count} unresolved_handlers={result.unresolved_handler_count} "
        f"ambiguous_handlers={result.ambiguous_handler_count} unsupported={result.unsupported_count}"
    )
    print("EXPOSES=" + str(sum(r.kind is RelationshipKind.EXPOSES for r in result.graph.relationships())))
    print(
        "deterministic="
        + str(
            index.route_observations == repeated_index.route_observations
            and result.resolutions == repeated.resolutions
            and result.graph.entities() == repeated.graph.entities()
            and result.graph.relationships() == repeated.graph.relationships()
        )
    )
    endpoint = next(e for e in result.endpoints if e.name == "POST /payments")
    target = next(e for e in result.graph.entities() if e.name == "validate_payment")
    path = result.graph.shortest_path(endpoint.id, target.id)
    assert path is not None
    for edge in path.relationships:
        source = result.graph.get_entity(edge.source_entity_id)
        target_entity = result.graph.get_entity(edge.target_entity_id)
        proof = edge.evidence[0]
        print(f"{source.qualified_name} {edge.kind.value} {target_entity.qualified_name}")
        print(
            f"evidence={proof.location.file_path}:{proof.location.start_line}-{proof.location.end_line} "
            f"method={proof.analysis_method} confidence={edge.confidence.value} score={edge.confidence_score}"
        )
        print("coordinates=" + repr(dict(proof.metadata)))


if __name__ == "__main__":
    main()
