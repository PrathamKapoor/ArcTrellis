import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from arctrellis.core import Confidence
from arctrellis.core import EntityKind as EK
from arctrellis.core import RelationshipKind as RK
from arctrellis.query import (
    AnalysisCompleteness,
    AnalysisSummary,
    InvalidQuerySourceError,
    QueryStatus,
    UnknownQueryEntityError,
    find_direct_tests_for_symbol,
    find_potentially_affected_endpoints,
    list_endpoints,
    trace_callable_to_database,
    trace_endpoint_to_database,
)
from tests.query.fixtures import JAVASCRIPT, MIXED, PYTHON, TYPESCRIPT, pipeline, write_repository


class GoldenTests(unittest.TestCase):
    def analyze(self, sources):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        write_repository(root, sources)
        return root, pipeline(root)

    def test_independent_positive_chains_proof_locations_and_confidence(self):
        cases = (
            (
                PYTHON,
                "POST /payments",
                "app.py",
                ("create_payment", "persist_payment"),
                "write",
                (
                    ("app.py", 4, "fastapi_decorated_handler"),
                    ("app.py", 6, "python_imported_symbol_call_resolution"),
                    ("payments.py", 5, "sqlalchemy_execute_insert"),
                ),
            ),
            (
                PYTHON,
                "GET /payments",
                "app.py",
                ("get_payment", "read_payment"),
                "read",
                (
                    ("app.py", 7, "fastapi_decorated_handler"),
                    ("app.py", 9, "python_imported_symbol_call_resolution"),
                    ("payments.py", 8, "sqlalchemy_session_get"),
                ),
            ),
            (
                JAVASCRIPT,
                "POST /orders",
                "js/app.js",
                ("createOrder", "persistOrder"),
                "write",
                (
                    ("js/app.js", 10, "express_local_handler_resolution"),
                    ("js/app.js", 7, "ecmascript_imported_symbol_call_resolution"),
                    ("js/service.js", 4, "prisma_model_create"),
                ),
            ),
            (
                TYPESCRIPT,
                "POST /orders",
                "ts/app.ts",
                ("createOrder", "persistOrder"),
                "write",
                (
                    ("ts/app.ts", 5, "express_local_handler_resolution"),
                    ("ts/app.ts", 4, "ecmascript_imported_symbol_call_resolution"),
                    ("ts/service.ts", 4, "prisma_model_create"),
                ),
            ),
        )
        for sources, name, file_path, chain, category, expected_proofs in cases:
            with self.subTest(name=name):
                _, (index, _, _, database) = self.analyze(sources)
                self.assertTrue(index.is_complete)
                graph = database.graph
                endpoints = sorted(
                    (
                        e
                        for e in graph.entities()
                        if e.kind is EK.API_ENDPOINT and e.name == name and e.location.file_path == file_path
                    ),
                    key=lambda e: e.location.start_line,
                )
                self.assertTrue(endpoints)
                result = trace_endpoint_to_database(graph, endpoints[0].id)
                self.assertEqual(result.status, QueryStatus.FOUND)
                self.assertEqual(len(result.paths), 1)
                path = result.paths[0]
                self.assertEqual(tuple(e.name for e in path.entities[1:-1]), chain)
                self.assertEqual(
                    tuple(e.kind for e in path.relationships),
                    (RK.EXPOSES, RK.CALLS, RK.WRITES_DATABASE if category == "write" else RK.READS_DATABASE),
                )
                self.assertEqual(dict(path.entities[-1].metadata)["operation_kind"], category)
                self.assertEqual(path.weakest_edge_score, 0.75)
                self.assertEqual(path.confidence_classification, Confidence.LIKELY)
                self.assertEqual(
                    tuple(
                        (
                            e.evidence[0].location.file_path,
                            e.evidence[0].location.start_line,
                            e.evidence[0].analysis_method,
                        )
                        for e in path.relationships
                    ),
                    expected_proofs,
                )
                for edge in path.relationships:
                    self.assertIs(edge, graph.get_relationship(edge.id))
                    self.assertIn("start_byte", dict(edge.evidence[0].metadata))
                impact = find_potentially_affected_endpoints(graph, path.entities[-2].id)
                self.assertIn(endpoints[0].id, {p.entities[0].id for p in impact.paths})

    def test_js_direct_read_middleware_exclusion_and_unresolved_handler(self):
        _, (index, _, _, result) = self.analyze(JAVASCRIPT)
        self.assertTrue(index.is_complete)
        graph = result.graph
        endpoint = next(e for e in graph.entities() if e.kind is EK.API_ENDPOINT and e.name == "GET /orders")
        path = trace_endpoint_to_database(graph, endpoint.id).paths[0]
        self.assertEqual(tuple(e.kind for e in path.relationships), (RK.EXPOSES, RK.READS_DATABASE))
        for name in ("GET /empty", "GET /dynamic"):
            endpoint = next(e for e in graph.entities() if e.kind is EK.API_ENDPOINT and e.name == name)
            self.assertEqual(trace_endpoint_to_database(graph, endpoint.id).status, QueryStatus.NO_KNOWN_PATH)
        guard = next(e for e in graph.entities() if e.kind is EK.FUNCTION and e.name == "guard")
        self.assertTrue(trace_callable_to_database(graph, guard.id).paths)
        self.assertEqual(find_potentially_affected_endpoints(graph, guard.id).paths, ())
        fake = next(e for e in graph.entities() if e.kind is EK.FUNCTION and e.name == "fakeWrite")
        self.assertEqual(trace_callable_to_database(graph, fake.id).paths, ())

    def test_python_staged_commit_unresolved_ambiguous_fake_and_errors(self):
        _, (index, calls, _, result) = self.analyze(PYTHON)
        self.assertTrue(index.is_complete)
        self.assertGreater(calls.ambiguous_count, 0)
        graph = result.graph
        for name in ("POST /staged", "GET /unknown", "GET /ambiguous"):
            endpoint = next(e for e in graph.entities() if e.kind is EK.API_ENDPOINT and e.name == name)
            self.assertEqual(trace_endpoint_to_database(graph, endpoint.id).paths, ())
        self.assertFalse(any(e.name == "POST /fake" for e in graph.entities() if e.kind is EK.API_ENDPOINT))
        with self.assertRaises(UnknownQueryEntityError):
            trace_endpoint_to_database(graph, "missing")
        module = next(e for e in graph.entities() if e.kind is EK.MODULE)
        with self.assertRaises(InvalidQuerySourceError):
            trace_callable_to_database(graph, module.id)

    def test_direct_test_evidence_not_transitive_or_http_coverage(self):
        _, (_, _, _, result) = self.analyze(MIXED)
        graph = result.graph
        for language, name, test_file, line in (
            ("python", "persist_payment", "test_payments.py", 3),
            ("javascript", "persistOrder", "js/service.test.js", 2),
            ("typescript", "persistOrder", "ts/service.test.ts", 2),
        ):
            helper = next(
                e for e in graph.entities() if e.kind is EK.FUNCTION and e.name == name and e.language == language
            )
            tests = find_direct_tests_for_symbol(graph, helper.id)
            self.assertEqual(len(tests.paths), 1)
            proof = tests.paths[0].relationships[0].evidence[0]
            self.assertEqual((proof.location.file_path, proof.location.start_line), (test_file, line))
            self.assertEqual(tests.paths[0].entities[0].kind, EK.TEST)
        handler = next(e for e in graph.entities() if e.kind is EK.FUNCTION and e.name == "create_payment")
        self.assertEqual(find_direct_tests_for_symbol(graph, handler.id).paths, ())

    def test_mixed_language_same_names_duplicates_effective_and_determinism(self):
        root, (index, _, _, result) = self.analyze(MIXED)
        graph = result.graph
        first = list_endpoints(graph)
        self.assertFalse(first.truncated)
        duplicates = tuple(
            e for e in list_endpoints(graph, route_path="/orders").entities if e.language == "typescript"
        )
        self.assertEqual(len(duplicates), 2)
        self.assertNotEqual(duplicates[0].id, duplicates[1].id)
        local = list_endpoints(graph, route_path="/local", scope="local").entities
        mounted = list_endpoints(graph, route_path="/api/local", scope="application").entities
        self.assertEqual(len(local), 1)
        self.assertEqual(len(mounted), 1)
        self.assertNotEqual(local[0].id, mounted[0].id)
        self.assertTrue(trace_endpoint_to_database(graph, mounted[0].id).paths)
        symbol = next(
            e for e in graph.entities() if e.kind is EK.FUNCTION and e.name == "persistOrder" and e.language == "python"
        )
        self.assertEqual(trace_callable_to_database(graph, symbol.id).paths, ())
        self.assertEqual(find_potentially_affected_endpoints(graph, symbol.id).paths, ())
        before = (graph.entities(), graph.relationships())
        again = pipeline(root)[3].graph
        for endpoint in first.entities:
            a, b = trace_endpoint_to_database(graph, endpoint.id), trace_endpoint_to_database(again, endpoint.id)
            self.assertEqual(a.to_dict(), b.to_dict())
            json.dumps(a.to_dict())
        self.assertEqual(before, (graph.entities(), graph.relationships()))
        self.assertEqual(
            AnalysisSummary(index.complete_file_count, index.partial_file_count, index.failed_file_count).completeness,
            AnalysisCompleteness.COMPLETE,
        )

    def test_partial_and_failed_context_never_become_complete(self):
        _, (index, _, _, result) = self.analyze(PYTHON | {"broken.py": "def broken(:"})
        self.assertEqual(index.partial_file_count, 1)
        summary = AnalysisSummary(index.complete_file_count, index.partial_file_count, index.failed_file_count)
        endpoint = next(e for e in result.graph.entities() if e.kind is EK.API_ENDPOINT and e.name == "POST /payments")
        known = trace_endpoint_to_database(result.graph, endpoint.id, analysis_completeness=summary.completeness)
        self.assertEqual(known.analysis_completeness, AnalysisCompleteness.PARTIAL)
        self.assertEqual(
            trace_endpoint_to_database(result.graph, endpoint.id).analysis_completeness, AnalysisCompleteness.UNKNOWN
        )
