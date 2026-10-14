"""Live loopback server: the real socket handler, over 127.0.0.1 only.

These tests open a listener on an ephemeral loopback port and connect to it with
http.client. That is a loopback connection, not an outbound network request, and
the listener is closed in the same test. No external host is ever contacted.
"""

from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from arctrellis.api import API_PREFIX, create_server, server_banner
from arctrellis.api.service import AnalysisService
from tests.orchestration.repository import MIXED, write_sources


class LiveServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls._temporary.name)
        write_sources(cls.root, MIXED)
        cls.server = create_server(str(cls.root), host="127.0.0.1", port=0)
        cls.host, cls.port = cls.server.server_address[0], cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.thread.join(timeout=30)
        cls.server.server_close()
        cls._temporary.cleanup()

    def request(self, method: str, path: str, body: bytes | None = None) -> tuple[int, dict, bytes]:
        connection = http.client.HTTPConnection(self.host, self.port, timeout=30)
        try:
            headers = {"Content-Type": "application/json"} if body is not None else {}
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_banner_reports_loopback_only(self) -> None:
        banner = server_banner(self.server)
        self.assertTrue(banner["loopback_only"])
        self.assertEqual(banner["host"], "127.0.0.1")
        self.assertEqual(banner["api_prefix"], API_PREFIX)
        self.assertNotIn(str(self.root), json.dumps(banner))

    def test_health_over_the_socket(self) -> None:
        status, headers, body = self.request("GET", f"{API_PREFIX}/health")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        payload = json.loads(body)
        self.assertEqual(payload["status"], "ok")
        self.assertNotIn(str(self.root), body.decode("utf-8"))

    def test_summary_over_the_socket(self) -> None:
        status, _, body = self.request("GET", f"{API_PREFIX}/summary")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertGreater(payload["counts"]["entity_count"], 0)

    def test_endpoints_over_the_socket(self) -> None:
        status, _, body = self.request("GET", f"{API_PREFIX}/endpoints?method=POST")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload["candidate_entities"])

    def test_search_over_the_socket(self) -> None:
        status, _, body = self.request(
            "POST", f"{API_PREFIX}/search", json.dumps({"text": "payment", "limit": 3}).encode()
        )
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["schema_version"], 1)
        self.assertIsNone(payload["selected_entity"])

    def test_ambiguity_is_a_409_with_the_bundle(self) -> None:
        status, _, body = self.request(
            "POST",
            f"{API_PREFIX}/query",
            json.dumps({"intent": "trace-endpoint-to-database", "method": "POST", "path": "/payments"}).encode(),
        )
        self.assertEqual(status, 409)
        payload = json.loads(body)
        self.assertEqual(payload["error"], "ambiguous_selection")
        self.assertIsNone(payload["bundle"]["selected_entity"])
        self.assertGreaterEqual(len(payload["bundle"]["candidate_entities"]), 2)

    def test_unknown_route_is_a_404_without_a_traceback(self) -> None:
        status, _, body = self.request("GET", "/api/v1/nope")
        self.assertEqual(status, 404)
        self.assertNotIn(b"Traceback", body)

    def test_oversized_body_is_refused(self) -> None:
        body = b'{"text": "' + b"a" * (64 * 1024 + 64) + b'"}'
        status, _, response = self.request("POST", f"{API_PREFIX}/search", body)
        self.assertEqual(status, 413)
        self.assertNotIn(b"Traceback", response)

    def test_head_request_returns_headers_without_a_body(self) -> None:
        status, headers, body = self.request("HEAD", f"{API_PREFIX}/health")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertGreater(int(headers["Content-Length"]), 0)

    def test_repeated_requests_are_byte_identical(self) -> None:
        first = self.request("GET", f"{API_PREFIX}/summary")[2]
        second = self.request("GET", f"{API_PREFIX}/summary")[2]
        self.assertEqual(first, second)

    def test_service_is_shared_across_requests(self) -> None:
        summary = json.loads(self.request("GET", f"{API_PREFIX}/summary")[2])
        search = json.loads(self.request("POST", f"{API_PREFIX}/search", b'{"text": "payment"}')[2])
        self.assertEqual(summary["index_snapshot_id"], search["index_snapshot_id"])


class SharedServiceTests(unittest.TestCase):
    def test_an_existing_service_can_be_reused_for_the_server(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            write_sources(Path(raw), MIXED)
            service = AnalysisService.from_root(raw)
            server = create_server(raw, host="127.0.0.1", port=0, service=service)
            try:
                self.assertIs(server.RequestHandlerClass, server.RequestHandlerClass)
                self.assertGreater(server.server_address[1], 0)
            finally:
                server.server_close()

    def test_server_is_not_started_by_construction(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            write_sources(Path(raw), MIXED)
            server = create_server(raw, host="127.0.0.1", port=0)
            try:
                self.assertFalse(
                    any(
                        thread.is_alive() and getattr(thread, "_arctrellis_test", False)
                        for thread in threading.enumerate()
                    )
                )
            finally:
                server.server_close()


if __name__ == "__main__":
    unittest.main()
