"""Deterministic build-time lexical snapshot over canonical entities.

The index is an immutable value: documents sorted by canonical entity ID plus
posting lists and statistics derived from them. It never retains the CodeGraph,
source bytes, syntax trees or parser objects, and it never mutates the graph.

Resource honesty (D-129): ``graph.entities()`` and ``graph.relationships()``
eagerly allocate and sort a complete snapshot tuple *before* any examination
budget applies. Retrieval performs each of those calls exactly once per build and
reuses the resulting projection; it therefore never repeats an eager adjacency
allocation per search hit. Index construction itself is bounded only by the
canonical entity/relationship count, and no memory cap is claimed.
"""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from json import dumps
from types import MappingProxyType
from uuid import NAMESPACE_URL, uuid5

from arctrellis.core import CodeEntity
from arctrellis.graph import CodeGraph
from arctrellis.query import AnalysisCompleteness

from .documents import SearchDocument, build_document
from .errors import InvalidSearchIndexError, RetrievalInvariantError

SNAPSHOT_NAMESPACE = "arctrellis-retrieval-snapshot-v1"

type PostingList = tuple[tuple[str, int], ...]
type PostingLists = Mapping[str, PostingList]


@dataclass(frozen=True, slots=True)
class LexicalSearchIndex:
    """Immutable retrieval snapshot; documents and posting lists are read-only.

    ``postings`` maps a token to ``((entity_id, term_frequency), ...)`` sorted by
    entity ID. ``document_frequency`` is the length of each posting list and
    ``document_lengths`` is the BM25 document length. ``average_document_length``
    is 0.0 for an empty corpus. ``source_entity_count``/``source_relationship_count``
    record the canonical graph counters observed at build time. ``snapshot_id`` is
    a content digest of these documents: it is *not* a repository revision, commit
    or provenance claim. Concurrent external graph mutation after the build is not
    observed; the snapshot never refreshes itself.
    """

    documents: tuple[SearchDocument, ...]
    postings: PostingLists
    document_lengths: Mapping[str, int]
    document_frequency: Mapping[str, int]
    source_entity_count: int
    source_relationship_count: int
    analysis_completeness: AnalysisCompleteness = AnalysisCompleteness.UNKNOWN
    snapshot_id: str = ""
    _documents_by_id: Mapping[str, SearchDocument] = field(init=False, repr=False, compare=False)
    _average_document_length: float = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.documents, tuple) or any(
            not isinstance(document, SearchDocument) for document in self.documents
        ):
            raise TypeError("documents must be a SearchDocument tuple")
        ids = tuple(document.entity_id for document in self.documents)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("documents must be unique and sorted by entity ID")
        if not isinstance(self.postings, Mapping) or not isinstance(self.document_lengths, Mapping):
            raise TypeError("posting maps are required")
        if not isinstance(self.analysis_completeness, AnalysisCompleteness):
            raise TypeError("analysis_completeness must be AnalysisCompleteness")
        lengths = dict(self.document_lengths)
        frequencies = {token: len(postings) for token, postings in self.postings.items()}
        if set(lengths) != set(ids) or any(
            lengths[identifier] != document.token_count
            for identifier, document in zip(ids, self.documents, strict=True)
        ):
            raise RetrievalInvariantError("document lengths must match the projected documents")
        expected: Counter[tuple[str, str]] = Counter()
        for document in self.documents:
            expected.update((token, document.entity_id) for token in document.tokens)
        for token, postings in self.postings.items():
            if not isinstance(postings, tuple) or not postings:
                raise RetrievalInvariantError("posting lists must be nonempty tuples")
            entries = tuple(sorted(postings))
            if entries != postings or len({entry[0] for entry in postings}) != len(postings):
                raise RetrievalInvariantError("posting lists must be unique and sorted by entity ID")
            if any(identifier not in lengths or frequency < 1 for identifier, frequency in postings):
                raise RetrievalInvariantError("posting lists must reference projected documents")
            if any(expected[(token, identifier)] != frequency for identifier, frequency in postings):
                raise RetrievalInvariantError("posting frequencies must equal the projected term counts")
        if dict(self.document_frequency) != frequencies:
            raise RetrievalInvariantError("document frequency must equal the posting list lengths")
        if type(self.source_entity_count) is not int or type(self.source_relationship_count) is not int:
            raise TypeError("source counts must be integers")
        if self.source_entity_count < len(self.documents) or self.source_relationship_count < 0:
            raise ValueError("source counts must cover the projected corpus")
        total = sum(lengths.values())
        object.__setattr__(self, "_documents_by_id", MappingProxyType(dict(zip(ids, self.documents, strict=True))))
        object.__setattr__(
            self,
            "_average_document_length",
            (total / len(self.documents)) if self.documents else 0.0,
        )
        if not isinstance(self.snapshot_id, str) or not self.snapshot_id:
            object.__setattr__(self, "snapshot_id", content_snapshot_id(self.documents))

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def term_count(self) -> int:
        """Distinct indexed retrieval tokens."""
        return len(self.postings)

    @property
    def posting_record_count(self) -> int:
        """Total (document, token) posting records."""
        return sum(len(postings) for postings in self.postings.values())

    @property
    def average_document_length(self) -> float:
        return self._average_document_length

    @property
    def documents_by_id(self) -> Mapping[str, SearchDocument]:
        return self._documents_by_id

    def document(self, entity_id: str) -> SearchDocument | None:
        """Return the projected document, or None when the corpus lacks that entity."""
        if not isinstance(entity_id, str):
            raise TypeError("entity_id must be a string")
        return self._documents_by_id.get(entity_id)

    @property
    def empty(self) -> bool:
        return not self.documents

    def to_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "document_count": self.document_count,
            "term_count": self.term_count,
            "posting_record_count": self.posting_record_count,
            "average_document_length": self.average_document_length,
            "source_entity_count": self.source_entity_count,
            "source_relationship_count": self.source_relationship_count,
            "analysis_completeness": self.analysis_completeness.value,
        }


def content_snapshot_id(documents: tuple[SearchDocument, ...]) -> str:
    """Content-addressed identity of a document tuple; never a revision claim."""
    payload = dumps([SNAPSHOT_NAMESPACE, [document.to_dict() for document in documents]])
    return str(uuid5(NAMESPACE_URL, payload))


def _validated_entities(graph: CodeGraph) -> tuple[CodeEntity, ...]:
    """Read canonical entities once and reject an unusable or corrupt container."""
    if not isinstance(graph, CodeGraph):
        raise InvalidSearchIndexError("build_search_index requires a completed CodeGraph")
    entities = graph.entities()
    if any(not isinstance(entity, CodeEntity) for entity in entities):
        raise RetrievalInvariantError("graph enumeration returned non-CodeEntity records")
    identifiers = tuple(entity.id for entity in entities)
    if len(set(identifiers)) != len(identifiers):
        raise RetrievalInvariantError("graph enumeration returned duplicate entity identities")
    if len(entities) != graph.entity_count:
        raise RetrievalInvariantError("graph enumeration disagrees with its entity count")
    return entities


def _build_postings(documents: tuple[SearchDocument, ...]) -> tuple[PostingLists, Mapping[str, int]]:
    """Invert token counts into entity-ID-ordered posting lists and lengths."""
    frequencies: dict[str, dict[str, int]] = {}
    lengths: dict[str, int] = {}
    for document in documents:
        counts = Counter(document.tokens)
        lengths[document.entity_id] = document.token_count
        for token, count in counts.items():
            frequencies.setdefault(token, {})[document.entity_id] = count
    postings = {token: tuple(sorted(per_document.items())) for token, per_document in sorted(frequencies.items())}
    return MappingProxyType(postings), MappingProxyType(lengths)


def build_search_index(
    graph: CodeGraph,
    *,
    analysis_completeness: AnalysisCompleteness = AnalysisCompleteness.UNKNOWN,
) -> LexicalSearchIndex:
    """Project a completed graph into an immutable deterministic retrieval snapshot.

    This consumes already-produced analysis data: it never scans, parses or opens a
    repository, never calls scan_repository/parse_discovered_file/index_repository
    and never adds or removes graph records. Entity kinds are not filtered or
    synthesized; every canonical entity becomes exactly one document, sorted by
    canonical entity ID, so equal graphs built in different insertion orders yield
    equal indexes.
    """
    if not isinstance(analysis_completeness, AnalysisCompleteness):
        raise TypeError("analysis_completeness must be AnalysisCompleteness")
    entities = _validated_entities(graph)
    documents = tuple(sorted((build_document(entity) for entity in entities), key=lambda item: item.entity_id))
    postings, lengths = _build_postings(documents)
    frequencies = MappingProxyType({token: len(entries) for token, entries in postings.items()})
    return LexicalSearchIndex(
        documents=documents,
        postings=postings,
        document_lengths=lengths,
        document_frequency=frequencies,
        source_entity_count=graph.entity_count,
        source_relationship_count=graph.relationship_count,
        analysis_completeness=analysis_completeness,
    )
