import json
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from tempfile import TemporaryDirectory

from arctrellis.core import CodeEntity, Confidence, Evidence, Relationship, SourceLocation
from arctrellis.core import EntityKind as EK
from arctrellis.core import RelationshipKind as RK
from arctrellis.graph import CodeGraph
from arctrellis.query import (
    AnalysisCompleteness,
    EvidencePath,
    InvalidQueryLimitError,
    InvalidQuerySourceError,
    QueryGraphInvariantError,
    QueryStatus,
    UnknownQueryEntityError,
    find_paths,
    trace_callable_to_database,
    trace_endpoint_to_database,
)


def entity(identifier, kind=EK.FUNCTION, metadata=()):
    return CodeEntity(identifier, kind, identifier, identifier, metadata=metadata)


def edge(identifier, source, target, kind=RK.CALLS, score=0.85, confidence=Confidence.LIKELY, proof=True):
    return Relationship(
        identifier,
        source,
        kind,
        target,
        confidence,
        score,
        (Evidence("proof-" + identifier, SourceLocation("app.py", 3, 3), "static_call", (("start_byte", "20"),)),)
        if proof
        else (),
    )


def graph_fixture(reverse=False):
    nodes = [
        entity("endpoint", EK.API_ENDPOINT),
        entity("handler"),
        entity("service"),
        entity("read", EK.DATABASE_OPERATION, (("operation_kind", "read"), ("provider", "sqlalchemy"))),
        entity("write", EK.DATABASE_OPERATION, (("operation_kind", "write"), ("provider", "prisma"))),
        entity("delete", EK.DATABASE_OPERATION, (("operation_kind", "delete"), ("provider", "prisma"))),
    ]
    edges = [
        edge("a", "endpoint", "handler", RK.EXPOSES, 1.0, Confidence.PROVEN),
        edge("b", "handler", "service", score=0.75),
        edge("c", "handler", "service"),
        edge("d", "service", "write", RK.WRITES_DATABASE),
        edge("e", "handler", "read", RK.READS_DATABASE),
        edge("f", "service", "handler"),
        edge("g", "service", "delete", RK.WRITES_DATABASE),
    ]
    graph = CodeGraph()
    for node in reversed(nodes) if reverse else nodes:
        graph.add_entity(node)
    for record in reversed(edges) if reverse else edges:
        graph.add_relationship(record)
    return graph


class PathTests(unittest.TestCase):
    def test_real_fastapi_express_read_write_delete_and_unlinked_observations(self):
        from tests.database.test_graph import PYTHON, TYPESCRIPT, pipeline

        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(PYTHON, encoding="utf-8")
            (root / "app.ts").write_text(TYPESCRIPT, encoding="utf-8")
            index, _, result = pipeline(root)
        self.assertTrue(index.is_complete)
        graph = result.graph
        for language, method, operation, kinds in (
            ("python", "POST", "write", (RK.EXPOSES, RK.CALLS, RK.WRITES_DATABASE)),
            ("python", "GET", "read", (RK.EXPOSES, RK.READS_DATABASE)),
            ("typescript", "POST", "write", (RK.EXPOSES, RK.CALLS, RK.WRITES_DATABASE)),
            ("typescript", "GET", "read", (RK.EXPOSES, RK.READS_DATABASE)),
        ):
            endpoint = next(
                e
                for e in graph.entities()
                if e.kind is EK.API_ENDPOINT and e.language == language and e.name.startswith(method)
            )
            paths = trace_endpoint_to_database(graph, endpoint.id, operation_kinds=frozenset((operation,))).paths
            self.assertEqual(len(paths), 1)
            self.assertEqual(tuple(e.kind for e in paths[0].relationships), kinds)
            self.assertEqual(paths[0].weakest_edge_score, 0.85)
            for record in paths[0].relationships:
                self.assertTrue(record.evidence)
                self.assertEqual(record.evidence, graph.get_relationship(record.id).evidence)
        endpoint = next(
            e
            for e in graph.entities()
            if e.kind is EK.API_ENDPOINT and e.language == "python" and e.name.startswith("POST")
        )
        self.assertEqual(
            {
                dict(p.entities[-1].metadata)["operation_kind"]
                for p in trace_endpoint_to_database(graph, endpoint.id).paths
            },
            {"write", "delete"},
        )

    def test_pattern_parallel_cycle_confidence_and_evidence(self):
        graph = graph_fixture()
        before = (graph.entities(), graph.relationships())
        result = trace_endpoint_to_database(graph, "endpoint")
        self.assertEqual(result.status, QueryStatus.FOUND)
        self.assertEqual(
            [p.relationship_ids for p in result.paths],
            [("a", "e"), ("a", "b", "d"), ("a", "b", "g"), ("a", "c", "d"), ("a", "c", "g")],
        )
        self.assertEqual(result.paths[1].weakest_edge_score, 0.75)
        self.assertEqual(result.paths[1].confidence_classification, Confidence.LIKELY)
        self.assertEqual(len({p.path_id for p in result.paths}), 5)
        for path in result.paths:
            for record in path.relationships:
                self.assertIs(record, graph.get_relationship(record.id))
                self.assertIs(record.evidence[0], graph.get_relationship(record.id).evidence[0])
        self.assertEqual(before, (graph.entities(), graph.relationships()))
        self.assertEqual(result.to_dict(), trace_endpoint_to_database(graph_fixture(True), "endpoint").to_dict())
        json.dumps(result.to_dict())
        self.assertEqual(result.analysis_completeness, AnalysisCompleteness.UNKNOWN)
        self.assertFalse(result.truncated)
        with self.assertRaises(FrozenInstanceError):
            result.paths = ()

    def test_filters_and_direct_callable(self):
        graph = graph_fixture()
        for operation, terminal in [("read", "read"), ("write", "write"), ("delete", "delete")]:
            result = trace_callable_to_database(graph, "handler", operation_kinds=frozenset((operation,)))
            self.assertTrue(result.paths)
            self.assertEqual({p.entity_ids[-1] for p in result.paths}, {terminal})
        self.assertEqual(trace_callable_to_database(graph, "service").paths[0].hop_count, 1)
        self.assertEqual(trace_endpoint_to_database(graph, "endpoint", operation_kinds=frozenset()).paths, ())

    def test_forbidden_edges_and_missing_exposes(self):
        for kind in (RK.IMPORTS, RK.DEFINES, RK.TESTS, RK.APPLIES_MIDDLEWARE):
            graph = graph_fixture()
            graph.add_entity(entity("isolated", EK.API_ENDPOINT))
            graph.add_relationship(edge("forbidden", "isolated", "service", kind))
            self.assertEqual(trace_endpoint_to_database(graph, "isolated").status, QueryStatus.NO_KNOWN_PATH)
        graph = graph_fixture()
        graph.add_entity(entity("unresolved"))
        self.assertEqual(trace_callable_to_database(graph, "unresolved").paths, ())

    def test_invalid_sources_limits_and_terminal(self):
        graph = graph_fixture()
        with self.assertRaises(UnknownQueryEntityError):
            trace_endpoint_to_database(graph, "missing")
        with self.assertRaises(InvalidQuerySourceError):
            trace_endpoint_to_database(graph, "handler")
        with self.assertRaises(InvalidQuerySourceError):
            trace_callable_to_database(graph, "endpoint")
        for name in ("max_depth", "max_paths", "max_expansions"):
            for value in (True, False, 0, -1, 1.2, float("inf"), None):
                with self.subTest(name=name, value=value), self.assertRaises(InvalidQueryLimitError):
                    trace_endpoint_to_database(graph, "endpoint", **{name: value})
        graph.add_relationship(edge("bad", "handler", "service", RK.WRITES_DATABASE))
        with self.assertRaises(QueryGraphInvariantError):
            trace_endpoint_to_database(graph, "endpoint")

    def test_depth_path_expansion_limits_and_exact_cap(self):
        graph = graph_fixture()
        for kwargs, reason in [
            ({"max_depth": 2}, "max_depth"),
            ({"max_paths": 1}, "max_paths"),
            ({"max_expansions": 1}, "max_expansions"),
        ]:
            result = trace_endpoint_to_database(graph, "endpoint", **kwargs)
            self.assertTrue(result.truncated)
            self.assertIn(reason, result.truncation_reasons)
            self.assertLessEqual(result.expansions, result.max_expansions)
            self.assertTrue(all(p.hop_count <= result.max_depth for p in result.paths))
        result = trace_callable_to_database(graph, "service", operation_kinds=frozenset(("write",)), max_paths=1)
        self.assertFalse(result.truncated)
        self.assertEqual(len(result.paths), 1)

    def test_general_direction_filter_and_validated_paths(self):
        graph = graph_fixture()
        result = find_paths(graph, "handler", "write", relationship_kinds=frozenset((RK.CALLS, RK.WRITES_DATABASE)))
        self.assertEqual([p.relationship_ids for p in result.paths], [("b", "d"), ("c", "d")])
        path = result.paths[0]
        with self.assertRaises(QueryGraphInvariantError):
            EvidencePath.from_graph(graph, (graph.get_entity("handler"), graph.get_entity("write")), path.relationships)
        with self.assertRaises(QueryGraphInvariantError):
            EvidencePath.from_graph(
                graph, path.entities, (replace(path.relationships[0], id="absent"),) + path.relationships[1:]
            )
        graph.add_relationship(edge("no-proof", "handler", "write", RK.CALLS, score=None, proof=False))
        path = find_paths(graph, "handler", "write", relationship_kinds=frozenset((RK.CALLS,))).paths[0]
        self.assertIsNone(path.weakest_edge_score)
        self.assertEqual(path.relationships[0].evidence, ())
