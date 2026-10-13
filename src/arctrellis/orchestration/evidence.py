"""Evidence-bundle assembly: the single explainable product of one request.

Every relationship in a bundle is the original stored record with its original
confidence and Evidence. Confidence is summarized, never multiplied: a bundle
contains no probability of runtime execution, no source content and no absolute
path (D-144).
"""

from __future__ import annotations

from arctrellis.core import CodeEntity, Evidence, Relationship
from arctrellis.query import EvidencePath, PathQueryResult
from arctrellis.retrieval import SearchHit

from .errors import OrchestrationInvariantError
from .execution import ExecutionOutcome, traversal_direction
from .models import (
    SCHEMA_VERSION,
    BundleStatus,
    EntityCandidate,
    EntitySummary,
    EvidenceBundle,
    EvidenceDetail,
    PathEvidence,
    QueryIntent,
    QueryPlan,
    RelationshipEvidence,
    SelectionBasis,
    SelectionResult,
    SelectionStatus,
)
from .pipeline import AnalysisSnapshot

#: Allowlisted canonical facts a bundle may expose. Entity metadata outside this
#: list, and every declaration signature, is deliberately omitted (D-144).
CANONICAL_FACT_FIELDS = (
    "http_method",
    "route_path",
    "framework",
    "path_completeness",
    "composition_scope",
    "provider",
    "operation_kind",
    "operation_name",
    "target_name",
)


def entity_summary(snapshot: AnalysisSnapshot, entity: CodeEntity) -> EntitySummary:
    """Summarize one canonical entity without its signature or arbitrary metadata."""
    document = snapshot.document(entity.id)
    if document is None:
        raise OrchestrationInvariantError(f"entity {entity.id!r} is missing from the retrieval snapshot")
    facts = tuple((name, value) for name in CANONICAL_FACT_FIELDS if (value := document.field_value(name)))
    return EntitySummary(
        entity_id=entity.id,
        entity_kind=entity.kind,
        name=entity.name,
        qualified_name=entity.qualified_name,
        language=entity.language,
        repository_relative_path=None if entity.location is None else entity.location.file_path,
        source_location=entity.location,
        canonical_facts=facts,
    )


def entity_candidate(
    snapshot: AnalysisSnapshot,
    entity: CodeEntity,
    basis: SelectionBasis,
    relevance_score: float | None = None,
    matched_fields: tuple[str, ...] = (),
) -> EntityCandidate:
    """Project a canonical entity into an explainable candidate record."""
    summary = entity_summary(snapshot, entity)
    return EntityCandidate(
        entity_id=summary.entity_id,
        name=summary.name,
        qualified_name=summary.qualified_name,
        entity_kind=summary.entity_kind,
        language=summary.language,
        repository_relative_path=summary.repository_relative_path,
        source_location=summary.source_location,
        basis=basis,
        relevance_score=relevance_score,
        matched_fields=matched_fields,
    )


def _evidence_detail(item: Evidence) -> EvidenceDetail:
    return EvidenceDetail(
        evidence_id=item.id,
        analysis_method=item.analysis_method,
        file_path=item.location.file_path,
        start_line=item.location.start_line,
        end_line=item.location.end_line,
        metadata=tuple(item.metadata),
    )


def _relationship_evidence(edge: Relationship) -> RelationshipEvidence:
    return RelationshipEvidence(
        relationship_id=edge.id,
        relationship_kind=edge.kind.value,
        source_entity_id=edge.source_entity_id,
        target_entity_id=edge.target_entity_id,
        confidence=edge.confidence.value,
        confidence_score=edge.confidence_score,
        evidence=tuple(_evidence_detail(item) for item in edge.evidence),
    )


def path_evidence(snapshot: AnalysisSnapshot, path: EvidencePath, result: PathQueryResult) -> PathEvidence:
    """Convert one validated evidence path into its stable bundle representation."""
    return PathEvidence(
        path_id=path.path_id,
        entities=tuple(entity_summary(snapshot, entity) for entity in path.entities),
        relationships=tuple(_relationship_evidence(edge) for edge in path.relationships),
        direction=traversal_direction(result),
        weakest_edge_score=path.weakest_edge_score,
        confidence_classification=(
            path.confidence_classification.value if path.confidence_classification is not None else None
        ),
    )


def _limitations(
    status: BundleStatus,
    selection: SelectionResult,
    completeness: str,
    retrieval_truncation: tuple[str, ...],
    graph_truncation: tuple[str, ...],
    graph_context_requested: bool,
) -> tuple[str, ...]:
    """Derive explicit, evidence-grounded limitations for this bundle."""
    found: set[str] = set()
    if status is BundleStatus.NO_KNOWN_PATH:
        found.add("no_known_path_is_not_proof_of_absence")
    if status is BundleStatus.AMBIGUOUS_SOURCE:
        found.add("ambiguous_source_selection_requires_an_exact_entity_id")
    if status is BundleStatus.NOT_FOUND_SOURCE:
        found.add("selected_source_entity_does_not_exist_in_the_snapshot")
    if status is BundleStatus.INVALID_SOURCE:
        found.add("selected_source_entity_kind_is_incompatible_with_the_intent")
    if status is BundleStatus.SEARCH_RESULTS:
        found.add("lexical_relevance_is_not_entity_identity")
        found.add("token_overlap_is_not_semantic_understanding")
    if completeness != "complete":
        found.add("source_analysis_was_partial_or_failed")
    if retrieval_truncation:
        found.add("retrieval_budget_truncated_candidate_examination")
    if graph_truncation:
        found.add("structural_query_budget_truncated_enumeration")
    if graph_context_requested:
        found.add("graph_context_is_a_structural_association_not_execution")
    return tuple(sorted(found))


def build_bundle(
    snapshot: AnalysisSnapshot,
    plan: QueryPlan,
    selection: SelectionResult,
    execution: ExecutionOutcome | None,
    *,
    retrieval_truncation: tuple[str, ...] = (),
    search_hits: tuple[SearchHit, ...] = (),
) -> EvidenceBundle:
    """Assemble one deterministic, JSON-compatible evidence bundle.

    A search request produces ranked candidates and selects nothing. A structural
    request runs only when selection resolved exactly one canonical entity. A
    graph-wide inventory reports its canonical entities as candidates.
    """
    if not isinstance(snapshot, AnalysisSnapshot):
        raise OrchestrationInvariantError("build_bundle requires an AnalysisSnapshot")
    if not isinstance(plan, QueryPlan):
        raise OrchestrationInvariantError("build_bundle requires a QueryPlan")
    if not isinstance(selection, SelectionResult):
        raise OrchestrationInvariantError("build_bundle requires a SelectionResult")
    request = plan.request
    if selection.status is SelectionStatus.AMBIGUOUS:
        status = BundleStatus.AMBIGUOUS_SOURCE
    elif selection.status is SelectionStatus.INVALID:
        status = BundleStatus.INVALID_SOURCE
    elif selection.status is SelectionStatus.NOT_FOUND and request.intent is not QueryIntent.SEARCH_ENTITIES:
        status = BundleStatus.NOT_FOUND_SOURCE
    elif request.intent is QueryIntent.SEARCH_ENTITIES:
        status = BundleStatus.SEARCH_RESULTS
    else:
        if execution is None:
            raise OrchestrationInvariantError("a structural bundle requires an execution outcome")
        has_result = bool(execution.paths) or bool(execution.entities)
        status = BundleStatus.EVIDENCE_PATHS if has_result else BundleStatus.NO_KNOWN_PATH
        if has_result and not execution.paths and execution.entity_result is not None:
            status = BundleStatus.INVENTORY
    paths: tuple[PathEvidence, ...] = ()
    selected: EntitySummary | None = None
    candidates = selection.candidates
    if status in (BundleStatus.EVIDENCE_PATHS, BundleStatus.NO_KNOWN_PATH, BundleStatus.INVENTORY) and (
        execution is not None
    ):
        if execution.path_result is not None:
            paths = tuple(path_evidence(snapshot, path, execution.path_result) for path in execution.paths)
        if selection.selected_entity_id is not None:
            document = snapshot.document(selection.selected_entity_id)
            if document is None:
                raise OrchestrationInvariantError("selected entity is missing from the retrieval snapshot")
            selected = entity_summary(snapshot, snapshot.graph.get_entity(selection.selected_entity_id))
        elif execution.entity_result is not None:
            candidates = tuple(
                entity_candidate(snapshot, entity, SelectionBasis.EXACT_ENTITY_ID)
                for entity in execution.entity_result.entities
            )
    graph_truncation = () if execution is None else execution.graph_truncation
    return EvidenceBundle(
        schema_version=SCHEMA_VERSION,
        status=status,
        request=request.to_dict(),
        plan=plan.to_dict(),
        selection=selection,
        selected_entity=selected,
        candidate_entities=candidates,
        search_hits=search_hits,
        paths=paths,
        analysis_completeness=snapshot.analysis_completeness,
        retrieval_truncation=retrieval_truncation,
        graph_truncation=graph_truncation,
        limitations=_limitations(
            status,
            selection,
            snapshot.analysis_completeness.value,
            retrieval_truncation,
            graph_truncation,
            request.include_graph_context,
        ),
        index_snapshot_id=snapshot.snapshot_id,
    )
