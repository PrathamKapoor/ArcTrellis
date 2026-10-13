"""One deliberate analysis entry point and the snapshot every query reads.

This is orchestration only: it calls the existing analysis stages in their real
dependency order and never reimplements parsing, resolution or querying. The
snapshot owns the final evidence graph and the retrieval index built from that
same graph, so structural queries and lexical search can never be served from
two different revisions (D-145).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from os import PathLike
from types import MappingProxyType
from typing import Any

from arctrellis.calls import resolve_calls
from arctrellis.core import EntityKind
from arctrellis.database import materialize_database_graph
from arctrellis.frameworks import resolve_framework_flow, resolve_http_endpoints
from arctrellis.graph import CodeGraph
from arctrellis.indexing import index_repository
from arctrellis.parsing.source import DEFAULT_MAX_SOURCE_BYTES
from arctrellis.query import AnalysisCompleteness, AnalysisSummary
from arctrellis.resolution import resolve_imports
from arctrellis.retrieval import LexicalSearchIndex, SearchDocument, build_search_index
from arctrellis.test_semantics import analyze_tests

from .errors import AnalysisPipelineError, OrchestrationInvariantError


@dataclass(frozen=True, slots=True)
class AnalysisCounts:
    """Measured structural totals for one analysis snapshot."""

    supported_file_count: int
    complete_file_count: int
    partial_file_count: int
    failed_file_count: int
    entity_count: int
    relationship_count: int
    endpoint_count: int
    test_count: int
    database_operation_count: int
    retrieval_document_count: int
    retrieval_term_count: int

    def __post_init__(self) -> None:
        for name in (
            "supported_file_count",
            "complete_file_count",
            "partial_file_count",
            "failed_file_count",
            "entity_count",
            "relationship_count",
            "endpoint_count",
            "test_count",
            "database_operation_count",
            "retrieval_document_count",
            "retrieval_term_count",
        ):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise OrchestrationInvariantError(f"{name} must be a nonnegative integer")

    @property
    def fully_analyzed(self) -> bool:
        return self.partial_file_count == 0 and self.failed_file_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "supported_file_count": self.supported_file_count,
            "complete_file_count": self.complete_file_count,
            "partial_file_count": self.partial_file_count,
            "failed_file_count": self.failed_file_count,
            "entity_count": self.entity_count,
            "relationship_count": self.relationship_count,
            "endpoint_count": self.endpoint_count,
            "test_count": self.test_count,
            "database_operation_count": self.database_operation_count,
            "retrieval_document_count": self.retrieval_document_count,
            "retrieval_term_count": self.retrieval_term_count,
            "fully_analyzed": self.fully_analyzed,
        }


@dataclass(frozen=True, slots=True)
class AnalysisSnapshot:
    """Completed analysis: one final graph plus the retrieval index built from it.

    ``graph`` is the ordinary mutable ``CodeGraph`` that every existing analysis
    result already returns; this frozen record does not freeze it. Callers must
    treat a snapshot as a completed, unmutated revision, exactly as the earlier
    phase results require.
    """

    counts: AnalysisCounts
    analysis_completeness: AnalysisCompleteness
    graph: CodeGraph
    retrieval: LexicalSearchIndex
    _by_qualified_name: Mapping[str, tuple[str, ...]] = field(init=False, repr=False, compare=False)
    _by_route: Mapping[tuple[str, str], tuple[str, ...]] = field(init=False, repr=False, compare=False)
    _by_entity_id: Mapping[str, SearchDocument] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.graph, CodeGraph):
            raise OrchestrationInvariantError("snapshot requires a completed CodeGraph")
        if not isinstance(self.retrieval, LexicalSearchIndex):
            raise OrchestrationInvariantError("snapshot requires a LexicalSearchIndex")
        if not isinstance(self.analysis_completeness, AnalysisCompleteness):
            raise OrchestrationInvariantError("analysis_completeness must be AnalysisCompleteness")
        entity_ids = {entity.id for entity in self.graph.entities()}
        if self.retrieval.document_count != self.graph.entity_count:
            raise OrchestrationInvariantError("retrieval index must project exactly the final graph entities")
        if set(self.retrieval.documents_by_id) != entity_ids:
            raise OrchestrationInvariantError("retrieval documents must correspond one-to-one with graph entities")
        by_qualified: dict[str, list[str]] = {}
        by_route: dict[tuple[str, str], list[str]] = {}
        for document in self.retrieval.documents:
            by_qualified.setdefault(document.qualified_name, []).append(document.entity_id)
            method = document.field_value("http_method")
            route = document.field_value("route_path")
            if method is not None and route is not None and document.entity_kind is EntityKind.API_ENDPOINT:
                by_route.setdefault((method, route), []).append(document.entity_id)
        object.__setattr__(
            self,
            "_by_qualified_name",
            MappingProxyType({key: tuple(sorted(value)) for key, value in by_qualified.items()}),
        )
        object.__setattr__(
            self,
            "_by_route",
            MappingProxyType({key: tuple(sorted(value)) for key, value in by_route.items()}),
        )
        object.__setattr__(self, "_by_entity_id", self.retrieval.documents_by_id)

    @property
    def snapshot_id(self) -> str:
        """Content identity of the retrieval projection of this graph."""
        return self.retrieval.snapshot_id

    def document(self, entity_id: str) -> SearchDocument | None:
        """Return the projected canonical document, or None when absent."""
        return self._by_entity_id.get(entity_id)

    def entities_with_qualified_name(self, qualified_name: str) -> tuple[str, ...]:
        """Exact canonical qualified-name matches, sorted by entity ID."""
        if not isinstance(qualified_name, str) or not qualified_name:
            return ()
        return self._by_qualified_name.get(qualified_name, ())

    def entities_with_route(self, http_method: str, route_path: str) -> tuple[str, ...]:
        """Exact canonical endpoint registrations, sorted by entity ID."""
        return self._by_route.get((http_method, route_path), ())

    def documents(self) -> tuple[SearchDocument, ...]:
        return self.retrieval.documents

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "analysis_completeness": self.analysis_completeness.value,
            "counts": self.counts.to_dict(),
            "graph_context_edge_count": self.retrieval.context_edge_count,
            "context_capped_list_count": self.retrieval.context_capped_list_count,
        }


def analyze_repository(
    root: str | PathLike[str],
    *,
    max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES,
    include_graph_context: bool = True,
    max_context_neighbors: int = 16,
) -> AnalysisSnapshot:
    """Analyze one local repository into a completed, queryable snapshot.

    The stage order below is the real dependency order of the existing analysis
    packages, not a guess: imports need the index, calls need imports, endpoints
    need calls, framework flow needs endpoints, tests need calls and flow, and
    database materialization needs the test-enriched graph. The retrieval index
    is built from that final graph, never from an intermediate one.

    Discovery failures and graph-collision invariants propagate as their existing
    typed ingestion/indexing errors rather than being swallowed. Per-file source
    failures are already bounded ``FAILED`` outcomes inside indexing and are
    reported through the counts and analysis completeness (D-145).

    No stage retains ParsedSource, source bytes or syntax trees after it returns,
    and nothing here executes, imports or installs target code.
    """
    index_result = index_repository(root, max_source_bytes=max_source_bytes)
    imports = resolve_imports(index_result)
    calls = resolve_calls(index_result, imports)
    endpoints = resolve_http_endpoints(index_result, imports, calls)
    flow = resolve_framework_flow(index_result, imports, calls, endpoints)
    tests = analyze_tests(index_result, imports, calls, base_graph=flow.graph)
    database = materialize_database_graph(index_result, base_graph=tests.graph)
    completeness = AnalysisSummary(
        index_result.complete_file_count, index_result.partial_file_count, index_result.failed_file_count
    ).completeness
    retrieval = build_search_index(
        database.graph,
        analysis_completeness=completeness,
        include_graph_context=include_graph_context,
        max_context_neighbors=max_context_neighbors,
    )
    if retrieval.document_count != database.graph.entity_count:
        raise AnalysisPipelineError("retrieval snapshot does not cover the final analysis graph")
    entities = database.graph.entities()

    def kind_count(kind: EntityKind) -> int:
        return sum(1 for entity in entities if entity.kind is kind)

    counts = AnalysisCounts(
        supported_file_count=index_result.supported_file_count,
        complete_file_count=index_result.complete_file_count,
        partial_file_count=index_result.partial_file_count,
        failed_file_count=index_result.failed_file_count,
        entity_count=len(entities),
        relationship_count=database.graph.relationship_count,
        endpoint_count=kind_count(EntityKind.API_ENDPOINT),
        test_count=kind_count(EntityKind.TEST),
        database_operation_count=kind_count(EntityKind.DATABASE_OPERATION),
        retrieval_document_count=retrieval.document_count,
        retrieval_term_count=retrieval.term_count,
    )
    return AnalysisSnapshot(
        counts=counts,
        analysis_completeness=completeness,
        graph=database.graph,
        retrieval=retrieval,
    )
