"""Local read-only HTTP API: routes, contracts, limits and security boundaries.

Every test drives ApiApplication in process, so no public listener is ever opened
for the suite. The one test that binds a socket uses port 0 on 127.0.0.1 and closes
it immediately. Target repositories are untrusted static text.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from arctrellis.api import (
    API_PREFIX,
    MAX_REQUEST_BYTES,
    AnalysisService,
    ApiApplication,
    UnsafeBindError,
    create_server,
    decode_payload,
    encode_payload,
    is_loopback,
    route_table,
)
from arctrellis.api.errors import PayloadTooLargeError
from arctrellis.api.service import AnalysisService as ServiceClass
from tests.orchestration.repository import (
    DUPLICATE_QUALIFIED_NAMES,
    MIXED,
    PARTIAL_SOURCE,
    PLAIN_SOURCE,
    write_sources,
)


class ApiTestCase(unittest.TestCase):
    sources = MIXED

    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls._temporary.name)
        write_sources(cls.root, cls.sources)
        cls.service = AnalysisService.from_root(str(cls.root))
        cls.app = ApiApplication(cls.service)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def get(self, path: str, query: str = ""):
        target = f"{path}?{query}" if query else path
        return self.app.handle("GET", target)

    def post(self, path: str, payload, *, content_type: str | None = "application/json"):
        body = None if payload is None else encode_payload(payload)
        return self.app.handle("POST", path, body, content_type)


class RoutingTests(ApiTestCase):
    def test_every_declared_route_answers(self) -> None:
        self.assertEqual(
            [operation for _, _, operation in route_table()],
            ["health", "summary", "endpoints", "search", "query"],
        )
        self.assertEqual(self.get(f"{API_PREFIX}/health").status, 200)
        self.assertEqual(self.get(f"{API_PREFIX}/summary").status, 200)
        self.assertEqual(self.get(f"{API_PREFIX}/endpoints").status, 200)
        self.assertEqual(self.post(f"{API_PREFIX}/search", {"text": "payment"}).status, 200)
        self.assertEqual(
            self.post(
                f"{API_PREFIX}/query",
                {"intent": "list-database-callers"},
            ).status,
            200,
        )

    def test_unknown_route_is_404(self) -> None:
        response = self.get("/api/v1/unknown")
        self.assertEqual(response.status, 404)
        self.assertEqual(response.payload["error"], "unknown_route")

    def test_wrong_method_is_405_and_names_the_allowed_methods(self) -> None:
        response = self.app.handle("POST", f"{API_PREFIX}/health", b"{}", "application/json")
        self.assertEqual(response.status, 405)
        self.assertEqual(response.payload["error"], "method_not_allowed")
        self.assertIn("GET", response.payload["message"])

    def test_get_on_a_post_route_is_405(self) -> None:
        self.assertEqual(self.get(f"{API_PREFIX}/query").status, 405)

    def test_unversioned_path_is_404(self) -> None:
        self.assertEqual(self.get("/health").status, 404)
        self.assertEqual(self.get("/api/v2/health").status, 404)

    def test_trailing_slash_is_tolerated(self) -> None:
        self.assertEqual(self.get(f"{API_PREFIX}/health/").status, 200)

    def test_responses_are_json_and_bounded(self) -> None:
        for response in (
            self.get(f"{API_PREFIX}/health"),
            self.get(f"{API_PREFIX}/summary"),
            self.post(f"{API_PREFIX}/search", {"text": "payment"}),
        ):
            self.assertEqual(response.headers["Content-Type"], "application/json; charset=utf-8")
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            json.dumps(response.payload)


class HealthAndSummaryTests(ApiTestCase):
    def test_health_reports_readiness_without_disclosing_the_root(self) -> None:
        payload = self.get(f"{API_PREFIX}/health").payload
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["api_version"], "v1")
        self.assertTrue(payload["analysis_available"])
        self.assertIn("loopback", payload["authentication"])
        serialized = json.dumps(payload)
        self.assertNotIn(str(self.root), serialized)
        self.assertNotIn(self.root.name, serialized)

    def test_summary_reports_measured_counts(self) -> None:
        payload = self.get(f"{API_PREFIX}/summary").payload
        counts = payload["counts"]
        self.assertEqual(counts["entity_count"], counts["retrieval_document_count"])
        self.assertGreater(counts["endpoint_count"], 0)
        self.assertEqual(payload["analysis_completeness"], "complete")
        self.assertNotIn(str(self.root), json.dumps(payload))

    def test_summary_and_bundle_agree_on_snapshot_identity(self) -> None:
        summary = self.get(f"{API_PREFIX}/summary").payload
        bundle = self.post(f"{API_PREFIX}/search", {"text": "payment"}).payload
        self.assertEqual(summary["index_snapshot_id"], bundle["index_snapshot_id"])


class SearchTests(ApiTestCase):
    def test_search_returns_ranked_hits_and_selects_nothing(self) -> None:
        payload = self.post(f"{API_PREFIX}/search", {"text": "list payments", "limit": 5}).payload
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["status"], "SEARCH_RESULTS")
        self.assertIsNone(payload["selected_entity"])
        self.assertLessEqual(len(payload["search_hits"]), 5)
        self.assertIn("lexical_relevance_is_not_entity_identity", payload["limitations"])

    def test_search_filters_are_applied(self) -> None:
        payload = self.post(f"{API_PREFIX}/search", {"text": "payment", "kind": "api-endpoint"}).payload
        self.assertTrue(payload["search_hits"])
        for hit in payload["search_hits"]:
            self.assertEqual(hit["entity_kind"], "API_ENDPOINT")

    def test_search_with_no_match_is_a_successful_empty_result(self) -> None:
        response = self.post(f"{API_PREFIX}/search", {"text": "zzzznothingzzzz"})
        self.assertEqual(response.status, 200)
        self.assertEqual(response.payload["search_hits"], [])

    def test_search_requires_text(self) -> None:
        response = self.post(f"{API_PREFIX}/search", {"limit": 3})
        self.assertEqual(response.status, 422)
        self.assertEqual(response.payload["error"], "validation_failed")

    def test_unknown_field_is_rejected_not_ignored(self) -> None:
        response = self.post(f"{API_PREFIX}/search", {"text": "payment", "root": "C:/Windows"})
        self.assertEqual(response.status, 422)
        self.assertIn("root", response.payload["message"])

    def test_boolean_limit_is_rejected(self) -> None:
        response = self.post(f"{API_PREFIX}/search", {"text": "payment", "limit": True})
        self.assertEqual(response.status, 422)
        self.assertIn("limit must be an integer", response.payload["message"])

    def test_string_limit_is_rejected(self) -> None:
        response = self.post(f"{API_PREFIX}/search", {"text": "payment", "limit": "5"})
        self.assertEqual(response.status, 422)

    def test_invalid_boolean_flag_is_rejected(self) -> None:
        response = self.post(f"{API_PREFIX}/search", {"text": "payment", "include_graph_context": "yes"})
        self.assertEqual(response.status, 422)
        self.assertIn("must be a boolean", response.payload["message"])

    def test_empty_text_is_rejected(self) -> None:
        response = self.post(f"{API_PREFIX}/search", {"text": ""})
        self.assertEqual(response.status, 422)

    def test_graph_context_flag_is_accepted(self) -> None:
        response = self.post(f"{API_PREFIX}/search", {"text": "payment", "include_graph_context": True})
        self.assertEqual(response.status, 200)


class QueryTests(ApiTestCase):
    def endpoint_id(self, file_name: str, name: str) -> str:
        payload = self.get(f"{API_PREFIX}/endpoints").payload
        for candidate in payload["candidate_entities"]:
            if candidate["repository_relative_path"] == file_name and candidate["name"] == name:
                return candidate["entity_id"]
        raise AssertionError(f"{name} in {file_name} is missing")

    def test_exact_id_query_returns_the_bundle_contract(self) -> None:
        endpoint = self.endpoint_id("app.py", "POST /payments")
        response = self.post(
            f"{API_PREFIX}/query",
            {"intent": "trace-endpoint-to-database", "entity_id": endpoint},
        )
        self.assertEqual(response.status, 200)
        payload = response.payload
        self.assertEqual(payload["status"], "EVIDENCE_PATHS")
        self.assertEqual(payload["selected_entity"]["entity_id"], endpoint)
        kinds = [item["relationship_kind"] for path in payload["paths"] for item in path["relationships"]]
        self.assertIn("EXPOSES", kinds)
        self.assertIn("CALLS", kinds)
        self.assertIn("WRITES_DATABASE", kinds)

    def test_evidence_preserves_ids_confidence_and_locations(self) -> None:
        endpoint = self.endpoint_id("app.py", "POST /payments")
        payload = self.post(
            f"{API_PREFIX}/query",
            {"intent": "trace-endpoint-to-database", "entity_id": endpoint},
        ).payload
        for path in payload["paths"]:
            self.assertEqual(len(path["entities"]), len(path["relationships"]) + 1)
            for relationship in path["relationships"]:
                self.assertTrue(relationship["relationship_id"])
                self.assertTrue(relationship["confidence"])
                for detail in relationship["evidence"]:
                    self.assertTrue(detail["file_path"])
                    self.assertFalse(detail["file_path"].startswith("/"))
                    self.assertNotIn(":", detail["file_path"])

    def test_method_and_path_selector_resolves_a_unique_route(self) -> None:
        response = self.post(
            f"{API_PREFIX}/query",
            {
                "intent": "trace-endpoint-to-database",
                "method": "get",
                "path": "/reports",
            },
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(response.payload["status"], "NO_KNOWN_PATH")
        self.assertIn("no_known_path_is_not_proof_of_absence", response.payload["limitations"])

    def test_ambiguous_selection_is_409_with_candidates_and_the_bundle(self) -> None:
        response = self.post(
            f"{API_PREFIX}/query",
            {"intent": "trace-endpoint-to-database", "method": "POST", "path": "/payments"},
        )
        self.assertEqual(response.status, 409)
        self.assertEqual(response.payload["error"], "ambiguous_selection")
        bundle = response.payload["bundle"]
        self.assertIsNone(bundle["selected_entity"])
        self.assertGreaterEqual(len(bundle["candidate_entities"]), 2)
        self.assertEqual(bundle["status"], "AMBIGUOUS_SOURCE")

    def test_unknown_entity_id_is_404(self) -> None:
        response = self.post(
            f"{API_PREFIX}/query",
            {
                "intent": "trace-endpoint-to-database",
                "entity_id": "00000000-0000-0000-0000-000000000000",
            },
        )
        self.assertEqual(response.status, 404)
        self.assertEqual(response.payload["error"], "entity_not_found")

    def test_wrong_kind_for_the_intent_is_409(self) -> None:
        payload = self.post(f"{API_PREFIX}/search", {"text": "listPayments", "kind": "function"}).payload
        function_id = payload["search_hits"][0]["entity_id"]
        response = self.post(
            f"{API_PREFIX}/query",
            {"intent": "trace-endpoint-to-database", "entity_id": function_id},
        )
        self.assertEqual(response.status, 409)
        self.assertEqual(response.payload["error"], "invalid_source")

    def test_duplicate_qualified_names_are_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            write_sources(Path(raw), DUPLICATE_QUALIFIED_NAMES)
            app = ApiApplication(AnalysisService.from_root(raw))
            response = app.handle(
                "POST",
                f"{API_PREFIX}/query",
                encode_payload({"intent": "find-callers", "qualified_name": "js/dup.js::handler"}),
                "application/json",
            )
        self.assertEqual(response.status, 409)
        self.assertEqual(len(response.payload["bundle"]["candidate_entities"]), 2)

    def test_unsupported_intent_is_501(self) -> None:
        response = self.post(f"{API_PREFIX}/query", {"intent": "explain-everything"})
        self.assertEqual(response.status, 501)
        self.assertEqual(response.payload["error"], "unsupported_operation")

    def test_missing_intent_is_422(self) -> None:
        response = self.post(f"{API_PREFIX}/query", {"entity_id": "x"})
        self.assertEqual(response.status, 422)
        self.assertIn("intent is required", response.payload["message"])

    def test_conflicting_selectors_are_422(self) -> None:
        response = self.post(
            f"{API_PREFIX}/query",
            {"intent": "find-callers", "entity_id": "x", "qualified_name": "a.py::b"},
        )
        self.assertEqual(response.status, 422)

    def test_selectorless_structural_intent_is_422(self) -> None:
        response = self.post(f"{API_PREFIX}/query", {"intent": "find-callers"})
        self.assertEqual(response.status, 422)

    def test_invalid_operation_kind_is_422(self) -> None:
        response = self.post(f"{API_PREFIX}/query", {"intent": "list-database-callers", "operations": ["drop"]})
        self.assertEqual(response.status, 422)

    def test_free_text_never_implies_a_structural_intent(self) -> None:
        response = self.post(
            f"{API_PREFIX}/query",
            {"intent": "trace-endpoint-to-database", "text": "show me what happens on payment"},
        )
        self.assertEqual(response.status, 422)

    def test_transitive_is_only_valid_for_find_callers(self) -> None:
        payload = self.post(f"{API_PREFIX}/search", {"text": "createPayment", "kind": "function"}).payload
        function_id = next(
            hit["entity_id"] for hit in payload["search_hits"] if hit["qualified_name"] == "payments.py::createPayment"
        )
        rejected = self.post(
            f"{API_PREFIX}/query",
            {"intent": "find-affected-endpoints", "entity_id": function_id, "transitive": True},
        )
        self.assertEqual(rejected.status, 422)
        accepted = self.post(
            f"{API_PREFIX}/query",
            {"intent": "find-callers", "entity_id": function_id, "transitive": True},
        )
        self.assertEqual(accepted.status, 200)


class EndpointInventoryTests(ApiTestCase):
    def test_endpoints_list_every_registration(self) -> None:
        payload = self.get(f"{API_PREFIX}/endpoints").payload
        self.assertEqual(payload["status"], "INVENTORY")
        self.assertTrue(payload["candidate_entities"])

    def test_endpoints_accepts_a_method_filter(self) -> None:
        payload = self.get(f"{API_PREFIX}/endpoints", "method=POST").payload
        self.assertTrue(payload["candidate_entities"])
        for candidate in payload["candidate_entities"]:
            self.assertTrue(candidate["name"].startswith("POST "))

    def test_endpoints_accepts_a_route_filter(self) -> None:
        payload = self.get(f"{API_PREFIX}/endpoints", "method=GET&path=/reports").payload
        self.assertEqual(len(payload["candidate_entities"]), 1)

    def test_endpoints_rejects_unknown_query_parameters(self) -> None:
        response = self.get(f"{API_PREFIX}/endpoints", "root=C%3A%2FWindows")
        self.assertEqual(response.status, 400)
        self.assertEqual(response.payload["error"], "invalid_payload")

    def test_endpoints_rejects_non_integer_limit(self) -> None:
        response = self.get(f"{API_PREFIX}/endpoints", "limit=abc")
        self.assertEqual(response.status, 400)

    def test_endpoints_rejects_repeated_parameters(self) -> None:
        response = self.get(f"{API_PREFIX}/endpoints", "method=GET&method=POST")
        self.assertEqual(response.status, 400)


class PayloadLimitTests(ApiTestCase):
    def test_oversized_body_is_rejected_before_parsing(self) -> None:
        body = b'{"text": "' + b"a" * (MAX_REQUEST_BYTES + 64) + b'"}'
        response = self.app.handle("POST", f"{API_PREFIX}/search", body, "application/json")
        self.assertEqual(response.status, 413)
        self.assertEqual(response.payload["error"], "payload_too_large")

    def test_malformed_json_is_400(self) -> None:
        response = self.app.handle("POST", f"{API_PREFIX}/search", b"{not json", "application/json")
        self.assertEqual(response.status, 400)
        self.assertEqual(response.payload["error"], "invalid_payload")

    def test_non_object_body_is_400(self) -> None:
        response = self.app.handle("POST", f"{API_PREFIX}/search", b"[1,2,3]", "application/json")
        self.assertEqual(response.status, 400)

    def test_wrong_content_type_is_415(self) -> None:
        response = self.app.handle("POST", f"{API_PREFIX}/search", encode_payload({"text": "x"}), "text/plain")
        self.assertEqual(response.status, 415)

    def test_invalid_utf8_body_is_400(self) -> None:
        response = self.app.handle("POST", f"{API_PREFIX}/search", b"\xff\xfe{}", "application/json")
        self.assertEqual(response.status, 400)

    def test_empty_body_is_treated_as_an_empty_payload(self) -> None:
        response = self.app.handle("POST", f"{API_PREFIX}/search", b"", None)
        self.assertEqual(response.status, 422)


class SecurityTests(ApiTestCase):
    def test_no_response_contains_a_traceback_or_absolute_path(self) -> None:
        responses = [
            self.get(f"{API_PREFIX}/health"),
            self.get(f"{API_PREFIX}/summary"),
            self.post(f"{API_PREFIX}/search", {"text": "payment"}),
            self.post(f"{API_PREFIX}/query", {"intent": "find-callers"}),
            self.post(f"{API_PREFIX}/search", {"text": "", "root": str(self.root)}),
        ]
        for response in responses:
            serialized = json.dumps(response.payload)
            self.assertNotIn("Traceback", serialized)
            self.assertNotIn(str(self.root), serialized)
            self.assertNotIn('File \\"', serialized)

    def test_no_request_field_can_change_the_repository_root(self) -> None:
        for payload in (
            {"text": "payment", "root": "C:/Windows"},
            {"intent": "list-endpoints", "directory": "C:/"},
            {"intent": "find-callers", "entity_id": "x", "repository": "C:/Windows"},
        ):
            with self.subTest(payload=payload):
                response = self.post(
                    f"{API_PREFIX}/query" if "intent" in payload else f"{API_PREFIX}/search",
                    payload,
                )
                self.assertEqual(response.status, 422)
                self.assertNotIn(str(self.root), json.dumps(response.payload))

    def test_path_traversal_in_a_selector_is_treated_as_data(self) -> None:
        response = self.post(
            f"{API_PREFIX}/query",
            {"intent": "list-endpoints", "path": "../../../../etc/passwd"},
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(response.payload["status"], "NO_KNOWN_PATH")
        # The traversal string is echoed only as the caller's own selector and is
        # matched against canonical route metadata; no filesystem access occurred.
        self.assertNotIn(str(self.root), json.dumps(response.payload))
        self.assertEqual(response.payload["candidate_entities"], [])

    def test_only_loopback_hosts_are_accepted(self) -> None:
        for host in ("127.0.0.1", "::1", "localhost", "127.0.0.53"):
            self.assertTrue(is_loopback(host), host)
        for host in ("0.0.0.0", "192.168.1.10", "example.com", "", "  ", "10.0.0.1"):
            self.assertFalse(is_loopback(host), host)

    def test_create_server_refuses_a_non_loopback_bind(self) -> None:
        for host in ("0.0.0.0", "192.168.1.10", "example.com"):
            with self.subTest(host=host), self.assertRaises(UnsafeBindError):
                create_server(str(self.root), host=host, port=0)

    def test_create_server_rejects_an_invalid_port(self) -> None:
        for port in (-1, 70000, True, "8080"):
            with self.subTest(port=port), self.assertRaises(ValueError):
                create_server(str(self.root), host="127.0.0.1", port=port)  # type: ignore[arg-type]

    def test_create_server_binds_loopback_on_an_ephemeral_port(self) -> None:
        server = create_server(str(self.root), host="127.0.0.1", port=0)
        try:
            self.assertEqual(server.server_address[0], "127.0.0.1")
            self.assertGreater(server.server_address[1], 0)
        finally:
            server.server_close()

    def test_service_requires_a_snapshot(self) -> None:
        with self.assertRaises(TypeError):
            AnalysisService("not a snapshot")  # type: ignore[arg-type]
        self.assertIs(ServiceClass, AnalysisService)

    def test_application_requires_a_service(self) -> None:
        with self.assertRaises(TypeError):
            ApiApplication("not a service")  # type: ignore[arg-type]

    def test_no_network_client_dependency_is_imported(self) -> None:
        import importlib
        from pathlib import Path as StdPath

        for module_name in ("arctrellis.api.service", "arctrellis.api.app"):
            module = importlib.import_module(module_name)
            source = StdPath(module.__file__).read_text(encoding="utf-8")
            for token in ("urllib.request", "http.client", "requests", "socket.create_connection"):
                self.assertNotIn(token, source, f"{module_name} must not reference {token}")

    def test_decode_payload_is_bounded(self) -> None:
        self.assertEqual(decode_payload(None, None), {})
        with self.assertRaises(PayloadTooLargeError):
            decode_payload(b"a" * (MAX_REQUEST_BYTES + 1), "application/json")


class DeterminismTests(ApiTestCase):
    def test_repeated_requests_are_byte_identical(self) -> None:
        for _ in range(2):
            first = encode_payload(self.post(f"{API_PREFIX}/search", {"text": "payment"}).payload)
            second = encode_payload(self.post(f"{API_PREFIX}/search", {"text": "payment"}).payload)
            self.assertEqual(first, second)

    def test_encoding_is_stable_across_key_order(self) -> None:
        self.assertEqual(encode_payload({"a": 1, "b": 2}), encode_payload({"b": 2, "a": 1}))

    def test_api_and_library_agree_on_canonical_evidence(self) -> None:
        from arctrellis.orchestration import QueryIntent, QueryRequest, run_query

        payload = self.post(f"{API_PREFIX}/search", {"text": "payment", "kind": "api-endpoint"}).payload
        endpoint = payload["search_hits"][0]["entity_id"]
        api_bundle = self.post(
            f"{API_PREFIX}/query",
            {"intent": "trace-endpoint-to-database", "entity_id": endpoint},
        ).payload
        library_bundle = run_query(
            self.service.snapshot,
            QueryRequest(intent=QueryIntent.TRACE_ENDPOINT_TO_DATABASE, entity_id=endpoint),
        ).to_dict()
        self.assertEqual(api_bundle, library_bundle)


class PartialAnalysisTests(unittest.TestCase):
    def test_partial_repository_is_reported_not_hidden(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            write_sources(Path(raw), PARTIAL_SOURCE)
            app = ApiApplication(AnalysisService.from_root(raw))
            health = app.handle("GET", f"{API_PREFIX}/health").payload
            summary = app.handle("GET", f"{API_PREFIX}/summary").payload
            search = app.handle(
                "POST",
                f"{API_PREFIX}/search",
                encode_payload({"text": "goodFunction"}),
                "application/json",
            ).payload
        self.assertNotEqual(health["analysis_completeness"], "complete")
        self.assertGreater(summary["counts"]["partial_file_count"], 0)
        self.assertIn("source_analysis_was_partial_or_failed", search["limitations"])
        self.assertTrue(search["search_hits"])

    def test_plain_repository_has_no_database_operations(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            write_sources(Path(raw), PLAIN_SOURCE)
            app = ApiApplication(AnalysisService.from_root(raw))
            summary = app.handle("GET", f"{API_PREFIX}/summary").payload
            owners = app.handle(
                "POST",
                f"{API_PREFIX}/query",
                encode_payload({"intent": "list-database-callers"}),
                "application/json",
            )
        self.assertEqual(summary["counts"]["database_operation_count"], 0)
        self.assertEqual(owners.status, 200)
        self.assertEqual(owners.payload["status"], "NO_KNOWN_PATH")


if __name__ == "__main__":
    unittest.main()
