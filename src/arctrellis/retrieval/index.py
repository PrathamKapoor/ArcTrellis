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

from collections.abc import Mapping
from dataclasses import dataclass, field
from json import dumps
from types import MappingProxyType
from uuid import NAMESPACE_URL, uuid5

from arctrellis.core import CodeEntity
from arctrellis.graph import CodeGraph
from arctrellis.query import AnalysisCompleteness

from .context import DEFAULT_MAX_CONTEXT_NEIGHBORS, GraphContextIndex, build_graph_context_index
from .documents import SearchDocument, build_document
from .errors import InvalidSearchIndexError, RetrievalInvariantError
from .scoring import weighted_document_length, weighted_term_frequency

SNAPSHOT_NAMESPACE = "arctrellis-retrieval-snapshot-v1"

type PostingList = tuple[tuple[str, float], ...]
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
    document_lengths: Mapping[str, float]
    document_frequency: Mapping[str, int]
    source_entity_count: int
    source_relationship_count: int
    analysis_completeness: AnalysisCompleteness = AnalysisCompleteness.UNKNOWN
    context: GraphContextIndex | None = None
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
        if self.context is not None:
            if not isinstance(self.context, GraphContextIndex):
                raise TypeError("context must be GraphContextIndex or None")
            if self.context.entity_count != len(self.documents):
                raise RetrievalInvariantError("context must project exactly the indexed corpus")
        lengths = dict(self.document_lengths)
        frequencies = {token: len(postings) for token, postings in self.postings.items()}
        if set(lengths) != set(ids):
            raise RetrievalInvariantError("document lengths must describe exactly the projected documents")
        for identifier, document in zip(ids, self.documents, strict=True):
            if abs(lengths[identifier] - weighted_document_length(document)) > 1e-9:
                raise RetrievalInvariantError("document lengths must equal the weighted projection lengths")
        by_id = {document.entity_id: document for document in self.documents}
        for token, postings in self.postings.items():
            if not isinstance(postings, tuple) or not postings:
                raise RetrievalInvariantError("posting lists must be nonempty tuples")
            entries = tuple(sorted(postings))
            if entries != postings or len({entry[0] for entry in postings}) != len(postings):
                raise RetrievalInvariantError("posting lists must be unique and sorted by entity ID")
            if any(identifier not in lengths or frequency <= 0 for identifier, frequency in postings):
                raise RetrievalInvariantError("posting lists must reference projected documents")
            if any(
                weighted_term_frequency(by_id[identifier], token) != frequency for identifier, frequency in postings
            ):
                raise RetrievalInvariantError("posting frequencies must equal the weighted projection term counts")
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

    @property
    def has_graph_context(self) -> bool:
        """Whether this snapshot carries a usable bounded one-hop context projection."""
        return self.context is not None and self.context.edge_count > 0

    @property
    def context_capped_list_count(self) -> int:
        """Adjacency lists that reached the per-entity neighbor cap at build time."""
        return 0 if self.context is None else self.context.capped_list_count

    @property
    def context_edge_count(self) -> int:
        return 0 if self.context is None else self.context.edge_count

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
            "context_edge_count": self.context_edge_count,
            "context_max_neighbors_per_entity": 0 if self.context is None else self.context.max_neighbors_per_entity,
            "context_capped_list_count": self.context_capped_list_count,
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


def _build_postings(documents: tuple[SearchDocument, ...]) -> tuple[PostingLists, Mapping[str, float]]:
    """Invert weighted term counts into entity-ID-ordered posting lists and lengths."""
    frequencies: dict[str, dict[str, float]] = {}
    lengths: dict[str, float] = {}
    for document in documents:
        lengths[document.entity_id] = weighted_document_length(document)
        for token in sorted(set(document.tokens)):
            frequencies.setdefault(token, {})[document.entity_id] = weighted_term_frequency(document, token)
    postings = {token: tuple(sorted(per_document.items())) for token, per_document in sorted(frequencies.items())}
    return MappingProxyType(postings), MappingProxyType(lengths)


def build_search_index(
    graph: CodeGraph,
    *,
    analysis_completeness: AnalysisCompleteness = AnalysisCompleteness.UNKNOWN,
    include_graph_context: bool = True,
    max_context_neighbors: int = DEFAULT_MAX_CONTEXT_NEIGHBORS,
) -> LexicalSearchIndex:
    """Project a completed graph into an immutable deterministic retrieval snapshot.

    This consumes already-produced analysis data: it never scans, parses or opens a
    repository, never calls scan_repository/parse_discovered_file/index_repository
    and never adds or removes graph records. Entity kinds are not filtered or
    synthesized; every canonical entity becomes exactly one document, sorted by
    canonical entity ID, so equal graphs built in different insertion orders yield
    equal indexes.

    ``graph.entities()`` is read exactly once and ``graph.relationships()`` at most
    once, so the eager snapshot allocation that public graph APIs perform is paid
    once per build instead of once per candidate or hit. The optional one-hop
    context projection is built from that same single relationship read, so the
    lexical corpus and the relationship context can never come from two different
    graph revisions.
    """
    if not isinstance(analysis_completeness, AnalysisCompleteness):
        raise TypeError("analysis_completeness must be AnalysisCompleteness")
    if type(include_graph_context) is not bool:
        raise TypeError("include_graph_context must be a boolean")
    entities = _validated_entities(graph)
    documents = tuple(sorted((build_document(entity) for entity in entities), key=lambda item: item.entity_id))
    postings, lengths = _build_postings(documents)
    frequencies = MappingProxyType({token: len(entries) for token, entries in postings.items()})
    context = None
    if include_graph_context:
        context = build_graph_context_index(
            graph.relationships(),
            frozenset(document.entity_id for document in documents),
            max_neighbors_per_entity=max_context_neighbors,
        )
    return LexicalSearchIndex(
        documents=documents,
        postings=postings,
        document_lengths=lengths,
        document_frequency=frequencies,
        source_entity_count=graph.entity_count,
        source_relationship_count=graph.relationship_count,
        analysis_completeness=analysis_completeness,
        context=context,
    )
