"""Full-product smoke through the in-process API.

Run with `.venv\\Scripts\\python.exe -m tests.api.smoke`. The listener is bound to
an ephemeral loopback port, queried over 127.0.0.1 and closed in the same run. The
printed values are measured; the script asserts that the API and the orchestration
API report identical canonical evidence.
"""

from __future__ import annotations

import http.client
import json
import tempfile
import threading
from pathlib import Path
from typing import Any

from arctrellis.api import API_PREFIX, create_server, server_banner
from arctrellis.orchestration import QueryIntent, QueryRequest, run_query
from tests.orchestration.repository import MIXED, write_sources


class Client:
    """Minimal loopback HTTP client; every call targets the configured listener."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, Any]:
        connection = http.client.HTTPConnection(self.host, self.port, timeout=60)
        try:
            body = None if payload is None else json.dumps(payload).encode("utf-8")
            headers = {"Content-Type": "application/json"} if body is not None else {}
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
        finally:
            connection.close()


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        write_sources(root, MIXED)

        server = create_server(str(root), host="127.0.0.1", port=0)
        banner = server_banner(server)
        client = Client(banner["host"], banner["port"])
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        try:
            status, health = client.request("GET", f"{API_PREFIX}/health")
            print("Listener:", banner["host"], banner["port"], "loopback_only:", banner["loopback_only"])
            print("GET /health:", status, health["status"], health["analysis_completeness"])
            print("Health discloses the analyzed root:", str(root) in json.dumps(health))

            status, summary = client.request("GET", f"{API_PREFIX}/summary")
            counts = summary["counts"]
            print()
            print("GET /summary:", status)
            print("Indexed support files:", counts["supported_file_count"])
            print("Complete files:", counts["complete_file_count"])
            print("Partial files:", counts["partial_file_count"])
            print("Failed files:", counts["failed_file_count"])
            print("Entities:", counts["entity_count"])
            print("Relationships:", counts["relationship_count"])
            print("Endpoints:", counts["endpoint_count"])
            print("Tests:", counts["test_count"])
            print("Database operations:", counts["database_operation_count"])
            print("Retrieval documents:", counts["retrieval_document_count"])
            print("Retrieval terms:", counts["retrieval_term_count"])
            print("Index snapshot id:", summary["index_snapshot_id"])

            status, endpoints = client.request("GET", f"{API_PREFIX}/endpoints")
            print()
            print("GET /endpoints:", status, endpoints["status"], len(endpoints["candidate_entities"]), "registrations")

            status, search = client.request("POST", f"{API_PREFIX}/search", {"text": "list payments", "limit": 5})
            print()
            print(
                "POST /search:",
                status,
                search["status"],
                len(search["search_hits"]),
                "hits, selected:",
                search["selected_entity"],
            )

            endpoint = next(
                candidate["entity_id"]
                for candidate in endpoints["candidate_entities"]
                if candidate["repository_relative_path"] == "app.py" and candidate["name"] == "POST /payments"
            )
            status, bundle = client.request(
                "POST", f"{API_PREFIX}/query", {"intent": "trace-endpoint-to-database", "entity_id": endpoint}
            )
            print()
            print("POST /query (exact endpoint):", status, bundle["status"])
            print("Source endpoint: POST /payments [app.py]")
            print("Selected canonical ID:", bundle["selected_entity"]["entity_id"])
            path = bundle["paths"][0]
            for index, relationship in enumerate(path["relationships"]):
                print()
                print(f"{relationship['relationship_kind']} edge:")
                print("  relationship ID:", relationship["relationship_id"])
                print("  source:", path["entities"][index]["entity_id"], path["entities"][index]["name"])
                print("  target:", path["entities"][index + 1]["entity_id"], path["entities"][index + 1]["name"])
                for detail in relationship["evidence"]:
                    print(
                        "  evidence:",
                        detail["analysis_method"],
                        detail["file_path"],
                        f"lines {detail['start_line']}-{detail['end_line']}",
                    )
                print("  confidence:", relationship["confidence"], relationship["confidence_score"])
            print()
            print("Analysis completeness:", bundle["analysis_completeness"])
            print("Query limits:", json.dumps(bundle["plan"]["limits"], sort_keys=True))
            print("Retrieval truncation:", bundle["retrieval_truncation"])
            print("Query truncation:", bundle["graph_truncation"])
            print("Limitations:", bundle["limitations"])

            status, ambiguous = client.request(
                "POST",
                f"{API_PREFIX}/query",
                {"intent": "trace-endpoint-to-database", "method": "POST", "path": "/payments"},
            )
            print()
            print(
                "POST /query (ambiguous):",
                status,
                ambiguous["error"],
                len(ambiguous["bundle"]["candidate_entities"]),
                "candidates, selected:",
                ambiguous["bundle"]["selected_entity"],
            )

            status, missing = client.request(
                "POST",
                f"{API_PREFIX}/query",
                {"intent": "trace-endpoint-to-database", "entity_id": "00000000-0000-0000-0000-000000000000"},
            )
            print("POST /query (unknown id):", status, missing["error"])

            status, rejected = client.request("POST", f"{API_PREFIX}/query", {"intent": "explain-everything"})
            print("POST /query (unsupported intent):", status, rejected["error"])

            status, oversized = client.request("POST", f"{API_PREFIX}/search", {"text": "a" * 70000})
            print("POST /search (oversized):", status, oversized["error"])

            status, unknown = client.request("GET", "/api/v1/unknown")
            print("GET /api/v1/unknown:", status, unknown["error"])

            # The API and the library must report identical canonical evidence.
            from arctrellis.api import AnalysisService

            service = AnalysisService.from_root(str(root))
            library = run_query(
                service.snapshot,
                QueryRequest(intent=QueryIntent.TRACE_ENDPOINT_TO_DATABASE, entity_id=endpoint),
            ).to_dict()
            repeat_status, repeat = client.request(
                "POST", f"{API_PREFIX}/query", {"intent": "trace-endpoint-to-database", "entity_id": endpoint}
            )
            print()
            print("API status:", status_of(bundle), "repeat status:", repeat_status)
            print("API matches the orchestration API exactly:", bundle == library)
            print("Repeated HTTP request is identical:", repeat == library)
            assert bundle == library
            assert repeat == library
        finally:
            server.shutdown()
            thread.join(timeout=60)
            server.server_close()

    print("Smoke complete.")
    return 0


def status_of(payload: dict[str, Any]) -> str:
    return payload["status"]


if __name__ == "__main__":
    raise SystemExit(main())
