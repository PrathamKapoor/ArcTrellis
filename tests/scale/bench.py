"""Measured performance reporting; no thresholds are asserted anywhere.

Run with `.venv\\Scripts\\python.exe -m tests.scale.bench`. The script prints the
actual environment, the exact commands used and the observed numbers. It exists so
a performance claim can be checked or refuted, never so one can be assumed. No
test asserts a wall-clock value, so this can never make the suite flaky.
"""

from __future__ import annotations

import json
import platform
import sys
import tempfile
import time
from pathlib import Path

from arctrellis.orchestration import QueryIntent, QueryRequest, analyze_repository, run_query
from tests.scale.fixtures import build_large_repository

PROFILES = (
    ("small", {"module_count": 10, "functions_per_module": 8, "endpoint_count": 5, "hub_degree": 10}),
    ("medium", {"module_count": 60, "functions_per_module": 12, "endpoint_count": 40, "hub_degree": 120}),
    ("large", {"module_count": 150, "functions_per_module": 16, "endpoint_count": 80, "hub_degree": 300}),
)


def _measure(label: str, **kwargs: int) -> dict[str, object]:
    sources = build_large_repository(**kwargs)  # type: ignore[arg-type]
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        total_bytes = 0
        for name, text in sources.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            total_bytes += len(text.encode("utf-8"))

        started = time.perf_counter()
        snapshot = analyze_repository(root)
        analyze_seconds = time.perf_counter() - started

        counts = snapshot.counts
        requests = {
            "search": QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="handler", top_k=25),
            "search_graph_context": QueryRequest(
                intent=QueryIntent.SEARCH_ENTITIES,
                search_text="handler",
                top_k=25,
                include_graph_context=True,
            ),
            "list_endpoints": QueryRequest(intent=QueryIntent.LIST_ENDPOINTS),
            "list_database_callers": QueryRequest(intent=QueryIntent.LIST_DATABASE_CALLERS),
            "ambiguous_trace": QueryRequest(
                intent=QueryIntent.TRACE_ENDPOINT_TO_DATABASE,
                http_method="POST",
                route_path="/payments",
            ),
        }
        timings: dict[str, float] = {}
        for name, request in requests.items():
            query_started = time.perf_counter()
            run_query(snapshot, request)
            timings[name] = time.perf_counter() - query_started
    return {
        "profile": label,
        "source_files": len(sources),
        "source_bytes": total_bytes,
        "entities": counts.entity_count,
        "relationships": counts.relationship_count,
        "retrieval_documents": counts.retrieval_document_count,
        "retrieval_terms": counts.retrieval_term_count,
        "posting_records": snapshot.retrieval.posting_record_count,
        "context_edges": snapshot.retrieval.context_edge_count,
        "analyze_seconds": round(analyze_seconds, 4),
        "query_seconds": {key: round(value, 4) for key, value in timings.items()},
    }


def main() -> int:
    print("ArcTrellis measured performance report")
    print("environment:", platform.platform())
    print("python:", platform.python_version(), sys.executable)
    print("commands:")
    print("  .venv\\Scripts\\python.exe -m tests.scale.bench")
    print("note: no wall-clock threshold is asserted by any test; these are observations only.")
    print()
    results = [_measure(label, **kwargs) for label, kwargs in PROFILES]  # type: ignore[arg-type]
    for result in results:
        print(json.dumps(result, sort_keys=True))
    print()
    print("Interpretation boundary: these numbers describe one machine, one synthetic corpus and")
    print("one build. They are not a throughput guarantee and not comparable to another machine.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
