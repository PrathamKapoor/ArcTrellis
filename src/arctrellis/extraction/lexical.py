"""Language-independent single-file lexical graph assembly."""

import json
from uuid import NAMESPACE_URL, uuid5

from arctrellis.core import CodeEntity, Confidence, Evidence, Relationship, RelationshipKind
from arctrellis.graph import CodeGraph

from .errors import SemanticExtractionError
from .models import ExtractionResult, _entity_span
from .source import _span_metadata

_METHOD = "lexical_parentage"


def _proof_id(marker: str, components: list[object]) -> str:
    """Use versioned, delimiter-safe identity without introducing repository scope."""
    key = json.dumps([marker, *components], ensure_ascii=True, separators=(",", ":"))
    return str(uuid5(NAMESPACE_URL, key))


def _lexical_relationship(parent: CodeEntity, child: CodeEntity) -> Relationship:
    span = _entity_span(child)
    coordinates = _span_metadata(span)
    location = child.location
    assert location is not None  # ExtractionResult requires source locations.
    evidence = Evidence(
        id=_proof_id(
            "arctrellis-lexical-evidence-v1",
            [_METHOD, parent.id, child.id, location.file_path, location.start_line, location.end_line, coordinates],
        ),
        location=location,
        analysis_method=_METHOD,
        metadata=coordinates,
    )
    return Relationship(
        id=_proof_id(
            "arctrellis-lexical-relationship-v1", [RelationshipKind.DEFINES.value, parent.id, child.id, evidence.id]
        ),
        source_entity_id=parent.id,
        kind=RelationshipKind.DEFINES,
        target_entity_id=child.id,
        confidence=Confidence.PROVEN,
        confidence_score=1.0,
        evidence=(evidence,),
    )


def build_lexical_graph(result: ExtractionResult) -> CodeGraph:
    """Return a fresh graph of entities and evidence-backed lexical DEFINES edges.

    Surviving declarations in a partial result retain proven parentage. Callers
    retain result.partial separately; this graph makes no file-completeness claim.
    No imports/calls/inheritance are resolved and no repository graph is merged.
    Identity is revision-deterministic, not edit-stable or repository-namespaced.
    """
    if not isinstance(result, ExtractionResult):
        raise TypeError("result must be ExtractionResult")
    try:
        # Reject corrupted producer output before constructing any graph.
        ExtractionResult(result.path, result.language, result.entities, result.partial)
    except (TypeError, ValueError) as error:
        raise SemanticExtractionError("invalid extraction result for lexical graph assembly") from error
    graph = CodeGraph()
    for entity in result.entities:
        graph.add_entity(entity)
    for child in result.entities[1:]:
        assert child.parent_id is not None  # ExtractionResult validates every child parent.
        parent = graph.get_entity(child.parent_id)
        graph.add_relationship(_lexical_relationship(parent, child))
    return graph
