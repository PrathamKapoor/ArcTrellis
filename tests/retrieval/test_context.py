"""Grounded one-hop graph context: real relationships only, bounded and explained."""

import unittest

from arctrellis.core import Confidence, EntityKind, RelationshipKind
from arctrellis.graph import CodeGraph
from arctrellis.retrieval import (
    CONTEXT_EDGE_WEIGHTS,
    CONTEXT_RELATIONSHIP_KINDS,
    GRAPH_CONTEXT_BOOST_CAP,
    ContextDirection,
    MatchBasis,
    build_search_index,
    search_endpoints,
    search_symbols,
)
from tests.retrieval.fixtures import edge, entity, payment_graph, proof, synthetic_graph


def context_of(result, entity_id):
    return next(hit for hit in result.hits if hit.entity_id == entity_id)


class GraphContextTests(unittest.TestCase):
    def setUp(self):
        self.index = build_search_index(payment_graph())

    def search(self, query, **options):
        return search_symbols(self.index, query, include_graph_context=True, **options)

    def test_endpoint_discovers_its_linked_handler(self):
        result = self.search("createPayment")
        endpoint = context_of(result, "endpoint:post-payments")
        self.assertEqual(endpoint.match_basis, MatchBasis.GRAPH_NEIGHBOR)
        self.assertEqual(endpoint.matched_terms, ())
        support = endpoint.context_support[0]
        self.assertEqual(support.relationship_kind, RelationshipKind.EXPOSES)
        self.assertEqual(support.relationship_id, "rel:exposes")
        self.assertEqual(support.neighbor_entity_id, "function:createPayment")
        self.assertEqual(support.direction, ContextDirection.OUTGOING)
        self.assertEqual(support.confidence, Confidence.PROVEN)
        self.assertEqual(support.confidence_score, 1.0)
        self.assertEqual(support.evidence[0].location.file_path, "app.py")
        self.assertEqual(support.evidence[0].analysis_method, "fastapi_decorated_handler")

    def test_handler_discovers_its_linked_endpoint(self):
        graph = payment_graph(
            extra_entities=(
                entity(
                    "endpoint:delete-payment",
                    EntityKind.API_ENDPOINT,
                    "DELETE /payments",
                    "app.py::endpoint:DELETE /payments",
                    path="app.py",
                    start=9,
                    end=10,
                    language="python",
                    metadata=(
                        ("framework", "fastapi"),
                        ("http_method", "DELETE"),
                        ("route_path", "/payments"),
                        ("path_completeness", "local"),
                    ),
                ),
            ),
            extra_edges=(
                edge(
                    "rel:exposes-delete",
                    "endpoint:delete-payment",
                    RelationshipKind.EXPOSES,
                    "function:deletePayment",
                    evidence=(proof("ev:exposes-delete", "app.py", 9, "fastapi_decorated_handler"),),
                ),
            ),
        )
        result = search_symbols(build_search_index(graph), "deletePayment", include_graph_context=True)
        endpoint = context_of(result, "endpoint:delete-payment")
        self.assertEqual(endpoint.match_basis, MatchBasis.LEXICAL_AND_GRAPH)
        support = endpoint.context_support[0]
        self.assertEqual(support.direction, ContextDirection.OUTGOING)
        self.assertEqual(support.neighbor_entity_id, "function:deletePayment")
        self.assertEqual(support.relationship_id, "rel:exposes-delete")

    def test_function_linked_to_a_database_operation_gets_grounded_context(self):
        graph = payment_graph(
            extra_edges=(
                edge(
                    "rel:writes",
                    "function:createPayment",
                    RelationshipKind.WRITES_DATABASE,
                    "db:insert",
                    evidence=(proof("ev:writes", "payments.py", 5, "sqlalchemy_execute_insert"),),
                ),
            )
        )
        index = build_search_index(graph)
        owner = context_of(search_symbols(index, "sqlalchemy", include_graph_context=True), "function:createPayment")
        support = next(
            item for item in owner.context_support if item.relationship_kind is RelationshipKind.WRITES_DATABASE
        )
        self.assertEqual(support.relationship_id, "rel:writes")
        self.assertEqual(support.direction, ContextDirection.OUTGOING)
        self.assertEqual(support.neighbor_entity_id, "db:insert")
        self.assertEqual(support.confidence_score, 0.85)
        self.assertLessEqual(support.contribution, CONTEXT_EDGE_WEIGHTS[RelationshipKind.WRITES_DATABASE])
        self.assertEqual(support.evidence[0].analysis_method, "sqlalchemy_execute_insert")

    def test_test_relationship_provides_grounded_static_context(self):
        result = self.search("createPayment")
        test_hit = context_of(result, "test:create-payment")
        support = next(item for item in test_hit.context_support if item.relationship_kind is RelationshipKind.TESTS)
        self.assertEqual(support.relationship_id, "rel:tests")
        self.assertEqual(support.evidence[0].analysis_method, "python_test_body_call")
        self.assertNotIn("runtime", " ".join(support.evidence[0].analysis_method))

    def test_middleware_stays_a_pre_handler_association(self):
        graph = payment_graph(
            extra_entities=(
                entity(
                    "function:auth",
                    EntityKind.FUNCTION,
                    "require_admin",
                    "app.py::require_admin",
                    path="app.py",
                    start=2,
                    language="python",
                ),
            ),
            extra_edges=(
                edge(
                    "rel:middleware",
                    "endpoint:post-payments",
                    RelationshipKind.APPLIES_MIDDLEWARE,
                    "function:auth",
                    confidence=Confidence.LIKELY,
                    score=0.85,
                    evidence=(proof("ev:middleware", "app.py", 4, "fastapi_decorator_dependency"),),
                ),
            ),
        )
        index = build_search_index(graph)
        result = search_symbols(index, "require_admin", include_graph_context=True)
        endpoint = context_of(result, "endpoint:post-payments")
        support = next(
            item for item in endpoint.context_support if item.relationship_kind is RelationshipKind.APPLIES_MIDDLEWARE
        )
        self.assertEqual(support.direction, ContextDirection.OUTGOING)
        self.assertEqual(support.contribution, CONTEXT_EDGE_WEIGHTS[RelationshipKind.APPLIES_MIDDLEWARE])
        self.assertNotEqual(support.relationship_kind, RelationshipKind.CALLS)
        self.assertLess(
            CONTEXT_EDGE_WEIGHTS[RelationshipKind.APPLIES_MIDDLEWARE],
            CONTEXT_EDGE_WEIGHTS[RelationshipKind.CALLS],
        )

    def test_imports_and_defines_never_become_invocation_context(self):
        graph = self.index.context
        stored = {edge.relationship_id for edges in graph.outgoing.values() for edge in edges}
        self.assertNotIn("rel:imports", stored)
        self.assertNotIn("rel:defines", stored)
        for kind in (
            RelationshipKind.IMPORTS,
            RelationshipKind.DEFINES,
            RelationshipKind.CONTAINS,
            RelationshipKind.INHERITS,
            RelationshipKind.USES,
        ):
            with self.subTest(kind=kind):
                self.assertNotIn(kind, CONTEXT_RELATIONSHIP_KINDS)
                self.assertNotIn(kind, CONTEXT_EDGE_WEIGHTS)
        hits = search_symbols(self.index, "persist_payment", include_graph_context=True, top_k=20).hits
        for hit in hits:
            for support in hit.context_support:
                self.assertIn(support.relationship_kind, CONTEXT_RELATIONSHIP_KINDS)

    def test_missing_edge_produces_no_context(self):
        graph = payment_graph(
            extra_entities=(
                entity(
                    "function:orphan",
                    EntityKind.FUNCTION,
                    "orphanHandler",
                    "orphan.py::orphanHandler",
                    path="orphan.py",
                    start=1,
                    language="python",
                ),
            )
        )
        result = search_symbols(build_search_index(graph), "orphanHandler", include_graph_context=True)
        self.assertEqual(result.hits[0].match_basis, MatchBasis.LEXICAL)
        self.assertEqual(result.hits[0].context_support, ())
        self.assertEqual(result.hits[0].graph_context_boost, 0.0)

    def test_parallel_relationships_preserve_separate_evidence(self):
        graph = payment_graph(
            extra_edges=(
                edge(
                    "rel:exposes-second",
                    "endpoint:post-payments",
                    RelationshipKind.EXPOSES,
                    "function:deletePayment",
                    evidence=(proof("ev:exposes-second", "app.py", 30, "fastapi_decorated_handler"),),
                ),
            )
        )
        result = search_symbols(build_search_index(graph), "createPayment", include_graph_context=True)
        supports = context_of(result, "endpoint:post-payments").context_support
        exposes = sorted(
            item.relationship_id for item in supports if item.relationship_kind is RelationshipKind.EXPOSES
        )
        self.assertEqual(exposes, ["rel:exposes", "rel:exposes-second"])
        locations = sorted(
            item.evidence[0].location.start_line
            for item in supports
            if item.relationship_kind is RelationshipKind.EXPOSES
        )
        self.assertEqual(locations, [4, 30])

    def test_many_neighbors_do_not_create_unbounded_boosts(self):
        def hub(degree):
            callers = tuple(
                entity(
                    f"function:caller{number:03d}",
                    EntityKind.FUNCTION,
                    f"createPaymentCaller{number:03d}",
                    f"hub.py::createPaymentCaller{number:03d}",
                    path="hub.py",
                    start=number + 1,
                    language="python",
                )
                for number in range(degree)
            )
            calls = tuple(
                edge(
                    f"rel:hub{number:03d}",
                    f"function:caller{number:03d}",
                    RelationshipKind.CALLS,
                    "function:createPayment",
                )
                for number in range(degree)
            )
            return build_search_index(payment_graph(extra_entities=callers, extra_edges=calls))

        small = search_symbols(hub(1), "createPayment", include_graph_context=True, top_k=50)
        large = search_symbols(hub(200), "createPayment", include_graph_context=True, top_k=50)
        single_boost = context_of(small, "function:caller000").graph_context_boost
        hub_boost = context_of(large, "function:caller000").graph_context_boost
        self.assertEqual(hub_boost, single_boost)
        self.assertEqual(hub_boost, CONTEXT_EDGE_WEIGHTS[RelationshipKind.CALLS])
        for hit in large.hits:
            with self.subTest(entity=hit.entity_id):
                self.assertLessEqual(hit.graph_context_boost, GRAPH_CONTEXT_BOOST_CAP)
        self.assertTrue(any(hit.has_graph_context for hit in large.hits))

    def test_context_never_reaches_two_hops(self):
        graph = payment_graph(
            extra_entities=(
                entity(
                    "function:audit",
                    EntityKind.FUNCTION,
                    "auditTrail",
                    "audit.py::auditTrail",
                    path="audit.py",
                    start=1,
                    language="python",
                ),
            ),
            extra_edges=(
                edge(
                    "rel:middleware",
                    "endpoint:post-payments",
                    RelationshipKind.APPLIES_MIDDLEWARE,
                    "function:deletePayment",
                    evidence=(proof("ev:middleware", "app.py", 4, "fastapi_decorator_dependency"),),
                ),
                edge(
                    "rel:two-hop",
                    "function:deletePayment",
                    RelationshipKind.CALLS,
                    "function:audit",
                    evidence=(proof("ev:two-hop", "payments.py", 25, "python_imported_symbol_call_resolution"),),
                ),
            ),
        )
        index = build_search_index(graph)
        result = search_symbols(index, "auditTrail", include_graph_context=True, top_k=50)
        self.assertEqual([hit.entity_id for hit in result.hits], ["function:audit", "function:deletePayment"])
        self.assertEqual(result.hits[0].context_support, ())
        self.assertEqual(result.hits[1].context_support[0].neighbor_entity_id, "function:audit")
        self.assertNotIn("endpoint:post-payments", result.entity_ids())

    def test_graph_context_search_is_deterministic(self):
        first = self.search("payment service")
        second = search_symbols(build_search_index(payment_graph()), "payment service", include_graph_context=True)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.entity_ids(), second.entity_ids())

    def test_graph_disabled_results_omit_every_graph_boost(self):
        result = search_symbols(self.index, "createPayment", include_graph_context=False)
        self.assertFalse(result.graph_context_used)
        for hit in result.hits:
            with self.subTest(entity=hit.entity_id):
                self.assertEqual(hit.graph_context_boost, 0.0)
                self.assertEqual(hit.context_support, ())
                self.assertIs(hit.match_basis, MatchBasis.LEXICAL)
        self.assertEqual(result.graph_candidate_count, 0)

    def test_graph_context_does_not_mutate_the_graph_or_reread_source(self):
        graph = payment_graph()
        before = (graph.entities(), graph.relationships())
        index = build_search_index(graph)
        with (
            __import__("unittest.mock", fromlist=["patch"]).patch(
                "builtins.open", side_effect=AssertionError("filesystem")
            ),
            __import__("unittest.mock", fromlist=["patch"]).patch("os.open", side_effect=AssertionError("filesystem")),
            __import__("unittest.mock", fromlist=["patch"]).patch.object(
                CodeGraph, "add_entity", side_effect=AssertionError("mutation")
            ),
            __import__("unittest.mock", fromlist=["patch"]).patch.object(
                CodeGraph, "add_relationship", side_effect=AssertionError("mutation")
            ),
        ):
            for _ in range(3):
                search_symbols(index, "createPayment", include_graph_context=True)
        self.assertEqual(before, (graph.entities(), graph.relationships()))

    def test_index_without_context_never_produces_graph_hits(self):
        index = build_search_index(payment_graph(), include_graph_context=False)
        self.assertIsNone(index.context)
        self.assertFalse(index.has_graph_context)
        result = search_symbols(index, "createPayment", include_graph_context=True)
        self.assertFalse(result.graph_context_used)
        self.assertEqual(result.graph_candidate_count, 0)

    def test_neighbors_are_read_from_one_projection_without_adjacency_snapshots(self):
        calls = []
        original = CodeGraph.outgoing

        def counting(self, entity_id, **kwargs):
            calls.append(entity_id)
            return original(self, entity_id, **kwargs)

        CodeGraph.outgoing = counting
        try:
            index = build_search_index(payment_graph())
            calls.clear()
            for _ in range(5):
                search_symbols(index, "createPayment", include_graph_context=True, top_k=10)
        finally:
            CodeGraph.outgoing = original
        self.assertEqual(calls, [])

    def test_corrupt_context_reference_is_an_invariant_failure(self):
        from arctrellis.retrieval.context import build_graph_context_index
        from arctrellis.retrieval.errors import RetrievalInvariantError

        graph = CodeGraph()
        graph.add_entity(entity("a", EntityKind.MODULE, "a", "a", path="a.py"))
        graph.add_entity(entity("b", EntityKind.MODULE, "b", "b", path="b.py"))
        graph.add_relationship(edge("r", "a", RelationshipKind.CALLS, "b"))
        with self.assertRaises(RetrievalInvariantError):
            build_graph_context_index(graph.relationships(), frozenset({"a"}))

    def test_neighbor_cap_is_reported_rather_than_hidden(self):
        edges = tuple(
            edge(f"rel:f{number:03d}", f"function:caller{number:03d}", RelationshipKind.CALLS, "function:createPayment")
            for number in range(10)
        )
        entities = tuple(
            entity(
                f"function:caller{number:03d}",
                EntityKind.FUNCTION,
                f"caller{number:03d}",
                f"hub.py::caller{number:03d}",
                path="hub.py",
                start=number + 1,
                language="python",
            )
            for number in range(10)
        )
        index = build_search_index(
            payment_graph(extra_entities=entities, extra_edges=edges),
            max_context_neighbors=4,
        )
        self.assertGreater(index.context_capped_list_count, 0)
        self.assertEqual(len(index.context.incoming["function:createPayment"]), 4)
        result = search_symbols(index, "createPayment", include_graph_context=True, top_k=20)
        supporters = [hit for hit in result.hits if hit.has_graph_context]
        self.assertLessEqual(len(supporters[0].context_support), index.context.max_neighbors_per_entity)

    def test_high_degree_synthetic_corpus_context_stays_bounded(self):
        index = build_search_index(synthetic_graph(300), max_context_neighbors=8)
        self.assertGreater(index.context_edge_count, 0)
        result = search_symbols(index, "paymentService00042", include_graph_context=True, top_k=25)
        self.assertEqual(result.hits[0].entity_id, "synthetic:function:00042")
        self.assertTrue(any(hit.has_graph_context for hit in result.hits))
        for hit in result.hits:
            self.assertLessEqual(hit.graph_context_boost, GRAPH_CONTEXT_BOOST_CAP)
            self.assertLessEqual(len(hit.context_support), 8)

    def test_endpoint_wrapper_can_use_graph_context(self):
        result = search_endpoints(self.index, "createPayment", include_graph_context=True, top_k=10)
        self.assertEqual([hit.entity_id for hit in result.hits], ["endpoint:post-payments"])
        self.assertTrue(result.hits[0].has_graph_context)
        self.assertEqual(result.filters.entity_kinds, frozenset({EntityKind.API_ENDPOINT}))
