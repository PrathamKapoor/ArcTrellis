"""Deterministic retrieval evaluation with independent relevance judgments.

This is not an LLM benchmark and not a semantic-similarity benchmark. It measures
whether ArcTrellis returns the canonical entities a developer already declared
relevant, using standard-library arithmetic and explicit, human-specified
judgments that live outside the ranking code.

Metric definitions, all macro-averaged over evaluated queries and computed at a
documented cut-off ``k``:

- ``recall@k``    = |top-k retrieved and relevant| / |relevant|
- ``precision@k`` = |top-k retrieved and relevant| / k
- ``mrr@k``       = 1 / rank of the first relevant result inside the top k, else 0
- ``hit_rate@k``  = 1 when at least one relevant result is inside the top k, else 0

Queries whose judgments resolve to no relevant entity are excluded from the
average and reported separately, because averaging over an empty target would
manufacture a number with no meaning. Duplicate retrieved identifiers are
de-duplicated by first occurrence and reported.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import isfinite

from arctrellis.core import EntityKind

from .documents import SearchDocument
from .errors import RetrievalError
from .index import LexicalSearchIndex
from .normalization import normalize_exact, tokenize
from .search import SearchFilters, SearchResult, search_symbols

BASELINE = "exact_substring_baseline"
BM25 = "bm25_lexical"
GRAPH = "bm25_with_graph_context"

EVALUATION_MODES = (BASELINE, BM25, GRAPH)

_EXACT_VALUE_TIER = 0
_SUBSTRING_TIER = 1
_TOKEN_CONTAINMENT_TIER = 2
_SHARED_TOKEN_TIER = 3
_NO_MATCH_TIER = 4


class RetrievalEvaluationError(RetrievalError):
    """Judgments, metrics or comparison inputs violate the evaluation contract."""


@dataclass(frozen=True, slots=True)
class ExpectedEntity:
    """Human-authored selector for a relevant canonical entity.

    Selectors deliberately avoid canonical UUID identities so judgments stay
    readable and independent of the implementation that produces the IDs.
    """

    entity_kind: EntityKind
    name: str
    path: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.entity_kind, EntityKind):
            raise TypeError("entity_kind must be EntityKind")
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("expected entity name must be a nonempty string")
        if self.path is not None and (not isinstance(self.path, str) or not self.path):
            raise ValueError("expected entity path must be a nonempty string or None")

    @property
    def label(self) -> str:
        location = "" if self.path is None else f"@{self.path}"
        return f"{self.entity_kind.value}:{self.name}{location}"

    def matches(self, document: SearchDocument) -> bool:
        return (
            document.entity_kind is self.entity_kind
            and document.name == self.name
            and (self.path is None or document.repository_relative_path == self.path)
        )

    def to_dict(self) -> dict[str, object]:
        return {"entity_kind": self.entity_kind.value, "name": self.name, "path": self.path}


@dataclass(frozen=True, slots=True)
class RelevanceJudgment:
    """One query with its independently specified relevant canonical entities."""

    query: str
    expected: tuple[ExpectedEntity, ...]
    category: str = "conceptual"
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.query, str) or not self.query:
            raise ValueError("judgment query must be a nonempty string")
        if not isinstance(self.expected, tuple) or any(not isinstance(item, ExpectedEntity) for item in self.expected):
            raise TypeError("expected must be a tuple of ExpectedEntity selectors")
        if len({item.label for item in self.expected}) != len(self.expected):
            raise ValueError("expected selectors must be unique")
        if self.category not in ("exact", "multi_entity", "conceptual"):
            raise ValueError("category must be exact, multi_entity or conceptual")
        if len(self.expected) > 1 and self.category == "exact":
            raise ValueError("an exact judgment expects exactly one canonical entity")
        if self.category == "exact" and not self.expected:
            raise ValueError("an exact judgment must name its single canonical entity")

    @property
    def relevant_labels(self) -> tuple[str, ...]:
        return tuple(sorted(item.label for item in self.expected))

    def resolve(self, index: LexicalSearchIndex) -> tuple[frozenset[str], tuple[str, ...]]:
        """Return canonical IDs and the labels that matched no entity in the corpus."""
        found: set[str] = set()
        unresolved: list[str] = []
        for selector in self.expected:
            matches = frozenset(document.entity_id for document in index.documents if selector.matches(document))
            if matches:
                found |= matches
            else:
                unresolved.append(selector.label)
        return frozenset(found), tuple(sorted(unresolved))

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "category": self.category,
            "note": self.note,
            "expected": [item.to_dict() for item in self.expected],
        }


@dataclass(frozen=True, slots=True)
class QueryOutcome:
    """Measured retrieval outcome for one judgment at one cut-off."""

    query: str
    category: str
    relevant_count: int
    retrieved_ids: tuple[str, ...]
    relevant_retrieved: int
    first_relevant_rank: int | None
    duplicate_identifiers_removed: int

    @property
    def recall(self) -> float:
        return self.relevant_retrieved / self.relevant_count

    @property
    def precision(self) -> float:
        return self.relevant_retrieved / len(self.retrieved_ids) if self.retrieved_ids else 0.0

    @property
    def reciprocal_rank(self) -> float:
        return 0.0 if self.first_relevant_rank is None else 1 / self.first_relevant_rank

    @property
    def hit(self) -> float:
        return 1.0 if self.first_relevant_rank is not None else 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "category": self.category,
            "relevant_count": self.relevant_count,
            "retrieved_count": len(self.retrieved_ids),
            "relevant_retrieved": self.relevant_retrieved,
            "first_relevant_rank": self.first_relevant_rank,
            "duplicate_identifiers_removed": self.duplicate_identifiers_removed,
            "recall": self.recall,
            "precision": self.precision,
            "reciprocal_rank": self.reciprocal_rank,
        }


@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    """Macro-averaged metrics at one cut-off for one retrieval mode."""

    mode: str
    k: int
    evaluated_queries: int
    skipped_queries: int
    recall_at_k: float
    precision_at_k: float
    mrr_at_k: float
    hit_rate_at_k: float

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "k": self.k,
            "evaluated_queries": self.evaluated_queries,
            "skipped_queries": self.skipped_queries,
            f"recall_at_{self.k}": self.recall_at_k,
            f"precision_at_{self.k}": self.precision_at_k,
            f"mrr_at_{self.k}": self.mrr_at_k,
            f"hit_rate_at_{self.k}": self.hit_rate_at_k,
        }


@dataclass(frozen=True, slots=True)
class ModeEvaluation:
    """Metrics plus the measured per-query evidence behind them."""

    metrics: RetrievalMetrics
    outcomes: tuple[QueryOutcome, ...]
    misses: tuple[str, ...]
    improved_over_baseline: tuple[str, ...]
    regressed_versus_baseline: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "metrics": self.metrics.to_dict(),
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
            "misses": list(self.misses),
            "improved_over_baseline": list(self.improved_over_baseline),
            "regressed_versus_baseline": list(self.regressed_versus_baseline),
        }


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationResult:
    """Complete measured comparison; contains only calculated values."""

    judgment_count: int
    k: int
    unresolved_judgment_labels: tuple[str, ...]
    baseline: ModeEvaluation
    bm25: ModeEvaluation
    graph_context: ModeEvaluation

    @property
    def metrics(self) -> tuple[ModeEvaluation, ...]:
        return (self.baseline, self.bm25, self.graph_context)

    def to_dict(self) -> dict[str, object]:
        return {
            "judgment_count": self.judgment_count,
            "k": self.k,
            "unresolved_judgment_labels": list(self.unresolved_judgment_labels),
            "exact_substring_baseline": self.baseline.to_dict(),
            "bm25_lexical": self.bm25.to_dict(),
            "bm25_with_graph_context": self.graph_context.to_dict(),
        }


def _validated_k(k: int) -> int:
    if type(k) is not int or k <= 0:
        raise RetrievalEvaluationError("k must be a positive non-boolean integer")
    return k


def _deduplicate(identifiers: Sequence[str]) -> tuple[tuple[str, ...], int]:
    seen: set[str] = set()
    unique: list[str] = []
    removed = 0
    for identifier in identifiers:
        if identifier in seen:
            removed += 1
            continue
        seen.add(identifier)
        unique.append(identifier)
    return tuple(unique), removed


def exact_substring_baseline(index: LexicalSearchIndex, query: str, *, top_k: int) -> tuple[str, ...]:
    """Simple non-statistical exact/substring lexical ranking baseline.

    A document is placed in the strongest exactness tier any single approved field
    reaches: an exact normalized value match, then a normalized substring match,
    then containment of every query token, then sharing any query token. Ties
    break on the number of fields that contributed and then canonical entity ID.
    It shares no code with BM25, no field weights, no boosts and no graph context.
    """
    normalized = normalize_exact(query)
    tokens = frozenset(tokenize(query))
    if not normalized or not tokens:
        raise RetrievalEvaluationError("baseline queries must contain retrievable text")
    ranked: list[tuple[int, int, str]] = []
    for document in index.documents:
        tier = _NO_MATCH_TIER
        fields = 0
        for item in document.fields:
            shared = tokens & frozenset(item.tokens)
            if not shared:
                continue
            fields += 1
            value = normalize_exact(item.value)
            if value == normalized:
                tier = min(tier, _EXACT_VALUE_TIER)
            elif normalized in value:
                tier = min(tier, _SUBSTRING_TIER)
            elif shared == tokens:
                tier = min(tier, _TOKEN_CONTAINMENT_TIER)
            else:
                tier = min(tier, _SHARED_TOKEN_TIER)
        if tier != _NO_MATCH_TIER:
            ranked.append((tier, -fields, document.entity_id))
    ranked.sort()
    return tuple(identifier for _, _, identifier in ranked)[:top_k]


def _ranked_identifiers(
    mode: str,
    index: LexicalSearchIndex,
    judgment: RelevanceJudgment,
    *,
    top_k: int,
    filters: SearchFilters | None,
) -> Sequence[str]:
    if mode == BASELINE:
        return exact_substring_baseline(index, judgment.query, top_k=top_k)
    if mode not in (BM25, GRAPH):
        raise RetrievalEvaluationError(f"unknown evaluation mode: {mode}")
    result: SearchResult = search_symbols(
        index,
        judgment.query,
        top_k=top_k,
        filters=filters,
        include_graph_context=mode == GRAPH,
    )
    return result.entity_ids()


def _evaluate_mode(
    mode: str,
    index: LexicalSearchIndex,
    resolved: Mapping[str, frozenset[str]],
    judgments: Sequence[RelevanceJudgment],
    *,
    k: int,
    filters: SearchFilters | None,
) -> ModeEvaluation:
    outcomes: list[QueryOutcome] = []
    misses: list[str] = []
    skipped = 0
    for judgment in judgments:
        relevant = resolved[judgment.query]
        if not relevant:
            skipped += 1
            continue
        identifiers, duplicates = _deduplicate(_ranked_identifiers(mode, index, judgment, top_k=k, filters=filters))
        found = [position for position, identifier in enumerate(identifiers, start=1) if identifier in relevant]
        outcomes.append(
            QueryOutcome(
                query=judgment.query,
                category=judgment.category,
                relevant_count=len(relevant),
                retrieved_ids=identifiers,
                relevant_retrieved=len(found),
                first_relevant_rank=found[0] if found else None,
                duplicate_identifiers_removed=duplicates,
            )
        )
        if not found:
            misses.append(judgment.query)
    return ModeEvaluation(
        metrics=_metrics(mode, k, outcomes, skipped),
        outcomes=tuple(outcomes),
        misses=tuple(misses),
        improved_over_baseline=(),
        regressed_versus_baseline=(),
    )


def _metrics(mode: str, k: int, outcomes: Iterable[QueryOutcome], skipped: int) -> RetrievalMetrics:
    measured = tuple(outcomes)
    count = len(measured)
    if count == 0:
        return RetrievalMetrics(mode, k, 0, skipped, 0.0, 0.0, 0.0, 0.0)
    recall = sum(outcome.recall for outcome in measured) / count
    precision = sum(outcome.precision for outcome in measured) / count
    reciprocal = sum(outcome.reciprocal_rank for outcome in measured) / count
    hits = sum(outcome.hit for outcome in measured) / count
    for value in (recall, precision, reciprocal, hits):
        if not isfinite(value):
            raise RetrievalEvaluationError("evaluation metrics must be finite")
    return RetrievalMetrics(mode, k, count, skipped, recall, precision, reciprocal, hits)


def _compare(
    mode: ModeEvaluation,
    baseline: ModeEvaluation,
    baseline_scores: dict[str, float],
    mode_scores: dict[str, float],
) -> ModeEvaluation:
    improved = tuple(
        outcome.query for outcome in mode.outcomes if mode_scores[outcome.query] > baseline_scores[outcome.query]
    )
    regressed = tuple(
        outcome.query for outcome in mode.outcomes if mode_scores[outcome.query] < baseline_scores[outcome.query]
    )
    return ModeEvaluation(
        metrics=mode.metrics,
        outcomes=mode.outcomes,
        misses=mode.misses,
        improved_over_baseline=improved,
        regressed_versus_baseline=regressed,
    )


def evaluate_retrieval(
    index: LexicalSearchIndex,
    judgments: Sequence[RelevanceJudgment],
    *,
    k: int = 5,
    filters: SearchFilters | None = None,
) -> RetrievalEvaluationResult:
    """Measure the exact baseline, BM25 and BM25+graph against one judgment set.

    Judgments are supplied by the caller and never influence ranking. Unresolved
    selectors are reported instead of being silently dropped, and a query with no
    resolvable relevant entity is excluded from every average.
    """
    _validated_k(k)
    if not isinstance(index, LexicalSearchIndex):
        raise RetrievalEvaluationError("evaluate_retrieval requires a LexicalSearchIndex")
    if not isinstance(judgments, Sequence) or isinstance(judgments, str):
        raise RetrievalEvaluationError("judgments must be a sequence of RelevanceJudgment")
    if any(not isinstance(item, RelevanceJudgment) for item in judgments):
        raise RetrievalEvaluationError("judgments must contain only RelevanceJudgment values")
    queries = tuple(judgment.query for judgment in judgments)
    if len(set(queries)) != len(queries):
        raise RetrievalEvaluationError("judgment queries must be unique")
    resolved: dict[str, frozenset[str]] = {}
    unresolved: list[str] = []
    for judgment in judgments:
        identifiers, missing = judgment.resolve(index)
        resolved[judgment.query] = identifiers
        unresolved.extend(f"{judgment.query} -> {label}" for label in missing)
    baseline = _evaluate_mode(BASELINE, index, resolved, judgments, k=k, filters=None)
    bm25 = _evaluate_mode(BM25, index, resolved, judgments, k=k, filters=filters)
    graph = _evaluate_mode(GRAPH, index, resolved, judgments, k=k, filters=filters)
    baseline_scores = {outcome.query: outcome.reciprocal_rank for outcome in baseline.outcomes}
    return RetrievalEvaluationResult(
        judgment_count=len(judgments),
        k=k,
        unresolved_judgment_labels=tuple(sorted(unresolved)),
        baseline=baseline,
        bm25=_compare(bm25, baseline, baseline_scores, {item.query: item.reciprocal_rank for item in bm25.outcomes}),
        graph_context=_compare(
            graph, baseline, baseline_scores, {item.query: item.reciprocal_rank for item in graph.outcomes}
        ),
    )


def format_evaluation(result: RetrievalEvaluationResult) -> str:
    """Deterministic plain-text report of measured values only."""
    k = result.k
    lines = [
        f"Evaluation queries: {result.judgment_count}",
        f"Evaluation K: {k}",
    ]
    for evaluation in result.metrics:
        metrics = evaluation.metrics
        lines.extend(
            [
                f"Mode: {metrics.mode}",
                f"  evaluated queries: {metrics.evaluated_queries}",
                f"  skipped queries: {metrics.skipped_queries}",
                f"  Recall@{k}: {metrics.recall_at_k:.4f}",
                f"  Precision@{k}: {metrics.precision_at_k:.4f}",
                f"  MRR@{k}: {metrics.mrr_at_k:.4f}",
                f"  HitRate@{k}: {metrics.hit_rate_at_k:.4f}",
                f"  misses: {', '.join(evaluation.misses) or 'none'}",
                f"  improved over baseline: {', '.join(evaluation.improved_over_baseline) or 'none'}",
                f"  regressed versus baseline: {', '.join(evaluation.regressed_versus_baseline) or 'none'}",
            ]
        )
    lines.append(f"Unresolved judgment labels: {', '.join(result.unresolved_judgment_labels) or 'none'}")
    return "\n".join(lines)
