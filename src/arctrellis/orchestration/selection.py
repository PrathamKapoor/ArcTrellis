"""Conservative canonical entity selection; a high lexical score is never identity.

Selection is the credibility boundary of ArcTrellis. This module therefore
never picks the best-ranked candidate: an exact canonical identifier resolves
directly, an exact qualified name or endpoint route resolves only when exactly
one eligible canonical entity matches, and a lexical query returns candidates
for explicit human selection (D-143).
"""

from __future__ import annotations

from dataclasses import dataclass

from arctrellis.core import EntityKind
from arctrellis.retrieval import SearchDocument, SearchFilters, SearchResult, search_symbols

from .errors import InvalidQueryRequestError
from .models import (
    EntityCandidate,
    QueryRequest,
    SelectionBasis,
    SelectionResult,
    SelectionStatus,
    SelectorForm,
)
from .pipeline import AnalysisSnapshot

MAX_SELECTION_CANDIDATES = 25
DEFAULT_OPERATION_KINDS = frozenset(("read", "write", "delete"))


@dataclass(frozen=True, slots=True)
class SearchCandidates:
    """Ranked lexical results plus their explicit, non-selecting selection record."""

    result: SearchResult
    selection: SelectionResult

    def __post_init__(self) -> None:
        if not isinstance(self.result, SearchResult) or not isinstance(self.selection, SelectionResult):
            raise InvalidQueryRequestError("search candidates require a SearchResult and SelectionResult")


def _candidate(document: SearchDocument, basis: SelectionBasis, relevance: float | None = None) -> EntityCandidate:
    """Project a canonical document into an explainable candidate record."""
    return EntityCandidate(
        entity_id=document.entity_id,
        name=document.name,
        qualified_name=document.qualified_name,
        entity_kind=document.entity_kind,
        language=document.language,
        repository_relative_path=document.repository_relative_path,
        source_location=document.source_location,
        basis=basis,
        relevance_score=relevance,
    )


def _eligible(document: SearchDocument, request: QueryRequest, source_kinds: frozenset[EntityKind]) -> bool:
    """Whether a canonical document satisfies every caller constraint.

    These are constraints, never selectors: they narrow what the caller's own
    selector may resolve to, they never choose an entity themselves.
    """
    if source_kinds and document.entity_kind not in source_kinds:
        return False
    if request.entity_kind is not None and document.entity_kind is not request.entity_kind:
        return False
    if request.language is not None and document.field_value("language") != request.language:
        return False
    if request.path_prefix is not None:
        path = document.repository_relative_path
        if path is None or not path.startswith(request.path_prefix):
            return False
    if request.framework is not None and document.field_value("framework") != request.framework:
        return False
    if request.endpoint_scope is None:
        return True
    # ``application`` is a composition scope, the other values are path
    # completeness levels. This mirrors ``list_endpoints`` so one request means
    # the same thing whichever intent applies it.
    if request.endpoint_scope == "application":
        return document.field_value("composition_scope") == "application"
    return document.field_value("path_completeness") == request.endpoint_scope


def _bounded(candidates: list[EntityCandidate], limit: int) -> tuple[tuple[EntityCandidate, ...], bool]:
    ordered = tuple(sorted(candidates, key=lambda item: item.entity_id)[:limit])
    return ordered, len(candidates) > limit


def select_canonical_entity(
    snapshot: AnalysisSnapshot, request: QueryRequest, source_kinds: frozenset[EntityKind]
) -> SelectionResult:
    """Resolve the request's explicit selector into one canonical entity or candidates.

    Returns ``RESOLVED`` only for a single exact canonical match. Duplicate
    qualified names, duplicate ``METHOD path`` registrations and same-name
    cross-kind collisions all return ``AMBIGUOUS`` with the exact candidate set,
    so the caller must choose explicitly rather than inherit a guess.
    """
    if not isinstance(snapshot, AnalysisSnapshot):
        raise InvalidQueryRequestError("select_canonical_entity requires an AnalysisSnapshot")
    if not isinstance(request, QueryRequest):
        raise InvalidQueryRequestError("select_canonical_entity requires a validated QueryRequest")
    form = request.selector_form
    if form is SelectorForm.ENTITY_ID:
        return _select_by_entity_id(snapshot, request, source_kinds)
    if form is SelectorForm.QUALIFIED_NAME:
        return _select_by_qualified_name(snapshot, request, source_kinds)
    if form is SelectorForm.ENDPOINT_METHOD_PATH:
        return _select_by_route(snapshot, request, source_kinds)
    if form is SelectorForm.SEARCH_TEXT:
        return search_candidates(snapshot, request).selection
    return _no_selection()


def _no_selection() -> SelectionResult:
    """Outcome for graph-wide intents that name no single source entity."""
    return SelectionResult(
        status=SelectionStatus.NOT_REQUIRED,
        selector_form=SelectorForm.NONE,
        selector_text="",
        selected_entity_id=None,
        candidates=(),
        truncated=False,
        reason="intent selects no single source entity",
    )


def _select_by_entity_id(
    snapshot: AnalysisSnapshot, request: QueryRequest, source_kinds: frozenset[EntityKind]
) -> SelectionResult:
    identifier = request.entity_id or ""
    document = snapshot.document(identifier)
    if document is None:
        return SelectionResult(
            SelectionStatus.NOT_FOUND,
            SelectorForm.ENTITY_ID,
            identifier,
            None,
            (),
            False,
            "no canonical entity with this ID exists in the analyzed snapshot",
        )
    if not _eligible(document, request, source_kinds):
        expected = sorted(kind.value for kind in (source_kinds or {document.entity_kind}))
        return SelectionResult(
            SelectionStatus.INVALID,
            SelectorForm.ENTITY_ID,
            identifier,
            None,
            (),
            False,
            f"canonical entity kind {document.entity_kind.value} does not satisfy {expected}",
        )
    return SelectionResult(
        SelectionStatus.RESOLVED,
        SelectorForm.ENTITY_ID,
        identifier,
        identifier,
        (),
        False,
        "resolved by exact canonical entity ID",
    )


def _select_by_qualified_name(
    snapshot: AnalysisSnapshot, request: QueryRequest, source_kinds: frozenset[EntityKind]
) -> SelectionResult:
    qualified_name = request.qualified_name or ""
    matches = [
        document
        for identifier in snapshot.entities_with_qualified_name(qualified_name)
        if (document := snapshot.document(identifier)) is not None and _eligible(document, request, source_kinds)
    ]
    if not matches:
        return SelectionResult(
            SelectionStatus.NOT_FOUND,
            SelectorForm.QUALIFIED_NAME,
            qualified_name,
            None,
            (),
            False,
            "no canonical entity has this exact qualified name",
        )
    candidates, truncated = _bounded(
        [_candidate(item, SelectionBasis.EXACT_QUALIFIED_NAME) for item in matches], MAX_SELECTION_CANDIDATES
    )
    if len(matches) == 1:
        return SelectionResult(
            SelectionStatus.RESOLVED,
            SelectorForm.QUALIFIED_NAME,
            qualified_name,
            matches[0].entity_id,
            (),
            False,
            "resolved by unique exact qualified name",
        )
    return SelectionResult(
        SelectionStatus.AMBIGUOUS,
        SelectorForm.QUALIFIED_NAME,
        qualified_name,
        None,
        candidates,
        truncated,
        f"{len(matches)} canonical entities share this qualified name; supply an exact entity ID",
    )


def _select_by_route(
    snapshot: AnalysisSnapshot, request: QueryRequest, source_kinds: frozenset[EntityKind]
) -> SelectionResult:
    selector_text = f"{request.http_method} {request.route_path}"
    matches = [
        document
        for identifier in snapshot.entities_with_route(request.http_method or "", request.route_path or "")
        if (document := snapshot.document(identifier)) is not None and _eligible(document, request, source_kinds)
    ]
    if not matches:
        return SelectionResult(
            SelectionStatus.NOT_FOUND,
            SelectorForm.ENDPOINT_METHOD_PATH,
            selector_text,
            None,
            (),
            False,
            "no canonical endpoint registration matches this method and path",
        )
    candidates, truncated = _bounded(
        [_candidate(item, SelectionBasis.EXACT_ENDPOINT_METHOD_PATH) for item in matches], MAX_SELECTION_CANDIDATES
    )
    if len(matches) == 1:
        return SelectionResult(
            SelectionStatus.RESOLVED,
            SelectorForm.ENDPOINT_METHOD_PATH,
            selector_text,
            matches[0].entity_id,
            (),
            False,
            "resolved by unique endpoint method and path",
        )
    return SelectionResult(
        SelectionStatus.AMBIGUOUS,
        SelectorForm.ENDPOINT_METHOD_PATH,
        selector_text,
        None,
        candidates,
        truncated,
        f"{len(matches)} endpoint registrations share this method and path; supply an exact entity ID",
    )


def search_candidates(snapshot: AnalysisSnapshot, request: QueryRequest) -> SearchCandidates:
    """Rank canonical candidates lexically without selecting any entity.

    A high BM25 relevance score is a lexical measurement, not proof of entity
    identity, so this never returns a selection that names an entity. The caller
    receives ordered candidates and must choose explicitly.
    """
    if not isinstance(snapshot, AnalysisSnapshot):
        raise InvalidQueryRequestError("search_candidates requires an AnalysisSnapshot")
    if not isinstance(request, QueryRequest):
        raise InvalidQueryRequestError("search_candidates requires a validated QueryRequest")
    filters = SearchFilters(
        entity_kinds=frozenset((request.entity_kind,)) if request.entity_kind is not None else None,
        languages=frozenset((request.language,)) if request.language is not None else None,
        path_prefixes=(request.path_prefix,) if request.path_prefix is not None else (),
        frameworks=frozenset((request.framework,)) if request.framework is not None else None,
        path_completeness=(frozenset((request.endpoint_scope,)) if request.endpoint_scope is not None else None),
        operation_kinds=(
            frozenset(request.operation_kinds) if request.operation_kinds != DEFAULT_OPERATION_KINDS else None
        ),
    )
    result = search_symbols(
        snapshot.retrieval,
        request.search_text or "",
        top_k=request.top_k,
        filters=filters,
        include_graph_context=request.include_graph_context,
        max_examined_postings=request.max_examined_postings,
        analysis_completeness=snapshot.analysis_completeness,
    )
    candidates = tuple(
        _candidate(document, SelectionBasis.LEXICAL_CANDIDATES, hit.relevance_score)
        for hit in result.hits
        if (document := snapshot.retrieval.document(hit.entity_id)) is not None
    )
    status = SelectionStatus.CANDIDATES if candidates else SelectionStatus.NOT_FOUND
    reason = (
        "lexical search produced ranked candidates; no entity is selected automatically"
        if candidates
        else "no canonical entity matched the search text"
    )
    return SearchCandidates(
        result=result,
        selection=SelectionResult(
            status=status,
            selector_form=SelectorForm.SEARCH_TEXT,
            selector_text=request.search_text or "",
            selected_entity_id=None,
            candidates=candidates,
            truncated=result.truncated,
            reason=reason,
        ),
    )
