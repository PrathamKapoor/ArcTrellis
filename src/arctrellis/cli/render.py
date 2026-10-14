"""Human-readable rendering of snapshot and bundle records; never a second contract.

Text mode is for people. Every value it prints comes from the orchestration models
or the snapshot counts, so a text report can never disagree with the JSON payload
that --json emits for the same request (D-147).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from arctrellis.orchestration import (
    AnalysisSnapshot,
    BundleStatus,
    EntityCandidate,
    EntitySummary,
    EvidenceBundle,
    EvidenceDetail,
    PathEvidence,
    RelationshipEvidence,
    SelectionResult,
    SelectionStatus,
)

INDENT = "  "


def _location(entity: EntitySummary) -> str:
    location = entity.source_location
    if location is None:
        return ""
    return f":{location.start_line}"


def describe_entity(entity: EntitySummary) -> str:
    """One-line identity: kind, name, repository-relative path and line."""
    path = entity.repository_relative_path or "<no path>"
    return f"{entity.entity_kind.value} {entity.name} [{path}{_location(entity)}]"


def describe_candidate(candidate: EntityCandidate, index: int) -> str:
    """One numbered candidate line with its selection basis and relevance."""
    score = "" if candidate.relevance_score is None else f" relevance={candidate.relevance_score:.4f}"
    return (
        f"{INDENT}{index}. {candidate.entity_id}  {candidate.entity_kind.value} "
        f"{candidate.name} [{candidate.repository_relative_path or '<no path>'}]"
        f"{score} basis={candidate.basis.value}"
    )


def render_snapshot(snapshot: AnalysisSnapshot) -> list[str]:
    """Counts and completeness for one analyzed repository."""
    counts = snapshot.counts
    lines = [
        f"snapshot {snapshot.snapshot_id}",
        f"analysis completeness: {snapshot.analysis_completeness.value}",
        f"supported files: {counts.supported_file_count}",
        f"complete files: {counts.complete_file_count}",
        f"partial files: {counts.partial_file_count}",
        f"failed files: {counts.failed_file_count}",
        f"entities: {counts.entity_count}",
        f"relationships: {counts.relationship_count}",
        f"endpoints: {counts.endpoint_count}",
        f"tests: {counts.test_count}",
        f"database operations: {counts.database_operation_count}",
        f"retrieval documents: {counts.retrieval_document_count}",
        f"retrieval terms: {counts.retrieval_term_count}",
    ]
    if not counts.fully_analyzed:
        lines.append("note: analysis is not complete; partial or failed files were not fully analyzed")
    return lines


def _relationship_line(relationship_index: int, relationship: RelationshipEvidence) -> str:
    score = "" if relationship.confidence_score is None else f" score={relationship.confidence_score}"
    return (
        f"{INDENT}{relationship.relationship_kind} #{relationship_index}: confidence={relationship.confidence}{score}"
    )


def _evidence_lines(evidence: Iterable[EvidenceDetail]) -> list[str]:
    lines = []
    for item in evidence:
        span = str(item.start_line) if item.start_line == item.end_line else f"{item.start_line}-{item.end_line}"
        lines.append(f"{INDENT}{INDENT}evidence {item.analysis_method} {item.file_path}:{span}")
    return lines


def render_path(path: PathEvidence, index: int) -> list[str]:
    """One evidence path as entity and relationship lines in stored forward order."""
    header = f"path {index + 1} of {path.hop_count} hop(s), direction={path.direction}"
    if path.confidence_classification is not None:
        header += f", weakest-edge confidence={path.confidence_classification}"
    if path.weakest_edge_score is not None:
        header += f" ({path.weakest_edge_score})"
    lines = [header]
    for position, entity in enumerate(path.entities):
        lines.append(f"{INDENT}{describe_entity(entity)}")
        if position < len(path.relationships):
            relationship = path.relationships[position]
            lines.append(_relationship_line(position + 1, relationship))
            lines.extend(_evidence_lines(relationship.evidence))
    return lines


_PATH_STATUS = {
    BundleStatus.EVIDENCE_PATHS: "structural evidence paths found",
    BundleStatus.INVENTORY: "canonical inventory",
    BundleStatus.NO_KNOWN_PATH: "no known structural path",
    BundleStatus.SEARCH_RESULTS: "ranked lexical candidates; no entity selected",
    BundleStatus.AMBIGUOUS_SOURCE: "ambiguous source selection; no entity selected",
    BundleStatus.NOT_FOUND_SOURCE: "source entity not found in the analyzed snapshot",
    BundleStatus.INVALID_SOURCE: "source entity kind is incompatible with the intent",
}

_CANDIDATE_STATUS = {
    SelectionStatus.RESOLVED: "resolved",
    SelectionStatus.AMBIGUOUS: "ambiguous",
    SelectionStatus.NOT_FOUND: "not found",
    SelectionStatus.INVALID: "invalid for this intent",
    SelectionStatus.CANDIDATES: "ranked candidates; none selected",
    SelectionStatus.NOT_REQUIRED: "not required for this intent",
}


def render_selection(selection: SelectionResult) -> list[str]:
    lines = [f"selection: {_CANDIDATE_STATUS[selection.status]} ({selection.reason})"]
    if selection.selector_text:
        lines.append(f"selector: {selection.selector_text}")
    if selection.truncated:
        lines.append("selection candidate list was truncated by a budget")
    for index, candidate in enumerate(selection.candidates, start=1):
        lines.append(describe_candidate(candidate, index))
    return lines


def render_bundle(bundle: EvidenceBundle) -> list[str]:
    """Human-readable report for one evidence bundle, in a stable field order."""
    lines = [
        f"status: {bundle.status.value} ({_PATH_STATUS[bundle.status]})",
        f"intent: {bundle.request['intent']}",
        f"index snapshot: {bundle.index_snapshot_id}",
        f"analysis completeness: {bundle.analysis_completeness.value}",
    ]
    if bundle.plan["structural_query"] is not None:
        lines.append(f"structural query: {bundle.plan['structural_query']}")
    lines.extend(render_selection(bundle.selection))
    if bundle.selected_entity is not None:
        lines.append(f"selected entity: {describe_entity(bundle.selected_entity)}")
    if bundle.search_hits:
        lines.append(f"ranked hits: {len(bundle.search_hits)} (relevance is lexical, not identity)")
        for rank, hit in enumerate(bundle.search_hits, start=1):
            lines.append(
                f"{INDENT}{rank}. {hit.entity_id}  {hit.entity_kind.value} {hit.name} "
                f"[{hit.repository_relative_path or '<no path>'}] relevance={hit.relevance_score:.4f} "
                f"basis={hit.match_basis.value} fields={','.join(hit.matched_fields) or '<none>'}"
            )
    if bundle.paths:
        lines.append(f"evidence paths: {len(bundle.paths)}")
        for index, path in enumerate(bundle.paths):
            lines.extend(render_path(path, index))
    elif bundle.candidate_entities and bundle.status is BundleStatus.INVENTORY:
        lines.append(f"inventory entities: {len(bundle.candidate_entities)}")
        for index, candidate in enumerate(bundle.candidate_entities, start=1):
            lines.append(describe_candidate(candidate, index))
    if bundle.retrieval_truncation:
        lines.append(f"retrieval truncation: {', '.join(bundle.retrieval_truncation)}")
    if bundle.graph_truncation:
        lines.append(f"query truncation: {', '.join(bundle.graph_truncation)}")
    for limitation in bundle.limitations:
        lines.append(f"limitation: {limitation}")
    return lines


def render_lines(lines: Sequence[str]) -> str:
    return "\n".join(lines)


def render_candidate_table(candidates: Iterable[EntityCandidate]) -> list[str]:
    return [describe_candidate(candidate, index) for index, candidate in enumerate(candidates, start=1)]
