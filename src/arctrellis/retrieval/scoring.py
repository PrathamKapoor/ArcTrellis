"""Deterministic BM25 relevance and explicit exact-match boost policy.

A BM25 score is a lexical relevance score only. It is not a probability, not a
confidence, not a semantic-correctness measure, not a runtime-execution estimate
and not a graph confidence. Relationship confidence is retained separately on
every context contribution and is never multiplied into relevance.

The whole policy is fixed constants. No query string, fixture name, entity name
or benchmark identity can change a weight (D-132).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import IntEnum
from math import isfinite, log
from typing import TYPE_CHECKING

from .errors import RetrievalInvariantError
from .normalization import fold, normalize_exact

if TYPE_CHECKING:
    from .documents import SearchDocument

BM25_K1 = 1.2
BM25_B = 0.75

EXACT_QUALIFIED_NAME_BOOST = 8.0
EXACT_NAME_BOOST = 6.0
EXACT_ROUTE_BOOST = 5.0
EXACT_NORMALIZED_NAME_BOOST = 3.0
NAME_PREFIX_BOOST = 0.5
NAME_PREFIX_MIN_QUERY_CHARACTERS = 4

#: Per-field relevance weights (D-134). A developer's intent is stated in the
#: entity name far more often than in a repository path, and a repeated generic
#: token inside a long path or qualified name must not outweigh a real symbol
#: name. Every weight is an exact binary fraction, so weighted counts compare
#: exactly and results stay reproducible.
FIELD_WEIGHTS: Mapping[str, float] = {
    "name": 3.0,
    "qualified_name": 2.0,
    "http_method": 2.0,
    "route_path": 2.0,
    "framework": 1.5,
    "provider": 1.5,
    "operation_kind": 1.5,
    "operation_name": 1.5,
    "target_name": 1.5,
    "imported_name": 1.5,
    "binding": 1.5,
    "module": 1.0,
    "alias": 1.0,
    "import_form": 1.0,
    "is_type_only": 1.0,
    "target_basis": 1.0,
    "effect_stage": 1.0,
    "registration_kind": 1.0,
    "composition_scope": 1.0,
    "path_completeness": 1.0,
    "entity_kind": 0.5,
    "language": 0.5,
    "repository_relative_path": 0.5,
}

DEFAULT_FIELD_WEIGHT = 1.0

_EXACT_BOOSTS: Mapping[int, float] = {
    5: EXACT_QUALIFIED_NAME_BOOST,
    4: EXACT_NAME_BOOST,
    3: EXACT_ROUTE_BOOST,
    2: EXACT_NORMALIZED_NAME_BOOST,
    1: NAME_PREFIX_BOOST,
}


def field_weight(name: str) -> float:
    """Relevance weight of one projected field; unlisted fields keep the default."""
    return FIELD_WEIGHTS.get(name, DEFAULT_FIELD_WEIGHT)


def weighted_document_length(document: SearchDocument) -> float:
    """BM25 length normalization factor: weighted token count across fields."""
    return sum(field_weight(item.name) * len(item.tokens) for item in document.fields)


def weighted_term_frequency(document: SearchDocument, term: str) -> float:
    """Weighted in-document term frequency summed across every matching field."""
    return sum(field_weight(item.name) * item.tokens.count(term) for item in document.fields if term in item.tokens)


class ExactMatchTier(IntEnum):
    """Priority of the strongest exact-match rule a document satisfies."""

    NONE = 0
    NAME_PREFIX = 1
    EXACT_NORMALIZED_NAME = 2
    EXACT_ROUTE = 3
    EXACT_NAME = 4
    EXACT_QUALIFIED_NAME = 5


def _alphanumeric(value: str) -> str:
    return "".join(character for character in fold(value) if character.isalnum())


def route_key(document: SearchDocument) -> str | None:
    """Canonical ``METHOD path`` retrieval key, or None when the entity has no route."""
    method = document.field_value("http_method")
    route = document.field_value("route_path")
    return None if not method or not route else f"{method} {route}"


def exact_match_tiers(document: SearchDocument, query: str) -> tuple[tuple[ExactMatchTier, str], ...]:
    """Every exact rule the document satisfies, in ascending priority order.

    Rules, strongest first:

    1. the whole query equals the canonical qualified name;
    2. the whole query equals the canonical entity name;
    3. the whole query equals the canonical ``METHOD path`` route key;
    4. the alphanumeric-only forms of query and name are equal, so separator
       spelling cannot hide an exact name;
    5. the name begins with the query, for prefixes of at least three characters.
    """
    normalized = normalize_exact(query)
    if not normalized:
        return ()
    compact = _alphanumeric(query)
    found: list[tuple[ExactMatchTier, str]] = []
    if normalize_exact(document.qualified_name) == normalized:
        found.append((ExactMatchTier.EXACT_QUALIFIED_NAME, "exact:qualified_name"))
    if normalize_exact(document.name) == normalized:
        found.append((ExactMatchTier.EXACT_NAME, "exact:name"))
    key = route_key(document)
    if key is not None and normalize_exact(key) == normalized:
        found.append((ExactMatchTier.EXACT_ROUTE, "exact:route"))
    name_compact = _alphanumeric(document.name)
    if compact and name_compact == compact:
        found.append((ExactMatchTier.EXACT_NORMALIZED_NAME, "exact:normalized_name"))
    elif (
        len(compact) >= NAME_PREFIX_MIN_QUERY_CHARACTERS
        and name_compact.startswith(compact)
        and name_compact != compact
    ):
        found.append((ExactMatchTier.NAME_PREFIX, "prefix:name"))
    return tuple(found)


def exact_match_boost(
    document: SearchDocument, query: str, tiers: tuple[tuple[ExactMatchTier, str], ...]
) -> tuple[float, ExactMatchTier]:
    """Return the single strongest exact boost and its tier.

    Only the strongest applicable tier is applied so that one document cannot
    accumulate several exact bonuses for the same fact. Every satisfied rule is
    still reported through :func:`exact_match_tiers` and match reasons.
    """
    if not tiers:
        return 0.0, ExactMatchTier.NONE
    strongest = max(tiers, key=lambda item: item[0])
    return _EXACT_BOOSTS[int(strongest[0])], strongest[0]


def bm25_score(
    document: SearchDocument,
    document_length: float,
    average_document_length: float,
    document_count: int,
    term_frequencies: Mapping[str, float],
    document_frequency: Mapping[str, int],
    *,
    k1: float = BM25_K1,
    b: float = BM25_B,
) -> float:
    """Standard BM25 over the terms that actually occur in this document.

    ``IDF(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))`` and
    ``tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / average_length))``.

    ``tf`` and ``length`` are the field-weighted values from
    :func:`weighted_term_frequency` and :func:`weighted_document_length`.

    Missing terms contribute nothing. An empty corpus is a defined zero case. A
    zero average length means there is no length information at all (an empty
    corpus), so the length-normalization term is dropped instead of dividing by
    zero and the denominator becomes ``tf``. Results are finite by construction
    and verified before returning.
    """
    if type(k1) not in (int, float):
        raise TypeError("k1 must be a number")
    if not isfinite(float(k1)) or k1 < 0:
        raise ValueError("k1 must be a finite nonnegative number")
    if type(b) not in (int, float):
        raise TypeError("b must be a number")
    if not isfinite(float(b)) or not 0 <= b <= 1:
        raise ValueError("b must be a finite number between 0 and 1")
    if document_count <= 0:
        return 0.0
    normalization = (
        0.0 if average_document_length <= 0 else k1 * (1 - b + b * (document_length / average_document_length))
    )
    score = 0.0
    for term, frequency in term_frequencies.items():
        document_frequency_count = document_frequency.get(term, 0)
        if document_frequency_count <= 0:
            continue
        idf = log(1 + (document_count - document_frequency_count + 0.5) / (document_frequency_count + 0.5))
        score += idf * (frequency * (k1 + 1)) / (frequency + normalization)
    if not isfinite(score):
        raise RetrievalInvariantError("BM25 produced a non-finite score")
    return score
