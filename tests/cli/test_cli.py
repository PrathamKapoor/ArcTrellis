"""CLI adapter behaviour: exit codes, streams, JSON contracts and safety.

Every test drives arctrellis.cli.main.main with in-memory streams, which is the
same code path the installed console entry point uses. The target repositories are
untrusted static text and are never executed, imported or installed.
"""

from __future__ import annotations

import http.client
import io
import json
import tempfile
import time
import unittest
from pathlib import Path

from arctrellis.cli import (
    EXIT_AMBIGUOUS,
    EXIT_ANALYSIS_FAILURE,
    EXIT_SUCCESS,
    EXIT_UNSUPPORTED,
    EXIT_USAGE,
    main,
)
from tests.orchestration.repository import DUPLICATE_QUALIFIED_NAMES, MIXED, PARTIAL_SOURCE, PLAIN_SOURCE, write_sources


def run_cli(*argv: str) -> tuple[int, str, str]:
    """Run the CLI with captured streams and return status, stdout and stderr.

    argparse signals usage errors and help requests by raising ``SystemExit`` with
    a status; refusing to catch it would make the CLI untestable and would also
    hide that argparse's own code 2 is the documented usage status.
    """
    out, err = io.StringIO(), io.StringIO()
    try:
        status = main(list(argv), stdout=out, stderr=err)
    except SystemExit as exit_request:
        code = exit_request.code
        status = 0 if code is None else int(code) if isinstance(code, int) else EXIT_USAGE
    return status, out.getvalue(), err.getvalue()


class CliTestCase(unittest.TestCase):
    sources: dict[str, str] = MIXED

    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls._temporary.name)
        write_sources(cls.root, cls.sources)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def root_text(self) -> str:
        return str(self.root)


class AnalyzeTests(CliTestCase):
    def test_analyze_mixed_repository_prints_measured_counts(self) -> None:
        status, out, err = run_cli("analyze", self.root_text())
        self.assertEqual(status, EXIT_SUCCESS)
        self.assertEqual(err, "")
        for label in (
            "analysis completeness: complete",
            "supported files: 8",
            "complete files: 8",
            "partial files: 0",
            "failed files: 0",
        ):
            self.assertIn(label, out)
        counts = {line.split(": ")[0]: line.split(": ")[1] for line in out.splitlines() if ": " in line}
        self.assertGreater(int(counts["entities"]), 0)
        self.assertEqual(counts["entities"], counts["retrieval documents"])
        self.assertGreater(int(counts["endpoints"]), 0)
        self.assertGreater(int(counts["database operations"]), 0)

    def test_analyze_empty_repository_reports_zeroes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            status, out, err = run_cli("analyze", raw)
        self.assertEqual(status, EXIT_SUCCESS)
        self.assertEqual(err, "")
        self.assertIn("entities: 0", out)
        self.assertIn("relationships: 0", out)
        self.assertIn("retrieval documents: 0", out)

    def test_analyze_partial_repository_does_not_claim_completeness(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            write_sources(root, PARTIAL_SOURCE)
            status, out, _ = run_cli("analyze", str(root))
        self.assertEqual(status, EXIT_SUCCESS)
        self.assertNotIn("analysis completeness: complete", out)
        self.assertIn("note: analysis is not complete", out)
        self.assertNotIn("partial files: 0", out)

    def test_analyze_json_is_one_document_on_stdout(self) -> None:
        status, out, err = run_cli("analyze", self.root_text(), "--json")
        self.assertEqual(status, EXIT_SUCCESS)
        self.assertEqual(err, "")
        payload = json.loads(out)
        self.assertEqual(
            sorted(payload),
            [
                "analysis_completeness",
                "context_capped_list_count",
                "counts",
                "graph_context_edge_count",
                "snapshot_id",
            ],
        )
        self.assertEqual(payload["counts"]["retrieval_document_count"], payload["counts"]["entity_count"])

    def test_analyze_invalid_path_is_an_analysis_failure(self) -> None:
        missing = str(self.root / "absent")
        status, out, err = run_cli("analyze", missing)
        self.assertEqual(status, EXIT_ANALYSIS_FAILURE)
        self.assertEqual(out, "")
        self.assertIn("error:", err)
        self.assertNotIn("Traceback", err)

    def test_analyze_invalid_limit_is_a_usage_failure(self) -> None:
        status, out, err = run_cli("analyze", self.root_text(), "--max-source-bytes", "abc")
        self.assertNotEqual(status, EXIT_SUCCESS)
        self.assertEqual(out, "")
        self.assertNotIn("Traceback", err)


class SearchTests(CliTestCase):
    def test_search_returns_candidates_and_never_selects(self) -> None:
        status, out, err = run_cli("search", self.root_text(), "list payments")
        self.assertEqual(status, EXIT_SUCCESS)
        self.assertEqual(err, "")
        self.assertIn("status: SEARCH_RESULTS", out)
        self.assertIn("none selected", out)
        self.assertIn("relevance is lexical, not identity", out)
        self.assertNotIn("selected entity:", out)

    def test_search_json_matches_the_bundle_contract(self) -> None:
        status, out, err = run_cli("search", self.root_text(), "list payments", "--json", "--limit", "3")
        self.assertEqual(status, EXIT_SUCCESS)
        self.assertEqual(err, "")
        payload = json.loads(out)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["status"], "SEARCH_RESULTS")
        self.assertIsNone(payload["selected_entity"])
        self.assertEqual(len(payload["search_hits"]), 3)
        self.assertEqual(len(payload["candidate_entities"]), 3)
        self.assertEqual(payload["paths"], [])

    def test_search_limit_is_honoured(self) -> None:
        _, out, _ = run_cli("search", self.root_text(), "payment", "--json", "--limit", "1")
        payload = json.loads(out)
        self.assertEqual(len(payload["search_hits"]), 1)

    def test_search_kind_filter_is_applied(self) -> None:
        _, out, _ = run_cli("search", self.root_text(), "payment", "--json", "--kind", "api-endpoint")
        payload = json.loads(out)
        self.assertTrue(payload["search_hits"])
        for hit in payload["search_hits"]:
            self.assertEqual(hit["entity_kind"], "API_ENDPOINT")

    def test_search_unknown_kind_is_a_usage_failure(self) -> None:
        status, out, err = run_cli("search", self.root_text(), "payment", "--kind", "widget")
        self.assertEqual(status, EXIT_USAGE)
        self.assertEqual(out, "")
        self.assertIn("unknown entity kind", err)

    def test_search_invalid_limit_is_a_usage_failure(self) -> None:
        for value in ("0", "-3", "abc"):
            with self.subTest(limit=value):
                status, out, err = run_cli("search", self.root_text(), "payment", "--limit", value)
                self.assertNotEqual(status, EXIT_SUCCESS)
                self.assertEqual(out, "")

    def test_search_limit_above_the_cap_is_a_usage_failure(self) -> None:
        status, _, err = run_cli("search", self.root_text(), "payment", "--limit", "1000")
        self.assertEqual(status, EXIT_USAGE)
        self.assertIn("top_k must not exceed", err)

    def test_search_no_match_reports_not_found_on_stderr_only(self) -> None:
        status, out, err = run_cli("search", self.root_text(), "zzzznothingzzzz", "--json")
        self.assertEqual(status, EXIT_SUCCESS)
        self.assertEqual(json.loads(out)["status"], "SEARCH_RESULTS")
        self.assertIn("not found:", err)


class QueryTests(CliTestCase):
    def endpoint_id(self, method: str, path: str, file_name: str) -> str:
        _, out, _ = run_cli("endpoints", self.root_text(), "--json")
        for candidate in json.loads(out)["candidate_entities"]:
            if candidate["repository_relative_path"] == file_name and candidate["name"] == f"{method} {path}":
                return candidate["entity_id"]
        raise AssertionError(f"{method} {path} in {file_name} is missing from the fixture")

    def test_exact_id_query_traces_to_a_database_write(self) -> None:
        endpoint = self.endpoint_id("POST", "/payments", "app.py")
        status, out, err = run_cli(
            "query", self.root_text(), "--intent", "trace-endpoint-to-database", "--entity-id", endpoint
        )
        self.assertEqual(status, EXIT_SUCCESS)
        self.assertEqual(err, "")
        self.assertIn("status: EVIDENCE_PATHS", out)
        self.assertIn("EXPOSES", out)
        self.assertIn("CALLS", out)
        self.assertIn("WRITES_DATABASE", out)
        self.assertIn("evidence", out)

    def test_exact_id_query_json_preserves_evidence_and_confidence(self) -> None:
        endpoint = self.endpoint_id("POST", "/payments", "app.py")
        _, out, _ = run_cli(
            "query",
            self.root_text(),
            "--intent",
            "trace-endpoint-to-database",
            "--entity-id",
            endpoint,
            "--json",
        )
        payload = json.loads(out)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["status"], "EVIDENCE_PATHS")
        self.assertTrue(payload["paths"])
        for path in payload["paths"]:
            self.assertEqual(len(path["entities"]), len(path["relationships"]) + 1)
            for relationship in path["relationships"]:
                self.assertTrue(relationship["relationship_id"])
                self.assertTrue(relationship["confidence"])
                self.assertTrue(relationship["evidence"])

    def test_endpoint_method_path_query_resolves_a_unique_route(self) -> None:
        status, out, err = run_cli(
            "query",
            self.root_text(),
            "--intent",
            "trace-endpoint-to-database",
            "--method",
            "get",
            "--path",
            "/reports",
        )
        self.assertEqual(status, EXIT_SUCCESS)
        self.assertIn("status: NO_KNOWN_PATH", out)
        self.assertIn("no known structural path", err)
        self.assertIn("not proof that none exists", err)

    def test_ambiguous_endpoint_selector_exits_three_and_prints_candidates(self) -> None:
        status, out, err = run_cli(
            "query",
            self.root_text(),
            "--intent",
            "trace-endpoint-to-database",
            "--method",
            "POST",
            "--path",
            "/payments",
        )
        self.assertEqual(status, EXIT_AMBIGUOUS)
        self.assertIn("status: AMBIGUOUS_SOURCE", out)
        payload = json.loads(
            run_cli(
                "query",
                self.root_text(),
                "--intent",
                "trace-endpoint-to-database",
                "--method",
                "POST",
                "--path",
                "/payments",
                "--json",
            )[1]
        )
        self.assertIsNone(payload["selected_entity"])
        self.assertGreaterEqual(len(payload["candidate_entities"]), 2)
        self.assertIn("ambiguous selection:", err)
        self.assertIn("supply --entity-id", err)

    def test_unknown_entity_id_is_not_found_with_usage_status(self) -> None:
        status, out, err = run_cli(
            "query",
            self.root_text(),
            "--intent",
            "trace-endpoint-to-database",
            "--entity-id",
            "00000000-0000-0000-0000-000000000000",
        )
        self.assertEqual(status, EXIT_USAGE)
        self.assertIn("status: NOT_FOUND_SOURCE", out)
        self.assertIn("not found:", err)

    def test_wrong_kind_for_the_intent_is_reported_as_invalid(self) -> None:
        _, out, _ = run_cli("search", self.root_text(), "listPayments", "--json", "--kind", "function")
        function_id = json.loads(out)["search_hits"][0]["entity_id"]
        status, out, err = run_cli(
            "query", self.root_text(), "--intent", "trace-endpoint-to-database", "--entity-id", function_id
        )
        self.assertEqual(status, EXIT_USAGE)
        self.assertIn("status: INVALID_SOURCE", out)
        self.assertIn("invalid selection:", err)

    def test_free_text_is_not_a_valid_selector_for_a_structural_intent(self) -> None:
        status, out, err = run_cli(
            "query", self.root_text(), "--intent", "trace-endpoint-to-database", "show me payments"
        )
        self.assertEqual(status, EXIT_USAGE)
        self.assertEqual(out, "")
        self.assertIn("TEXT is only valid with --intent search-entities", err)

    def test_missing_selector_is_a_usage_failure(self) -> None:
        status, out, err = run_cli("query", self.root_text(), "--intent", "find-callers")
        self.assertEqual(status, EXIT_USAGE)
        self.assertEqual(out, "")
        self.assertIn("requires an explicit entity selector", err)

    def test_unsupported_intent_exits_five(self) -> None:
        status, out, err = run_cli("query", self.root_text(), "--intent", "explain-everything", "--entity-id", "x")
        self.assertEqual(status, EXIT_UNSUPPORTED)
        self.assertEqual(out, "")
        self.assertIn("unsupported intent", err)

    def test_half_specified_selector_pair_is_rejected(self) -> None:
        status, out, err = run_cli(
            "query", self.root_text(), "--intent", "trace-endpoint-to-database", "--method", "POST"
        )
        self.assertEqual(status, EXIT_USAGE)
        self.assertEqual(out, "")
        self.assertIn("http_method and route_path must be supplied together", err)

    def test_method_only_is_allowed_for_an_inventory_filter(self) -> None:
        status, out, err = run_cli("endpoints", self.root_text(), "--method", "POST")
        self.assertEqual(status, EXIT_SUCCESS)
        self.assertEqual(err, "")
        self.assertIn("status: INVENTORY", out)

    def test_invalid_method_is_rejected(self) -> None:
        status, _, err = run_cli(
            "query",
            self.root_text(),
            "--intent",
            "trace-endpoint-to-database",
            "--method",
            "PURGE",
            "--path",
            "/payments",
        )
        self.assertEqual(status, EXIT_USAGE)
        self.assertIn("http_method", err)

    def test_operation_filter_is_accepted_and_narrows_the_trace(self) -> None:
        _, out, _ = run_cli("database", self.root_text(), "--json")
        self.assertTrue(json.loads(out)["paths"])
        status, out, _ = run_cli("database", self.root_text(), "--operations", "read", "--json")
        self.assertEqual(status, EXIT_SUCCESS)
        payload = json.loads(out)
        for path in payload["paths"]:
            self.assertEqual({item["relationship_kind"] for item in path["relationships"]}, {"READS_DATABASE"})

    def test_invalid_operation_kind_is_a_usage_failure(self) -> None:
        status, _, err = run_cli("database", self.root_text(), "--operations", "drop")
        self.assertEqual(status, EXIT_USAGE)
        self.assertIn("unknown operation kinds", err)

    def test_transitive_is_only_valid_for_find_callers(self) -> None:
        _, out, _ = run_cli("search", self.root_text(), "listPayments", "--json", "--kind", "function")
        function_id = json.loads(out)["search_hits"][0]["entity_id"]
        status, _, err = run_cli(
            "query",
            self.root_text(),
            "--intent",
            "find-affected-endpoints",
            "--entity-id",
            function_id,
            "--transitive",
        )
        self.assertEqual(status, EXIT_USAGE)
        self.assertIn("transitive_callers", err)


class WrapperCommandTests(CliTestCase):
    def test_endpoints_lists_registrations_as_an_inventory(self) -> None:
        status, out, err = run_cli("endpoints", self.root_text())
        self.assertEqual(status, EXIT_SUCCESS)
        self.assertEqual(err, "")
        self.assertIn("status: INVENTORY", out)
        self.assertIn("inventory entities:", out)

    def test_endpoints_accepts_a_method_filter_without_a_path(self) -> None:
        status, out, _ = run_cli("endpoints", self.root_text(), "--method", "POST", "--json")
        self.assertEqual(status, EXIT_SUCCESS)
        payload = json.loads(out)
        self.assertTrue(payload["candidate_entities"])
        for candidate in payload["candidate_entities"]:
            self.assertTrue(candidate["name"].startswith("POST "))

    def test_endpoints_route_filter_returns_one_registration(self) -> None:
        _, out, _ = run_cli("endpoints", self.root_text(), "--method", "GET", "--path", "/reports", "--json")
        self.assertEqual(len(json.loads(out)["candidate_entities"]), 1)

    def test_trace_wrapper_reports_no_known_path(self) -> None:
        status, out, err = run_cli("trace", self.root_text(), "--method", "GET", "--path", "/reports")
        self.assertEqual(status, EXIT_SUCCESS)
        self.assertIn("NO_KNOWN_PATH", out)
        self.assertIn("not proof", err)

    def test_tests_wrapper_finds_a_direct_test(self) -> None:
        _, out, _ = run_cli("search", self.root_text(), "createPayment", "--json", "--kind", "function")
        hits = json.loads(out)["search_hits"]
        function_id = next(hit["entity_id"] for hit in hits if hit["qualified_name"] == "payments.py::createPayment")
        status, out, err = run_cli("tests", self.root_text(), "--entity-id", function_id)
        self.assertEqual(status, EXIT_SUCCESS)
        self.assertEqual(err, "")
        self.assertIn("TESTS", out)

    def test_impact_wrapper_reports_candidate_endpoints(self) -> None:
        _, out, _ = run_cli("search", self.root_text(), "createPayment", "--json", "--kind", "function")
        function_id = next(
            hit["entity_id"]
            for hit in json.loads(out)["search_hits"]
            if hit["qualified_name"] == "payments.py::createPayment"
        )
        status, out, _ = run_cli("impact", self.root_text(), "--entity-id", function_id, "--json")
        self.assertEqual(status, EXIT_SUCCESS)
        payload = json.loads(out)
        self.assertEqual(payload["status"], "EVIDENCE_PATHS")
        kinds = {item["relationship_kind"] for path in payload["paths"] for item in path["relationships"]}
        self.assertIn("EXPOSES", kinds)

    def test_database_wrapper_lists_direct_owners(self) -> None:
        status, out, _ = run_cli("database", self.root_text(), "--json")
        self.assertEqual(status, EXIT_SUCCESS)
        payload = json.loads(out)
        self.assertEqual(payload["status"], "EVIDENCE_PATHS")
        self.assertTrue(payload["paths"])


class StreamSeparationTests(CliTestCase):
    def test_json_mode_writes_valid_json_to_stdout_only(self) -> None:
        data_commands = (
            ("analyze", self.root_text(), "--json"),
            ("search", self.root_text(), "payment", "--json"),
            ("endpoints", self.root_text(), "--json"),
            ("database", self.root_text(), "--json"),
        )
        for argv in data_commands:
            with self.subTest(argv=argv[0]):
                status, out, err = run_cli(*argv)
                self.assertEqual(status, EXIT_SUCCESS)
                json.loads(out)
                self.assertEqual(err, "", "a successful JSON run must not explain anything on stderr")

    def test_json_mode_keeps_diagnostics_off_stdout_when_selection_is_ambiguous(self) -> None:
        status, out, err = run_cli(
            "query",
            self.root_text(),
            "--intent",
            "trace-endpoint-to-database",
            "--method",
            "POST",
            "--path",
            "/payments",
            "--json",
        )
        self.assertEqual(status, EXIT_AMBIGUOUS)
        payload = json.loads(out)
        self.assertEqual(payload["status"], "AMBIGUOUS_SOURCE")
        self.assertNotIn("{", err)
        self.assertNotIn("status:", err)
        self.assertTrue(err.strip(), "an ambiguity must still explain itself on stderr")

    def test_text_mode_writes_no_json_to_stdout(self) -> None:
        _, out, _ = run_cli("analyze", self.root_text())
        self.assertNotIn('"', out)
        self.assertNotIn("{", out)

    def test_failures_write_nothing_to_stdout(self) -> None:
        for argv in (
            ("search", self.root_text(), "payment", "--limit", "0"),
            ("search", self.root_text(), "payment", "--kind", "widget"),
            ("query", self.root_text(), "--intent", "find-callers"),
            ("query", self.root_text(), "--intent", "nope", "--entity-id", "x"),
            ("analyze", str(self.root / "absent")),
        ):
            with self.subTest(argv=argv[0]):
                status, out, err = run_cli(*argv)
                self.assertEqual(out, "")
                self.assertNotEqual(status, EXIT_SUCCESS)
                self.assertIn("error:", err)

    def test_no_output_ever_contains_a_traceback(self) -> None:
        for argv in (
            ("analyze", str(self.root / "absent")),
            ("query", self.root_text(), "--intent", "find-callers"),
            ("search", self.root_text(), "payment", "--limit", "0"),
        ):
            with self.subTest(argv=argv[0]):
                _, out, err = run_cli(*argv)
                self.assertNotIn("Traceback", out + err)
                self.assertNotIn('File "', err)


class DeterminismTests(CliTestCase):
    def test_repeated_runs_produce_identical_output(self) -> None:
        for argv in (
            ("analyze", self.root_text(), "--json"),
            ("search", self.root_text(), "payment", "--json"),
            ("endpoints", self.root_text(), "--json"),
        ):
            with self.subTest(argv=argv[0]):
                first = run_cli(*argv)
                second = run_cli(*argv)
                self.assertEqual(first[0], second[0])
                self.assertEqual(first[1], second[1])

    def test_analyze_is_independent_of_argument_spelling(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.root.parent) as raw:
            write_sources(Path(raw), PLAIN_SOURCE)
            absolute = run_cli("analyze", raw, "--json")[1]
            relative = run_cli("analyze", str(Path(raw)), "--json")[1]
        self.assertEqual(json.loads(absolute)["counts"], json.loads(relative)["counts"])


class SafetyTests(CliTestCase):
    def test_unicode_and_spaced_repository_paths_work(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "unicode repository \N{SNOWMAN}"
            target.mkdir()
            write_sources(target, PLAIN_SOURCE)
            status, out, err = run_cli("analyze", str(target))
        self.assertEqual(status, EXIT_SUCCESS)
        self.assertEqual(err, "")
        self.assertIn("entities:", out)

    def test_target_code_is_never_executed(self) -> None:
        marker = Path(tempfile.gettempdir()) / "arctrellis_cli_must_not_execute.txt"
        self.assertFalse(marker.exists())
        sources = {
            "sideeffect.py": (
                f"import pathlib\npathlib.Path({str(marker)!r}).write_text('executed', encoding='utf-8')\n"
            )
        }
        with tempfile.TemporaryDirectory() as raw:
            write_sources(Path(raw), sources)
            status, out, _ = run_cli("analyze", raw)
        self.assertEqual(status, EXIT_SUCCESS)
        self.assertIn("entities: ", out)
        self.assertFalse(marker.exists())

    def test_target_repository_is_not_modified(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            write_sources(root, MIXED)
            before = {p: p.stat().st_mtime_ns for p in sorted(root.rglob("*")) if p.is_file()}
            run_cli("analyze", raw)
            run_cli("search", raw, "payment")
            after = {p: p.stat().st_mtime_ns for p in sorted(root.rglob("*")) if p.is_file()}
        self.assertEqual(before, after)

    def test_no_network_or_subprocess_primitives_are_imported_by_the_cli(self) -> None:
        import importlib

        module = importlib.import_module("arctrellis.cli.main")
        source = Path(module.__file__).read_text(encoding="utf-8")
        for token in (
            "socket",
            "urllib",
            "http.client",
            "requests",
            "subprocess",
            "os.system",
            "eval(",
            "exec(",
        ):
            self.assertNotIn(token, source, f"the CLI must not reference {token}")
        self.assertNotIn("os.environ", source)

    def test_duplicate_qualified_names_require_an_exact_id(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            write_sources(root, DUPLICATE_QUALIFIED_NAMES)
            plain = run_cli("query", str(root), "--intent", "find-callers", "--qualified-name", "js/dup.js::handler")
            machine = run_cli(
                "query",
                str(root),
                "--intent",
                "find-callers",
                "--qualified-name",
                "js/dup.js::handler",
                "--json",
            )
        self.assertEqual(plain[0], EXIT_AMBIGUOUS)
        payload = json.loads(machine[1])
        self.assertIsNone(payload["selected_entity"])
        self.assertEqual(len(payload["candidate_entities"]), 2)
        self.assertIn("ambiguous selection:", plain[2])


class ServeCommandTests(CliTestCase):
    def test_serve_refuses_a_non_loopback_bind(self) -> None:
        for host in ("0.0.0.0", "192.168.1.10", "example.com"):
            with self.subTest(host=host):
                status, out, err = run_cli("serve", self.root_text(), "--host", host, "--port", "0")
                self.assertEqual(status, EXIT_USAGE)
                self.assertEqual(out, "")
                self.assertIn("loopback-only", err)

    def test_serve_refuses_an_invalid_port(self) -> None:
        status, out, _ = run_cli("serve", self.root_text(), "--port", "70000")
        self.assertEqual(status, EXIT_ANALYSIS_FAILURE)
        self.assertEqual(out, "")

    def test_serve_reports_an_analysis_failure_for_a_missing_root(self) -> None:
        status, out, err = run_cli("serve", str(self.root / "absent"), "--port", "0")
        self.assertEqual(status, EXIT_ANALYSIS_FAILURE)
        self.assertEqual(out, "")
        self.assertIn("error:", err)

    def test_serve_binds_and_serves_then_shuts_down(self) -> None:
        import threading
        from unittest import mock

        import arctrellis.api as api_module

        captured: dict[str, object] = {}
        real_create = api_module.create_server

        def capture(root, **kwargs):
            server = real_create(root, **kwargs)
            captured["server"] = server
            return server

        out, err = io.StringIO(), io.StringIO()
        result: dict[str, int] = {}

        def serve() -> None:
            result["status"] = main(["serve", self.root_text(), "--port", "0"], stdout=out, stderr=err)

        with mock.patch.object(api_module, "create_server", capture):
            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            server = _await_server(captured)
            host, port = server.server_address[0], server.server_address[1]
            connection = http.client.HTTPConnection(host, port, timeout=30)
            try:
                connection.request("GET", "/api/v1/health")
                response = connection.getresponse()
                status, body = response.status, response.read()
            finally:
                connection.close()
            server.shutdown()
            thread.join(timeout=30)

        self.assertFalse(thread.is_alive())
        self.assertEqual(result["status"], EXIT_SUCCESS)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "ok")
        self.assertIn("loopback only", out.getvalue())
        self.assertIn("press Ctrl+C", err.getvalue())
        self.assertIn("stopped", err.getvalue())
        self.assertNotIn(str(self.root), out.getvalue() + err.getvalue())


def _await_server(captured: dict[str, object], timeout: float = 60.0):
    """Wait until the serve command has constructed and bound its listener."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        server = captured.get("server")
        if server is not None:
            return server
        time.sleep(0.01)
    raise AssertionError("the serve command did not bind a listener")


class HelpTests(unittest.TestCase):
    def test_top_level_help_lists_every_subcommand(self) -> None:
        out = io.StringIO()
        with self.assertRaises(SystemExit) as raised:
            main(["--help"], stdout=out, stderr=io.StringIO())
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("analyze", out.getvalue())
        for command in ("search", "query", "endpoints", "database", "trace", "impact", "tests"):
            self.assertIn(command, out.getvalue())
        self.assertIn("exit codes:", out.getvalue())

    def test_every_subcommand_has_help(self) -> None:
        for command in ("analyze", "search", "query", "endpoints", "database", "trace", "impact", "tests"):
            with self.subTest(command=command):
                out = io.StringIO()
                with self.assertRaises(SystemExit) as raised:
                    main([command, "--help"], stdout=out, stderr=io.StringIO())
                self.assertEqual(raised.exception.code, 0)
                self.assertIn("usage:", out.getvalue())

    def test_missing_command_exits_two(self) -> None:
        err = io.StringIO()
        with self.assertRaises(SystemExit) as raised:
            main([], stdout=io.StringIO(), stderr=err)
        self.assertEqual(raised.exception.code, EXIT_USAGE)

    def test_unknown_subcommand_exits_two(self) -> None:
        err = io.StringIO()
        with self.assertRaises(SystemExit) as raised:
            main(["explain"], stdout=io.StringIO(), stderr=err)
        self.assertEqual(raised.exception.code, EXIT_USAGE)


if __name__ == "__main__":
    unittest.main()
