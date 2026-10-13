"""Bounded deterministic ranked retrieval over an immutable search snapshot.

Relevance is ``bm25_score + exact_match_boost + prefix_boost + graph_context_boost``.
Every component is a bounded, non-negative relevance number. None of them is a
probability, a confidence calibration, a semantic-similarity score or a statement
about runtime behavior.

Retrieval never reads the filesystem, never re-reads the graph, never mutates the
index and never invents an entity, a relationship or an Evidence record. Query
text is data: it is tokenized and matched, never interpreted or executed.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Any

from arctrellis.core import Confidence, EntityKind, Evidence, RelationshipKind, SourceLocation
from arctrellis.query import AnalysisCompleteness

from .context import GRAPH_CONTEXT_BOOST_CAP, ContextDirection, ContextEdge, GraphContextIndex
from .documents import FIELD_LANGUAGE, FIELD_PATH, SearchDocument
from .errors import InvalidSearchLimitError, InvalidSearchQueryError, RetrievalInvariantError
from .index import LexicalSearchIndex
from .normalization import normalize_exact, tokenize
from .scoring import ExactMatchTier, bm25_score, exact_match_boost, exact_match_tiers

MAX_QUERY_LENGTH = 512
MAX_QUERY_TOKENS = 24
DEFAULT_TOP_K = 25
MAX_ACCEPTED_TOP_K = 100
DEFAULT_MAX_EXAMINED_POSTINGS = 50000
DEFAULT_MAX_GRAPH_SEEDS = 25
DEFAULT_MAX_GRAPH_NEIGHBORS = 16

TRUNCATION_REASONS = ("graph_neighbor_budget", "graph_seed_budget", "posting_budget")

LEXICAL = "lexical"
GRAPH_NEIGHBOR = "graph_neighbor"
LEXICAL_AND_GRAPH = "lexical_and_graph"


class MatchBasis(StrEnum):
    """Why a document is present in the result."""

    LEXICAL = LEXICAL
    GRAPH_NEIGHBOR = GRAPH_NEIGHBOR
    LEXICAL_AND_GRAPH = LEXICAL_AND_GRAPH


def validate_limit(name: str, value: int, maximum: int | None = None) -> int:
    """Require a positive non-boolean integer, optionally within a documented cap."""
    if type(value) is not int:
        raise InvalidSearchLimitError(f"{name} must be a positive integer, not {type(value).__name__}")
    if value <= 0:
        raise InvalidSearchLimitError(f"{name} must be a positive integer")
    if maximum is not None and value > maximum:
        raise InvalidSearchLimitError(f"{name} must not exceed {maximum}")
    return value


def normalize_query(query: str) -> tuple[str, tuple[str, ...]]:
    """Validate and tokenize query text.

    A blank query, a query with no retrievable token, an over-long query and an
    over-long token sequence are rejected rather than answered, so a blank query
    can never return arbitrary top-ranked documents. Everything here is pure text
    handling: no decoding, no path resolution, no filesystem access.
    """
    if not isinstance(query, str):
        raise InvalidSearchQueryError("query must be a string")
    if not query or query != query.strip():
        raise InvalidSearchQueryError("query must be nonempty and have no surrounding whitespace")
    if len(query) > MAX_QUERY_LENGTH:
        raise InvalidSearchQueryError(f"query must not exceed {MAX_QUERY_LENGTH} characters")
    tokens = tokenize(query, max_tokens=MAX_QUERY_TOKENS + 1)
    if not tokens:
        raise InvalidSearchQueryError("query contains no retrievable token")
    if len(tokens) > MAX_QUERY_TOKENS:
        raise InvalidSearchQueryError(f"query must not exceed {MAX_QUERY_TOKENS} tokens")
    return normalize_exact(query), tokens


@dataclass(frozen=True, slots=True)
class SearchFilters:
    """Typed, exact-value filters over canonical entity and projected metadata.

    Filters are matched against canonical entity attributes and allowlisted
    projected field values only. Nothing is inferred from a name or a filename,
    and an absent value never satisfies a filter.
    """

    entity_kinds: frozenset[EntityKind] | None = None
    languages: frozenset[str] | None = None
    path_prefixes: tuple[str, ...] = ()
    http_methods: frozenset[str] | None = None
    frameworks: frozenset[str] | None = None
    providers: frozenset[str] | None = None
    operation_kinds: frozenset[str] | None = None
    path_completeness: frozenset[str] | None = None

    def __post_init__(self) -> None:
        if self.entity_kinds is not None and (
            not isinstance(self.entity_kinds, frozenset)
            or any(not isinstance(kind, EntityKind) for kind in self.entity_kinds)
        ):
            raise TypeError("entity_kinds must be a frozenset of EntityKind")
        for name in ("languages", "http_methods", "frameworks", "providers", "operation_kinds", "path_completeness"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, frozenset) or any(not isinstance(item, str) or not item for item in value)
            ):
                raise TypeError(f"{name} must be a frozenset of nonempty strings or None")
            if value is not None and not value:
                raise ValueError(f"{name} must be None or a nonempty frozenset")
        if self.entity_kinds is not None and not self.entity_kinds:
            raise ValueError("entity_kinds must be None or a nonempty frozenset")
        if not isinstance(self.path_prefixes, tuple) or any(
            not isinstance(item, str) or not item for item in self.path_prefixes
        ):
            raise TypeError("path_prefixes must be a tuple of nonempty strings")
        if self.path_prefixes != tuple(sorted(set(self.path_prefixes))):
            raise ValueError("path_prefixes must be sorted and unique")

    @property
    def active(self) -> bool:
        return bool(
            self.entity_kinds
            or self.languages
            or self.path_prefixes
            or self.http_methods
            or self.frameworks
            or self.providers
            or self.operation_kinds
            or self.path_completeness
        )

    def accepts(self, document: SearchDocument) -> bool:
        """Whether a projected document satisfies every supplied filter."""
        if self.entity_kinds is not None and document.entity_kind not in self.entity_kinds:
            return False
        if self.languages is not None and document.field_value(FIELD_LANGUAGE) not in self.languages:
            return False
        if self.path_prefixes:
            path = document.field_value(FIELD_PATH)
            if path is None or not any(path.startswith(prefix) for prefix in self.path_prefixes):
                return False
        for values, key in (
            (self.http_methods, "http_method"),
            (self.frameworks, "framework"),
            (self.providers, "provider"),
            (self.operation_kinds, "operation_kind"),
            (self.path_completeness, "path_completeness"),
        ):
            if values is not None and document.field_value(key) not in values:
                return False
        return True

    def to_dict(self) -> dict[str, object]:
        return {
            "entity_kinds": None if self.entity_kinds is None else sorted(kind.value for kind in self.entity_kinds),
            "languages": None if self.languages is None else sorted(self.languages),
            "path_prefixes": list(self.path_prefixes),
            "http_methods": None if self.http_methods is None else sorted(self.http_methods),
            "frameworks": None if self.frameworks is None else sorted(self.frameworks),
            "providers": None if self.providers is None else sorted(self.providers),
            "operation_kinds": None if self.operation_kinds is None else sorted(self.operation_kinds),
            "path_completeness": None if self.path_completeness is None else sorted(self.path_completeness),
        }


@dataclass(frozen=True, slots=True)
class ContextSupport:
    """One grounded relationship that justifies a graph-context hit.

    The relationship, its confidence and its Evidence are the original stored
    records. ``confidence`` and ``confidence_score`` describe static resolution
    strength only and are never multiplied into the retrieval relevance score.
    """

    neighbor_entity_id: str
    neighbor_name: str
    relationship_id: str
    relationship_kind: RelationshipKind
    direction: ContextDirection
    confidence: Confidence
    confidence_score: float | None
    contribution: float
    evidence: tuple[Evidence, ...]

    def __post_init__(self) -> None:
        if not self.neighbor_entity_id or not self.relationship_id:
            raise ValueError("context support requires nonempty neighbor and relationship IDs")
        if not isinstance(self.relationship_kind, RelationshipKind):
            raise TypeError("relationship_kind must be RelationshipKind")
        if not isinstance(self.direction, ContextDirection):
            raise TypeError("direction must be ContextDirection")
        if not isinstance(self.confidence, Confidence):
            raise TypeError("confidence must be Confidence")
        if not 0 <= self.contribution <= GRAPH_CONTEXT_BOOST_CAP or not isfinite(self.contribution):
            raise RetrievalInvariantError("context contribution must stay within the documented cap")
        if not isinstance(self.evidence, tuple):
            raise TypeError("evidence must be a tuple of original Evidence records")

    def to_dict(self) -> dict[str, object]:
        return {
            "neighbor_entity_id": self.neighbor_entity_id,
            "neighbor_name": self.neighbor_name,
            "relationship_id": self.relationship_id,
            "relationship_kind": self.relationship_kind.value,
            "direction": self.direction.value,
            "confidence": self.confidence.value,
            "confidence_score": self.confidence_score,
            "contribution": self.contribution,
            "evidence": [
                {
                    "id": item.id,
                    "analysis_method": item.analysis_method,
                    "file_path": item.location.file_path,
                    "start_line": item.location.start_line,
                    "end_line": item.location.end_line,
                }
                for item in self.evidence
            ],
        }


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One ranked canonical entity with its full, inspectable score composition."""

    entity_id: str
    entity_kind: EntityKind
    name: str
    qualified_name: str
    language: str | None
    parent_id: str | None
    repository_relative_path: str | None
    source_location: SourceLocation | None
    match_basis: MatchBasis
    relevance_score: float
    bm25_score: float
    exact_match_boost: float
    prefix_boost: float
    graph_context_boost: float
    exact_match_priority: ExactMatchTier
    matched_terms: tuple[str, ...]
    matched_fields: tuple[str, ...]
    match_reasons: tuple[str, ...]
    context_support: tuple[ContextSupport, ...]
    document_length: float
    searchable_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.entity_id:
            raise ValueError("hits require a canonical entity ID")
        if not isinstance(self.match_basis, MatchBasis):
            raise TypeError("match_basis must be MatchBasis")
        total = self.bm25_score + self.exact_match_boost + self.prefix_boost + self.graph_context_boost
        if not isfinite(total) or not isfinite(self.relevance_score):
            raise RetrievalInvariantError("hit scores must be finite")
        if abs(self.relevance_score - total) > 1e-9:
            raise RetrievalInvariantError("relevance_score must equal the sum of its components")
        for component in (self.bm25_score, self.exact_match_boost, self.prefix_boost, self.graph_context_boost):
            if component < 0:
                raise RetrievalInvariantError("score components must be nonnegative")
        if self.graph_context_boost > GRAPH_CONTEXT_BOOST_CAP:
            raise RetrievalInvariantError("graph context boost must respect the documented cap")
        if not isinstance(self.match_reasons, tuple) or not self.match_reasons:
            raise ValueError("every hit must carry at least one match reason")
        if not isinstance(self.context_support, tuple):
            raise TypeError("context_support must be a ContextSupport tuple")
        if self.match_basis is MatchBasis.GRAPH_NEIGHBOR and not self.context_support:
            raise ValueError("a graph-neighbor hit must expose its supporting relationships")
        if self.match_basis is not MatchBasis.GRAPH_NEIGHBOR and self.context_support and not self.graph_context_boost:
            raise ValueError("context support requires a graph context boost")

    @property
    def has_graph_context(self) -> bool:
        return bool(self.context_support)

    def to_dict(self) -> dict[str, object]:
        return {
            "entity_id": self.entity_id,
            "entity_kind": self.entity_kind.value,
            "name": self.name,
            "qualified_name": self.qualified_name,
            "language": self.language,
            "parent_id": self.parent_id,
            "repository_relative_path": self.repository_relative_path,
            "source_location": None
            if self.source_location is None
            else {
                "file_path": self.source_location.file_path,
                "start_line": self.source_location.start_line,
                "end_line": self.source_location.end_line,
            },
            "match_basis": self.match_basis.value,
            "relevance_score": self.relevance_score,
            "score_components": {
                "bm25_score": self.bm25_score,
                "exact_match_boost": self.exact_match_boost,
                "prefix_boost": self.prefix_boost,
                "graph_context_boost": self.graph_context_boost,
            },
            "exact_match_priority": int(self.exact_match_priority),
            "matched_terms": list(self.matched_terms),
            "matched_fields": list(self.matched_fields),
            "match_reasons": list(self.match_reasons),
            "searchable_fields": list(self.searchable_fields),
            "document_length": self.document_length,
            "context_support": [item.to_dict() for item in self.context_support],
        }


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Bounded ranked result for one query against one immutable index snapshot.

    ``truncated`` reports budget-driven incompleteness only. ``top_k`` limiting is
    reported separately through ``eligible_candidate_count``, because returning
    fewer hits than the corpus matched is not an incomplete search. Counts are
    exact only when ``truncated`` is False.
    """

    query: str
    normalized_query: str
    query_tokens: tuple[str, ...]
    hits: tuple[SearchHit, ...]
    matched_candidate_count: int
    eligible_candidate_count: int
    graph_candidate_count: int
    filters: SearchFilters
    top_k: int
    max_examined_postings: int
    examined_postings: int
    graph_seed_budget: int
    graph_neighbor_budget: int
    truncation_reasons: tuple[str, ...]
    graph_context_used: bool
    index_snapshot_id: str
    index_document_count: int
    analysis_completeness: AnalysisCompleteness

    def __post_init__(self) -> None:
        if not isinstance(self.hits, tuple) or any(not isinstance(hit, SearchHit) for hit in self.hits):
            raise TypeError("hits must be a SearchHit tuple")
        identifiers = tuple(hit.entity_id for hit in self.hits)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("hits must not repeat a canonical entity ID")
        if self.hits != tuple(sorted(self.hits, key=hit_order)):
            raise ValueError("hits must be deterministically ordered")
        if len(self.hits) > self.top_k:
            raise ValueError("hits must respect top_k")
        for name in (
            "matched_candidate_count",
            "eligible_candidate_count",
            "graph_candidate_count",
            "examined_postings",
        ):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.eligible_candidate_count < len(self.hits) or self.eligible_candidate_count < self.graph_candidate_count:
            raise ValueError("candidate counts must cover the returned hits")
        if self.examined_postings > self.max_examined_postings:
            raise ValueError("examined postings must respect the budget")
        if self.truncation_reasons != tuple(sorted(set(self.truncation_reasons))) or any(
            reason not in TRUNCATION_REASONS for reason in self.truncation_reasons
        ):
            raise ValueError("truncation reasons must be sorted, unique and known")
        if bool(self.truncation_reasons) is not any(
            reason in self.truncation_reasons
            for reason in ("posting_budget", "graph_seed_budget", "graph_neighbor_budget")
        ):
            raise ValueError("truncated results must carry a budget reason")
        if not isinstance(self.graph_context_used, bool):
            raise TypeError("graph_context_used must be a boolean")
        if self.graph_context_used and not any(hit.has_graph_context for hit in self.hits):
            raise ValueError("graph-context results must expose at least one grounded contribution")
        if not isinstance(self.filters, SearchFilters):
            raise TypeError("filters must be SearchFilters")
        if not isinstance(self.analysis_completeness, AnalysisCompleteness):
            raise TypeError("analysis_completeness must be AnalysisCompleteness")

    @property
    def truncated(self) -> bool:
        """Whether a budget stopped candidate examination before the corpus was covered."""
        return bool(self.truncation_reasons)

    def entity_ids(self) -> tuple[str, ...]:
        """Canonical IDs suitable for existing structural query entry points."""
        return tuple(hit.entity_id for hit in self.hits)

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "normalized_query": self.normalized_query,
            "query_tokens": list(self.query_tokens),
            "hits": [hit.to_dict() for hit in self.hits],
            "matched_candidate_count": self.matched_candidate_count,
            "eligible_candidate_count": self.eligible_candidate_count,
            "graph_candidate_count": self.graph_candidate_count,
            "filters": self.filters.to_dict(),
            "top_k": self.top_k,
            "max_examined_postings": self.max_examined_postings,
            "examined_postings": self.examined_postings,
            "graph_seed_budget": self.graph_seed_budget,
            "graph_neighbor_budget": self.graph_neighbor_budget,
            "truncated": self.truncated,
            "truncation_reasons": list(self.truncation_reasons),
            "graph_context_used": self.graph_context_used,
            "index_snapshot_id": self.index_snapshot_id,
            "index_document_count": self.index_document_count,
            "analysis_completeness": self.analysis_completeness.value,
        }


def hit_order(hit: SearchHit) -> tuple[float, int, str]:
    """Deterministic ranking order: relevance, then exact priority, then entity ID."""
    return (-hit.relevance_score, -int(hit.exact_match_priority), hit.entity_id)


@dataclass(slots=True)
class _Candidate:
    """Internal mutable accumulator; never exposed outside one search call."""

    document: SearchDocument
    eligible: bool = True
    bm25: float = 0.0
    exact_boost: float = 0.0
    prefix_boost: float = 0.0
    graph_boost: float = 0.0
    tier: ExactMatchTier = ExactMatchTier.NONE
    matched_terms: set[str] | None = None
    matched_fields: set[str] | None = None
    context: list[ContextSupport] | None = None

    def terms(self) -> set[str]:
        return set() if self.matched_terms is None else self.matched_terms

    def fields(self) -> set[str]:
        return set() if self.matched_fields is None else self.matched_fields

    @property
    def lexical_score(self) -> float:
        return self.bm25 + self.exact_boost + self.prefix_boost


def _lexical_candidates(
    index: LexicalSearchIndex,
    terms: tuple[str, ...],
    filters: SearchFilters,
    max_examined_postings: int,
) -> tuple[dict[str, _Candidate], int, int, bool]:
    """Scan posting lists once, in term order, collecting every lexical match.

    Every posting record actually inspected consumes the examination budget,
    including records whose document is later rejected by a filter, so the
    reported examination count is the real work governed by the budget.

    Filters mark a candidate eligible or ineligible rather than discarding it.
    Ranking context must be able to start from the strongest matches in the
    whole corpus, so that ``search_endpoints(index, "createPayment")`` can
    surface the endpoint that exposes ``createPayment``. Ineligible candidates
    are removed before the returned ranking, so a filter always constrains
    output and ``top_k`` always applies to eligible results only.
    """
    candidates: dict[str, _Candidate] = {}
    examined_ids: set[str] = set()
    examined = 0
    truncated = False
    for term in terms:
        postings = index.postings.get(term)
        if postings is None:
            continue
        for entity_id, frequency in postings:
            if examined == max_examined_postings:
                truncated = True
                break
            examined += 1
            examined_ids.add(entity_id)
            document = index.document(entity_id)
            if document is None:
                raise RetrievalInvariantError("posting list references a document outside the index")
            candidate = candidates.get(entity_id)
            if candidate is None:
                candidate = _Candidate(document=document, eligible=filters.accepts(document))
                candidates[entity_id] = candidate
            candidate.bm25 += bm25_score(
                document,
                index.document_lengths[entity_id],
                index.average_document_length,
                index.document_count,
                {term: frequency},
                index.document_frequency,
            )
            if candidate.matched_terms is None or candidate.matched_fields is None:
                candidate.matched_terms = set()
                candidate.matched_fields = set()
            terms_matched = candidate.matched_terms
            fields_matched = candidate.matched_fields
            terms_matched.add(term)
            fields_matched.update(item.name for item in document.fields if term in item.tokens)
        if truncated:
            break
    return candidates, len(examined_ids), examined, truncated


def _apply_exact_boosts(index: LexicalSearchIndex, candidates: Mapping[str, _Candidate], query: str) -> None:
    for identifier in sorted(candidates):
        candidate = candidates[identifier]
        tiers = exact_match_tiers(candidate.document, query)
        if not tiers:
            continue
        boost, tier = exact_match_boost(candidate.document, query, tiers)
        if tier is ExactMatchTier.NAME_PREFIX:
            candidate.prefix_boost = boost
        else:
            candidate.exact_boost = boost
        candidate.tier = tier


def _context_edges(
    index: LexicalSearchIndex,
    seed_id: str,
    *,
    max_neighbors: int,
) -> tuple[tuple[tuple[ContextEdge, str], ...], bool]:
    """Bounded one-hop context of a seed as ``(edge, neighbor_id)`` pairs.

    A neighbor does not have to contain the query terms itself: the endpoint
    exposing a strongly matched ``createPayment`` is exactly the case that
    graph-aware retrieval exists for. Only relationships that the indexed
    snapshot actually stores are returned.
    """
    context: GraphContextIndex | None = index.context
    if context is None:
        return (), False
    found: list[tuple[ContextEdge, str]] = []
    truncated = False
    for edge, _ in context.edges(seed_id, limit=max_neighbors + 1):
        if len(found) == max_neighbors:
            truncated = True
            break
        neighbor_id = edge.other_endpoint(seed_id)
        if neighbor_id != seed_id:
            found.append((edge, neighbor_id))
    return tuple(found), truncated


def _expand_context(
    index: LexicalSearchIndex,
    candidates: dict[str, _Candidate],
    filters: SearchFilters,
    terms: tuple[str, ...],
    *,
    max_graph_seeds: int,
    max_neighbors: int,
) -> tuple[int, bool, bool]:
    """Add bounded one-hop neighbors of the strongest matched documents.

    Only direct neighbors of seeds are ever considered, so retrieval performs no
    arbitrary traversal and never reaches a second hop. A seed contributes in
    proportion to how much of the query it covered, relative to the best seed,
    so a corpus where nothing matches every query term still surfaces connected
    context. Each candidate keeps the *maximum* contribution over its supporting
    relationships, never their sum, so degree cannot inflate a boost.

    Every support is recorded relative to the returned hit: the supporting
    relationship's other endpoint is the matched entity that led to this hit, and
    the direction is the stored edge direction seen from this hit. Seeds are the
    strongest lexical matches in the whole corpus, so a kind-restricted wrapper
    can still discover entities that only graph context connects to the query.
    """
    context = index.context
    if context is None or context.edge_count == 0 or not terms:
        return 0, False, False
    distinct = frozenset(terms)
    seeds = sorted(candidates.values(), key=lambda item: (-item.lexical_score, item.document.entity_id))
    selected = seeds[:max_graph_seeds]
    seed_truncated = len(seeds) > max_graph_seeds
    coverage = {seed.document.entity_id: len(distinct & seed.terms()) / len(distinct) for seed in selected}
    best = max(coverage.values(), default=0.0)
    added = 0
    neighbor_truncated = False
    for seed in selected:
        strength = coverage[seed.document.entity_id] / best if best > 0 else 0.0
        found, truncated = _context_edges(index, seed.document.entity_id, max_neighbors=max_neighbors)
        neighbor_truncated = neighbor_truncated or truncated
        for edge, neighbor_id in found:
            document = index.document(neighbor_id)
            if document is None:
                continue
            candidate = candidates.get(neighbor_id)
            if candidate is None:
                candidate = _Candidate(document=document, eligible=filters.accepts(document))
                candidates[neighbor_id] = candidate
                added += 1
            if candidate.context is None:
                candidate.context = []
            if any(item.relationship_id == edge.relationship_id for item in candidate.context):
                continue
            candidate.context.append(
                ContextSupport(
                    neighbor_entity_id=seed.document.entity_id,
                    neighbor_name=seed.document.name,
                    relationship_id=edge.relationship_id,
                    relationship_kind=edge.kind,
                    direction=ContextDirection(edge.direction_from(neighbor_id)),
                    confidence=edge.confidence,
                    confidence_score=edge.confidence_score,
                    contribution=min(GRAPH_CONTEXT_BOOST_CAP, strength * edge.weight),
                    evidence=edge.evidence,
                )
            )
    for identifier in sorted(candidates):
        candidate = candidates[identifier]
        if candidate.context:
            candidate.graph_boost = max(item.contribution for item in candidate.context)
    return added, seed_truncated, neighbor_truncated


def _build_hit(candidate: _Candidate, index: LexicalSearchIndex, *, lexical: bool) -> SearchHit:
    document = candidate.document
    terms = tuple(sorted(candidate.terms()))
    fields = tuple(sorted(candidate.fields()))
    reasons: list[str] = []
    for term in terms:
        reasons.append(f"lexical:token={term}")
    if candidate.exact_boost:
        reasons.append(f"exact:priority={int(candidate.tier)}")
    if candidate.prefix_boost:
        reasons.append(f"prefix:priority={int(candidate.tier)}")
    supports = (
        ()
        if candidate.context is None
        else tuple(sorted(candidate.context, key=lambda item: (-item.contribution, item.relationship_id)))
    )
    for support in supports:
        reasons.append(
            f"graph:kind={support.relationship_kind.value}"
            f";relationship={support.relationship_id}"
            f";direction={support.direction.value}"
            f";neighbor={support.neighbor_entity_id}"
        )
    if lexical and supports:
        basis = MatchBasis.LEXICAL_AND_GRAPH
    elif lexical:
        basis = MatchBasis.LEXICAL
    else:
        basis = MatchBasis.GRAPH_NEIGHBOR
    relevance = candidate.bm25 + candidate.exact_boost + candidate.prefix_boost + candidate.graph_boost
    return SearchHit(
        entity_id=document.entity_id,
        entity_kind=document.entity_kind,
        name=document.name,
        qualified_name=document.qualified_name,
        language=document.language,
        parent_id=document.parent_id,
        repository_relative_path=document.repository_relative_path,
        source_location=document.source_location,
        match_basis=basis,
        relevance_score=relevance,
        bm25_score=candidate.bm25,
        exact_match_boost=candidate.exact_boost,
        prefix_boost=candidate.prefix_boost,
        graph_context_boost=candidate.graph_boost,
        exact_match_priority=candidate.tier,
        matched_terms=terms,
        matched_fields=fields,
        match_reasons=tuple(reasons),
        context_support=supports,
        document_length=index.document_lengths[document.entity_id],
        searchable_fields=tuple(item.name for item in document.fields),
    )


def search_symbols(
    index: LexicalSearchIndex,
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    filters: SearchFilters | None = None,
    include_graph_context: bool = False,
    max_examined_postings: int = DEFAULT_MAX_EXAMINED_POSTINGS,
    max_graph_seeds: int = DEFAULT_MAX_GRAPH_SEEDS,
    max_graph_neighbors: int = DEFAULT_MAX_GRAPH_NEIGHBORS,
    analysis_completeness: AnalysisCompleteness | None = None,
) -> SearchResult:
    """Rank canonical entities for a query against an immutable search snapshot.

    This is the single scoring entry point. ``search_endpoints``, ``search_tests``
    and ``search_database_operations`` delegate here with entity-kind filters and
    never reimplement ranking. Despite its name this function is not restricted
    to declarations: it searches every indexed canonical entity kind.

    ``include_graph_context`` is an explicit opt-in. With it enabled, up to
    ``max_graph_seeds`` strongly matched documents seed one bounded, one-hop
    neighborhood lookup each; no neighbor of a neighbor is ever examined. Budget
    exhaustion sets ``truncated`` with a stable reason, so a truncated result is
    never presented as an exhaustive ranking.
    """
    if not isinstance(index, LexicalSearchIndex):
        raise InvalidSearchQueryError("search_symbols requires a LexicalSearchIndex")
    if type(include_graph_context) is not bool:
        raise TypeError("include_graph_context must be a boolean")
    validate_limit("top_k", top_k, MAX_ACCEPTED_TOP_K)
    validate_limit("max_examined_postings", max_examined_postings)
    validate_limit("max_graph_seeds", max_graph_seeds)
    validate_limit("max_graph_neighbors", max_graph_neighbors)
    active_filters = SearchFilters() if filters is None else filters
    if not isinstance(active_filters, SearchFilters):
        raise TypeError("filters must be SearchFilters or None")
    if analysis_completeness is not None and not isinstance(analysis_completeness, AnalysisCompleteness):
        raise TypeError("analysis_completeness must be AnalysisCompleteness or None")
    normalized, tokens = normalize_query(query)
    distinct_terms = tuple(sorted(dict.fromkeys(tokens)))
    candidates, matched, examined, posting_truncated = _lexical_candidates(
        index, distinct_terms, active_filters, max_examined_postings
    )
    _apply_exact_boosts(index, candidates, query)
    graph_candidates = 0
    seed_truncated = False
    neighbor_truncated = False
    use_context = include_graph_context and index.has_graph_context
    if use_context:
        graph_candidates, seed_truncated, neighbor_truncated = _expand_context(
            index,
            candidates,
            active_filters,
            distinct_terms,
            max_graph_seeds=max_graph_seeds,
            max_neighbors=max_graph_neighbors,
        )
    eligible = [candidate for candidate in candidates.values() if candidate.eligible]
    graph_candidates = sum(1 for candidate in eligible if not candidate.terms())
    hits = tuple(
        sorted(
            (_build_hit(candidate, index, lexical=bool(candidate.terms())) for candidate in eligible),
            key=hit_order,
        )
    )
    reasons: set[str] = set()
    if posting_truncated:
        reasons.add("posting_budget")
    if seed_truncated:
        reasons.add("graph_seed_budget")
    if neighbor_truncated:
        reasons.add("graph_neighbor_budget")
    returned = hits[:top_k]
    return SearchResult(
        query=query,
        normalized_query=normalized,
        query_tokens=tokens,
        hits=returned,
        matched_candidate_count=matched,
        eligible_candidate_count=len(eligible),
        graph_candidate_count=graph_candidates,
        filters=active_filters,
        top_k=top_k,
        max_examined_postings=max_examined_postings,
        examined_postings=examined,
        graph_seed_budget=max_graph_seeds,
        graph_neighbor_budget=max_graph_neighbors,
        truncation_reasons=tuple(sorted(reasons)),
        graph_context_used=use_context and any(hit.has_graph_context for hit in returned),
        index_snapshot_id=index.snapshot_id,
        index_document_count=index.document_count,
        analysis_completeness=index.analysis_completeness if analysis_completeness is None else analysis_completeness,
    )


def search_endpoints(index: LexicalSearchIndex, query: str, **options: Any) -> SearchResult:
    """Rank API_ENDPOINT entities only; delegates to the shared lexical engine."""
    return _filtered_search(index, query, frozenset((EntityKind.API_ENDPOINT,)), options)


def search_tests(index: LexicalSearchIndex, query: str, **options: Any) -> SearchResult:
    """Rank TEST entities only; delegates to the shared lexical engine."""
    return _filtered_search(index, query, frozenset((EntityKind.TEST,)), options)


def search_database_operations(index: LexicalSearchIndex, query: str, **options: Any) -> SearchResult:
    """Rank DATABASE_OPERATION entities only; delegates to the shared lexical engine."""
    return _filtered_search(index, query, frozenset((EntityKind.DATABASE_OPERATION,)), options)


def _filtered_search(
    index: LexicalSearchIndex,
    query: str,
    kinds: frozenset[EntityKind],
    options: Mapping[str, Any],
) -> SearchResult:
    """Merge a wrapper's kind restriction with caller filters without duplicating ranking.

    Unknown option names still fail inside ``search_symbols``; only ``filters`` is
    intercepted here so the restriction can be merged instead of replaced.
    """
    supplied = options.get("filters")
    if supplied is not None and not isinstance(supplied, SearchFilters):
        raise TypeError("filters must be SearchFilters or None")
    filters = SearchFilters() if supplied is None else supplied
    merged = SearchFilters(
        entity_kinds=kinds | filters.entity_kinds if filters.entity_kinds else kinds,
        languages=filters.languages,
        path_prefixes=filters.path_prefixes,
        http_methods=filters.http_methods,
        frameworks=filters.frameworks,
        providers=filters.providers,
        operation_kinds=filters.operation_kinds,
        path_completeness=filters.path_completeness,
    )
    remaining = {key: value for key, value in options.items() if key != "filters"}
    return search_symbols(index, query, filters=merged, **remaining)


def explain_hit(hit: SearchHit) -> str:
    """Deterministic plain-text explanation of one hit; no prose generation."""
    lines = [
        f"entity: {hit.name}",
        f"entity_id: {hit.entity_id}",
        f"kind: {hit.entity_kind.value}",
        f"language: {hit.language}",
        f"path: {hit.repository_relative_path}",
        "location: "
        + (
            "none recorded"
            if hit.source_location is None
            else f"{hit.source_location.file_path}:{hit.source_location.start_line}-{hit.source_location.end_line}"
        ),
        f"match_basis: {hit.match_basis.value}",
        f"bm25_score: {hit.bm25_score:.6f}",
        f"exact_match_boost: {hit.exact_match_boost:.6f}",
        f"prefix_boost: {hit.prefix_boost:.6f}",
        f"graph_context_boost: {hit.graph_context_boost:.6f}",
        f"relevance_score: {hit.relevance_score:.6f}",
        f"matched_terms: {','.join(hit.matched_terms) or 'none'}",
        f"matched_fields: {','.join(hit.matched_fields) or 'none'}",
    ]
    if hit.context_support:
        lines.append("supporting_relationships:")
        for support in hit.context_support:
            lines.append(
                f"  {support.relationship_kind.value} {support.relationship_id}"
                f" ({support.direction.value}) -> {support.neighbor_name}"
                f" [{support.confidence.value}"
                f"/{'' if support.confidence_score is None else support.confidence_score}]"
            )
            for item in support.evidence:
                lines.append(
                    f"    evidence: {item.location.file_path}:{item.location.start_line}"
                    f"-{item.location.end_line} via {item.analysis_method}"
                )
    return "\n".join(lines)


def search_summary(index: LexicalSearchIndex) -> str:
    """Measured index statistics as plain text; useful for reproducible smoke output."""
    payload = index.to_dict()
    return "\n".join(f"{key}: {value}" for key, value in sorted(payload.items()))
