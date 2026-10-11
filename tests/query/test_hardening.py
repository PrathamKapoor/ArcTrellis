import ast
import json
import subprocess
import sys
import unittest
from dataclasses import fields, is_dataclass, replace
from pathlib import Path
from unittest.mock import patch

from arctrellis.core import Confidence
from arctrellis.core import EntityKind as EK
from arctrellis.core import RelationshipKind as RK
from arctrellis.graph import CodeGraph
from arctrellis.query import (
    AnalysisCompleteness,
    EntityQueryResult,
    EvidencePath,
    PathQueryResult,
    QueryGraphInvariantError,
    TraversalDirection,
    find_callers,
    find_direct_tests_for_symbol,
    find_paths,
    find_potentially_affected_endpoints,
    get_direct_database_operations,
    list_direct_database_callers,
    list_endpoints,
    trace_callable_to_database,
    trace_endpoint_to_database,
)
from tests.query.test_paths import edge, entity, graph_fixture


class MissingTargetGraph(CodeGraph):
    def relationships(self):
        return (edge("dangling", "owner", "missing", RK.WRITES_DATABASE),)


class HardeningTests(unittest.TestCase):
    def test_multihop_paths_and_fully_failed_analysis_context(self):
        from arctrellis.query import AnalysisSummary

        graph = graph_fixture()
        graph.add_entity(entity("middle"))
        graph.add_relationship(edge("middle1", "handler", "middle"))
        graph.add_relationship(edge("middle2", "middle", "service"))
        trace = trace_endpoint_to_database(graph, "endpoint")
        self.assertIn(("a", "middle1", "middle2", "d"), [p.relationship_ids for p in trace.paths])
        reverse = find_potentially_affected_endpoints(graph, "service")
        self.assertIn(("a", "middle1", "middle2"), [p.relationship_ids for p in reverse.paths])
        failed = AnalysisSummary(0, 0, 3)
        empty = list_endpoints(CodeGraph(), analysis_completeness=failed.completeness)
        self.assertEqual(empty.analysis_completeness, AnalysisCompleteness.FAILED)
        self.assertEqual(empty.entities, ())

    def test_corrupt_inventory_is_invariant_failure_not_unknown_input(self):
        graph = MissingTargetGraph()
        graph.add_entity(entity("owner"))
        with self.assertRaises(QueryGraphInvariantError):
            list_direct_database_callers(graph)

    def test_corrupt_impact_exposes_and_direct_test_source_rejected(self):
        graph = graph_fixture()
        graph.add_entity(entity("bad_source"))
        graph.add_relationship(edge("bad-exposes", "bad_source", "service", RK.EXPOSES))
        with self.assertRaises(QueryGraphInvariantError):
            find_potentially_affected_endpoints(graph, "service")
        graph.add_relationship(edge("bad-tests", "bad_source", "service", RK.TESTS))
        with self.assertRaises(QueryGraphInvariantError):
            find_direct_tests_for_symbol(graph, "service")

    def test_relevant_database_metadata_corruption_rejected(self):
        for metadata in (
            (),
            (("operation_kind", "write"), ("effect_stage", "staged_mutation")),
            (("operation_kind", "read"),),
            (("operation_kind", "transaction"),),
        ):
            graph = CodeGraph()
            graph.add_entity(entity("owner"))
            graph.add_entity(entity("db", EK.DATABASE_OPERATION, metadata))
            graph.add_relationship(edge("dbedge", "owner", "db", RK.WRITES_DATABASE))
            with self.subTest(metadata=metadata), self.assertRaises(QueryGraphInvariantError):
                trace_callable_to_database(graph, "owner")

    def test_json_has_only_primitives_and_preserves_missing_evidence_and_scores(self):
        graph = graph_fixture()
        graph.add_entity(entity("source"))
        graph.add_relationship(
            edge("no-proof", "source", "handler", score=None, confidence=Confidence.POSSIBLE, proof=False)
        )
        path = find_paths(graph, "source", "service", relationship_kinds=frozenset((RK.CALLS,))).paths[0]
        self.assertEqual(path.confidence_classification, Confidence.POSSIBLE)
        self.assertIsNone(path.weakest_edge_score)
        payload = path.to_dict()
        self.assertEqual(payload["relationships"][0]["evidence"], [])
        self.assertEqual(payload["relationships"][0]["score"], None)
        self.assertEqual(json.loads(json.dumps(payload)), payload)
        for value in self.walk(payload):
            self.assertIn(type(value), (dict, list, str, int, float, bool, type(None)))

    @staticmethod
    def walk(value):
        pending = [value]
        while pending:
            current = pending.pop()
            yield current
            if isinstance(current, dict):
                pending.extend(current.values())
            elif isinstance(current, (tuple, list)):
                pending.extend(current)
            elif is_dataclass(current):
                pending.extend(getattr(current, f.name) for f in fields(current))

    def test_query_execution_has_no_filesystem_analysis_execution_or_graph_mutation(self):
        graph = graph_fixture()
        before = (graph.entities(), graph.relationships())
        with (
            patch("builtins.open", side_effect=AssertionError("filesystem")),
            patch("os.open", side_effect=AssertionError("filesystem")),
            patch.object(CodeGraph, "add_entity", side_effect=AssertionError("mutation")),
            patch.object(CodeGraph, "add_relationship", side_effect=AssertionError("mutation")),
        ):
            results = [
                trace_endpoint_to_database(graph, "endpoint"),
                trace_callable_to_database(graph, "handler"),
                get_direct_database_operations(graph, "handler"),
                list_direct_database_callers(graph),
                find_direct_tests_for_symbol(graph, "service"),
                find_callers(graph, "service", transitive=True),
                find_potentially_affected_endpoints(graph, "service"),
                list_endpoints(graph),
                find_paths(
                    graph,
                    "service",
                    "endpoint",
                    direction=TraversalDirection.REVERSE,
                    relationship_kinds=frozenset((RK.CALLS, RK.EXPOSES)),
                ),
            ]
        self.assertEqual(before, (graph.entities(), graph.relationships()))
        from arctrellis.parsing import ParsedSource, SyntaxNode

        for result in results:
            for value in self.walk(result):
                self.assertNotIsInstance(value, (bytes, bytearray, CodeGraph, ParsedSource, SyntaxNode))

    def test_fresh_public_imports_do_not_load_analysis_or_runtime_dependencies(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import arctrellis.query as q; "
                "assert all(callable(getattr(q, name)) for name in q.__all__); "
                'assert not any(name.startswith(("arctrellis.parsing", "arctrellis.indexing", '
                '"tree_sitter", "sqlalchemy", "prisma", "fastapi")) for name in sys.modules)',
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_query_import_boundary(self):
        root = Path(__file__).resolve().parents[2] / "src/arctrellis/query"
        for path in root.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    modules = [node.module]
                for name in modules:
                    if name.startswith("arctrellis."):
                        self.assertIn(name.split(".")[1], ("core", "graph", "query"))

    def test_models_reject_invalid_order_direction_count_and_membership(self):
        graph = graph_fixture()
        result = trace_endpoint_to_database(graph, "endpoint")
        for changes in (
            {"paths": result.paths[::-1]},
            {"max_paths": 1},
            {"expansions": -1},
            {"analysis_completeness": "complete"},
            {"source_entity_id": "wrong"},
            {"truncation_reasons": ("invented",)},
            {"paths": result.paths + result.paths},
        ):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(result, **changes)
        with self.assertRaises(QueryGraphInvariantError):
            EvidencePath((entity("a"), entity("a")), (edge("self", "a", "a"),))
        with self.assertRaises(ValueError):
            EntityQueryResult("endpoints", (entity("z"), entity("a")), 10, 100, 2)
        self.assertIsInstance(result, PathQueryResult)
        self.assertEqual(result.analysis_completeness, AnalysisCompleteness.UNKNOWN)

    def test_functional_stress_budgets_at_three_graph_sizes(self):
        for size in (20, 200, 2000):
            with self.subTest(size=size):
                graph = CodeGraph()
                graph.add_entity(entity("endpoint", EK.API_ENDPOINT))
                graph.add_entity(entity("handler"))
                graph.add_relationship(edge("exposes", "endpoint", "handler", RK.EXPOSES))
                for i in range(size):
                    name = f"service-{i:04d}"
                    graph.add_entity(entity(name))
                    graph.add_entity(entity("db-" + name, EK.DATABASE_OPERATION, (("operation_kind", "write"),)))
                    graph.add_relationship(edge("call-" + name, "handler", name))
                    graph.add_relationship(edge("parallel-" + name, "handler", name))
                    graph.add_relationship(edge("cycle-" + name, name, "handler"))
                    graph.add_relationship(edge("write-" + name, name, "db-" + name, RK.WRITES_DATABASE))
                a = trace_endpoint_to_database(graph, "endpoint", max_paths=7, max_expansions=100)
                b = trace_endpoint_to_database(graph, "endpoint", max_paths=7, max_expansions=100)
                self.assertEqual(a.to_dict(), b.to_dict())
                self.assertTrue(a.truncated)
                self.assertLessEqual(len(a.paths), 7)
                self.assertLessEqual(a.expansions, 100)
                shallow = trace_endpoint_to_database(graph, "endpoint", max_depth=2, max_expansions=100)
                self.assertEqual(shallow.paths, ())
                self.assertTrue(shallow.truncated)
                full = trace_endpoint_to_database(graph, "endpoint", max_paths=2 * size, max_expansions=20000)
                self.assertEqual(len(full.paths), 2 * size)
                self.assertFalse(full.truncated)
                self.assertTrue(all(p.hop_count == 3 for p in full.paths))
