"""Reproducible end-to-end static retrieval measurements; no target code executes.

Every number printed here is computed from a real static analysis run over a
temporary mixed-language repository and a retrieval index built from the
resulting graph. Nothing is hard-coded and nothing is asserted as a universal
performance or quality guarantee.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from arctrellis.query import QueryStatus, trace_endpoint_to_database
from arctrellis.retrieval import build_search_index, search_endpoints, search_symbols
from arctrellis.retrieval.evaluation import evaluate_retrieval, format_evaluation
from tests.retrieval.judgments import JUDGMENTS
from tests.retrieval.repository import MIXED, analysis_context, pipeline, write_repository

QUERIES = (
    "payment",
    "payment service",
    "createPayment",
    "POST /payments",
    "payment database",
    "prisma payment create",
    "sqlalchemy payment",
    "test payment",
    "payment refund",
)

DETAILED = ("createPayment", "payment refund", "POST /payments")


def describe(result, rank, hit):
    location = (
        "none recorded"
        if hit.source_location is None
        else f"{hit.source_location.file_path}:{hit.source_location.start_line}-{hit.source_location.end_line}"
    )
    supports = ",".join(support.relationship_id for support in hit.context_support) or "none"
    print(f"Query: {result.query}")
    print(f"Rank: {rank}")
    print(f"Entity: {hit.name}")
    print(f"Kind: {hit.entity_kind.value}")
    print(f"Language: {hit.language}")
    print(f"Path: {hit.repository_relative_path}")
    print(f"Location: {location}")
    print(f"Match basis: {hit.match_basis.value}")
    print(f"BM25 score: {hit.bm25_score:.6f}")
    print(f"Exact boost: {hit.exact_match_boost:.6f}")
    print(f"Prefix boost: {hit.prefix_boost:.6f}")
    print(f"Graph boost: {hit.graph_context_boost:.6f}")
    print(f"Final score: {hit.relevance_score:.6f}")
    print(f"Matched fields: {','.join(hit.matched_fields) or 'none'}")
    print(f"Matched terms: {','.join(hit.matched_terms) or 'none'}")
    print(f"Supporting relationship IDs: {supports}")
    print(f"Match reasons: {'; '.join(hit.match_reasons)}")
    for support in hit.context_support:
        for item in support.evidence:
            print(
                f"  evidence: {item.location.file_path}:{item.location.start_line}"
                f"-{item.location.end_line} via {item.analysis_method}"
            )
    print()


def main():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        write_repository(root, MIXED)
        index, _, _, database = pipeline(root)
        graph = database.graph
        completeness = analysis_context(index)
        before = (graph.entities(), graph.relationships())
        snapshot = build_search_index(graph, analysis_completeness=completeness)

        lexical = [search_symbols(snapshot, query, top_k=5) for query in QUERIES]
        contextual = [search_symbols(snapshot, query, include_graph_context=True, top_k=5) for query in QUERIES]

        print("Indexed entities:", graph.entity_count)
        print("Indexed relationships:", graph.relationship_count)
        print("Search documents:", snapshot.document_count)
        print("Indexed terms:", snapshot.term_count)
        print("Posting records:", snapshot.posting_record_count)
        print("Average document length:", round(snapshot.average_document_length, 6))
        print("Graph context edges:", snapshot.context_edge_count)
        print("Index snapshot id:", snapshot.snapshot_id)
        print("Analysis completeness:", completeness.value)
        print("Search queries:", len(QUERIES))
        print("")
        print("Lexical hits:", sum(len(result.hits) for result in lexical))
        print("Graph-context hits:", sum(len(result.hits) for result in contextual))
        print("Graph-context queries using context:", sum(result.graph_context_used for result in contextual))
        print(
            "Truncated searches:",
            sum(result.truncated for result in (*lexical, *contextual)),
        )
        print("")

        for query in DETAILED:
            detail = search_symbols(snapshot, query, include_graph_context=True, top_k=3)
            for rank, hit in enumerate(detail.hits, start=1):
                describe(detail, rank, hit)

        print("Retrieved endpoint candidates and existing structural traces:")
        endpoints = search_endpoints(snapshot, "payments", include_graph_context=True, top_k=10)
        found = 0
        for hit in endpoints.hits:
            trace = trace_endpoint_to_database(graph, hit.entity_id, analysis_completeness=completeness)
            if trace.status is QueryStatus.FOUND:
                found += 1
            print(f"  {hit.name} [{hit.repository_relative_path}] status={trace.status.value} paths={len(trace.paths)}")
        print(f"  endpoints with an existing evidence path: {found}")
        verified = next(
            trace
            for hit in endpoints.hits
            for trace in [trace_endpoint_to_database(graph, hit.entity_id, analysis_completeness=completeness)]
            if trace.status is QueryStatus.FOUND
        )
        print("  first verified trace (unchanged existing evidence):")
        print("   ", " -> ".join(entity.name for entity in verified.paths[0].entities))
        print("    relationships:", ", ".join(verified.paths[0].relationship_ids))
        print("")

        print(format_evaluation(evaluate_retrieval(snapshot, JUDGMENTS, k=5)))
        print("")

        rebuilt = build_search_index(pipeline(root)[3].graph, analysis_completeness=completeness)
        deterministic = all(
            search_symbols(rebuilt, query, include_graph_context=True, top_k=5).to_dict()
            == search_symbols(snapshot, query, include_graph_context=True, top_k=5).to_dict()
            for query in QUERIES
        )
        unchanged = before == (graph.entities(), graph.relationships())
        print("Deterministic:", deterministic)
        print("Graph unchanged:", unchanged)
        print("Snapshot identity stable:", rebuilt.snapshot_id == snapshot.snapshot_id)
        assert deterministic and unchanged and rebuilt.snapshot_id == snapshot.snapshot_id and found > 0


if __name__ == "__main__":
    main()
