import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from arctrellis.core import EntityKind as EK
from arctrellis.core import RelationshipKind as RK
from arctrellis.query import (
    AnalysisCompleteness,
    AnalysisSummary,
    InvalidQuerySourceError,
    QueryStatus,
    TraversalDirection,
    UnknownQueryEntityError,
    find_callers,
    find_direct_tests_for_symbol,
    find_potentially_affected_endpoints,
    get_direct_database_operations,
    list_direct_database_callers,
    list_endpoints,
)
from tests.query.test_paths import edge, entity, graph_fixture


class ArchitectureQueryTests(unittest.TestCase):
    def test_real_python_script_tests_direct_database_and_impact(self):
        from tests.database.test_graph import PYTHON, TYPESCRIPT, pipeline

        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(PYTHON, encoding="utf-8")
            (root / "app.js").write_text(
                TYPESCRIPT + '\ntest("persist", () => { persistPayment(); });', encoding="utf-8"
            )
            index, _, result = pipeline(root)
        graph = result.graph
        summary = AnalysisSummary(index.complete_file_count, index.partial_file_count, index.failed_file_count)
        self.assertEqual(summary.completeness, AnalysisCompleteness.COMPLETE)
        for name in ("create_payment", "persistPayment"):
            symbol = next(e for e in graph.entities() if e.kind is EK.FUNCTION and e.name == name)
            tests = find_direct_tests_for_symbol(graph, symbol.id)
            self.assertEqual(len(tests.paths), 1)
            self.assertEqual(tests.paths[0].relationships[0].kind, RK.TESTS)
        helper = next(e for e in graph.entities() if e.kind is EK.FUNCTION and e.name == "persist_payment")
        self.assertEqual(len(get_direct_database_operations(graph, helper.id).paths), 2)
        self.assertEqual(find_direct_tests_for_symbol(graph, helper.id).paths, ())
        impact = find_potentially_affected_endpoints(graph, helper.id)
        self.assertEqual([p.entities[0].name for p in impact.paths], ["POST /payments"])
        self.assertEqual(tuple(e.kind for e in impact.paths[0].relationships), (RK.EXPOSES, RK.CALLS))
        self.assertEqual(len(list_endpoints(graph, scope="declared").entities), 4)

    def test_database_direct_versus_transitive_and_inventory(self):
        graph = graph_fixture()
        result = get_direct_database_operations(graph, "handler")
        self.assertEqual([p.entity_ids for p in result.paths], [("handler", "read")])
        self.assertEqual(
            {p.entity_ids[-1] for p in get_direct_database_operations(graph, "service").paths}, {"write", "delete"}
        )
        result = list_direct_database_callers(graph)
        self.assertEqual({p.entity_ids[0] for p in result.paths}, {"handler", "service"})
        self.assertEqual(len(result.paths), 3)
        graph.add_entity(entity("importer"))
        graph.add_relationship(edge("import", "importer", "service", RK.IMPORTS))
        self.assertEqual(get_direct_database_operations(graph, "importer").paths, ())
        self.assertNotIn("importer", {p.entity_ids[0] for p in list_direct_database_callers(graph).paths})
        json.dumps(result.to_dict())

    def test_direct_tests_duplicate_evidence_and_no_transitive_claims(self):
        graph = graph_fixture()
        graph.add_entity(entity("test", EK.TEST))
        graph.add_entity(entity("other_test", EK.TEST))
        for identifier, test in [("test1", "test"), ("test2", "test"), ("test3", "other_test")]:
            graph.add_relationship(edge(identifier, test, "handler", RK.TESTS))
        result = find_direct_tests_for_symbol(graph, "handler")
        self.assertEqual([p.relationship_ids for p in result.paths], [("test1",), ("test2",), ("test3",)])
        self.assertEqual(result.direction, TraversalDirection.REVERSE)
        self.assertEqual(find_direct_tests_for_symbol(graph, "service").status, QueryStatus.NO_KNOWN_PATH)
        with self.assertRaises(UnknownQueryEntityError):
            find_direct_tests_for_symbol(graph, "missing")
        with self.assertRaises(InvalidQuerySourceError):
            find_direct_tests_for_symbol(graph, "endpoint")

    def test_direct_and_transitive_callers_only_calls_and_cycles(self):
        graph = graph_fixture()
        graph.add_entity(entity("outer"))
        graph.add_relationship(edge("outer_call", "outer", "handler"))
        for kind in (RK.IMPORTS, RK.DEFINES, RK.TESTS, RK.APPLIES_MIDDLEWARE):
            graph.add_entity(entity(kind.value))
            graph.add_relationship(edge(kind.value, kind.value, "service", kind))
        direct = find_callers(graph, "service")
        self.assertEqual([p.relationship_ids for p in direct.paths], [("b",), ("c",)])
        transitive = find_callers(graph, "service", transitive=True)
        self.assertEqual(
            [p.relationship_ids for p in transitive.paths], [("b",), ("c",), ("outer_call", "b"), ("outer_call", "c")]
        )
        self.assertEqual(transitive.direction, TraversalDirection.REVERSE)
        self.assertEqual(find_callers(graph, "outer").paths, ())

    def test_impact_direct_handler_multiple_endpoints_and_original_direction(self):
        graph = graph_fixture()
        graph.add_entity(entity("duplicate", EK.API_ENDPOINT))
        graph.add_relationship(edge("duplicate_exposes", "duplicate", "handler", RK.EXPOSES))
        result = find_potentially_affected_endpoints(graph, "service")
        self.assertEqual({p.entity_ids[0] for p in result.paths}, {"endpoint", "duplicate"})
        self.assertEqual(len(result.paths), 4)
        for path in result.paths:
            self.assertEqual(path.entity_ids[-1], "service")
            self.assertEqual(tuple(e.kind for e in path.relationships), (RK.EXPOSES, RK.CALLS))
            self.assertEqual(path.weakest_edge_score, min(e.confidence_score for e in path.relationships))
        direct = find_potentially_affected_endpoints(graph, "handler")
        self.assertEqual({p.entity_ids[0] for p in direct.paths}, {"endpoint", "duplicate"})
        self.assertTrue(all(p.hop_count == 1 for p in direct.paths))
        self.assertTrue(find_potentially_affected_endpoints(graph, "service", max_depth=1).truncated)

    def test_no_import_defines_test_or_middleware_impact(self):
        graph = graph_fixture()
        graph.add_entity(entity("changed"))
        for kind in (RK.IMPORTS, RK.DEFINES, RK.TESTS, RK.APPLIES_MIDDLEWARE):
            graph.add_relationship(edge("false-" + kind.value, "endpoint", "changed", kind))
        self.assertEqual(find_potentially_affected_endpoints(graph, "changed").status, QueryStatus.NO_KNOWN_PATH)

    def test_endpoint_metadata_filters_keep_registration_identities(self):
        graph = graph_fixture()
        for identifier, scope in [("local1", "local"), ("local2", "local"), ("effective", "effective")]:
            graph.add_entity(
                entity(
                    identifier,
                    EK.API_ENDPOINT,
                    (
                        ("http_method", "POST"),
                        ("route_path", "/x"),
                        ("framework", "express"),
                        ("path_completeness", scope),
                    ),
                )
            )
        result = list_endpoints(graph, http_method="POST", route_path="/x", framework="express", scope="local")
        self.assertEqual([e.id for e in result.entities], ["local1", "local2"])
        self.assertEqual([e.id for e in list_endpoints(graph, scope="effective").entities], ["effective"])
        self.assertEqual(list_endpoints(graph, framework="fastapi").entities, ())
        self.assertEqual(len(list_endpoints(graph).entities), 4)
        self.assertTrue(list_endpoints(graph, max_results=1).truncated)
        json.dumps(result.to_dict())

    def test_completeness_and_determinism(self):
        for counts, state in [
            ((3, 0, 0), AnalysisCompleteness.COMPLETE),
            ((2, 1, 0), AnalysisCompleteness.PARTIAL),
            ((2, 0, 1), AnalysisCompleteness.PARTIAL),
            ((0, 0, 2), AnalysisCompleteness.FAILED),
        ]:
            summary = AnalysisSummary(*counts)
            self.assertEqual(summary.completeness, state)
            result = find_callers(graph_fixture(), "service", analysis_completeness=summary.completeness)
            self.assertEqual(result.analysis_completeness, state)
        for counts in ((True, 0, 0), (-1, 0, 0), (1.2, 0, 0)):
            with self.assertRaises(ValueError):
                AnalysisSummary(*counts)
        for query, source in [
            (get_direct_database_operations, "handler"),
            (find_direct_tests_for_symbol, "service"),
            (find_callers, "service"),
            (find_potentially_affected_endpoints, "service"),
        ]:
            a, b = graph_fixture(), graph_fixture(True)
            before = (a.entities(), a.relationships())
            self.assertEqual(query(a, source).to_dict(), query(b, source).to_dict())
            self.assertEqual(before, (a.entities(), a.relationships()))
