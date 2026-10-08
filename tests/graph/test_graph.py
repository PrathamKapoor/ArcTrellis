"""Graph storage, adjacency, consistency and snapshot contracts."""

import unittest
from dataclasses import replace

from arctrellis.core import Confidence, RelationshipKind
from arctrellis.graph import (
    CodeGraph,
    DuplicateEntityError,
    DuplicateRelationshipError,
    GraphError,
    UnknownEntityError,
    UnknownRelationshipError,
)

from .fixtures import build_graph, entity, ids, payment_graph, relationship


class GraphStorageTests(unittest.TestCase):
    def test_empty_graph_has_empty_snapshots_and_zero_counts(self):
        graph = CodeGraph()
        self.assertEqual(graph.entities(), ())
        self.assertEqual(graph.relationships(), ())
        self.assertEqual((graph.entity_count, graph.relationship_count), (0, 0))
        self.assertFalse(graph.has_entity("missing"))
        self.assertFalse(graph.has_relationship("missing"))

    def test_entity_insertion_returns_none_and_lookup_retains_record(self):
        graph, record = CodeGraph(), entity("A")
        self.assertIsNone(graph.add_entity(record))
        self.assertIs(graph.get_entity("A"), record)
        self.assertTrue(graph.has_entity("A"))
        self.assertEqual(graph.entity_count, 1)

    def test_equal_entity_reinsertion_is_idempotent_and_keeps_original(self):
        graph, record = CodeGraph(), entity("A")
        graph.add_entity(record)
        self.assertIsNone(graph.add_entity(replace(record)))
        self.assertEqual(graph.entity_count, 1)
        self.assertIs(graph.get_entity("A"), record)

    def test_conflicting_entity_id_fails_without_overwriting(self):
        graph, record = CodeGraph(), entity("A")
        graph.add_entity(record)
        with self.assertRaises(DuplicateEntityError):
            graph.add_entity(replace(record, name="different"))
        self.assertIs(graph.get_entity("A"), record)
        self.assertEqual(graph.entity_count, 1)

    def test_relationship_insertion_returns_none_and_retains_record(self):
        graph = build_graph((entity("A"), entity("B")), ())
        edge = relationship("r", "A", "B")
        self.assertIsNone(graph.add_relationship(edge))
        self.assertIs(graph.get_relationship("r"), edge)
        self.assertTrue(graph.has_relationship("r"))
        self.assertEqual(graph.relationship_count, 1)
        self.assertEqual(graph.outgoing("A"), (edge,))
        self.assertEqual(graph.incoming("B"), (edge,))

    def test_relationship_rejects_missing_source_without_partial_state(self):
        graph = build_graph((entity("B"),), ())
        with self.assertRaises(UnknownEntityError):
            graph.add_relationship(relationship("r", "A", "B"))
        self.assertEqual(graph.relationship_count, 0)
        self.assertEqual(graph.incoming("B"), ())
        graph.add_entity(entity("A"))
        graph.add_relationship(relationship("r", "A", "B"))
        self.assertEqual(ids(graph.outgoing("A")), ("r",))

    def test_relationship_rejects_missing_target_without_partial_state(self):
        graph = build_graph((entity("A"),), ())
        with self.assertRaises(UnknownEntityError):
            graph.add_relationship(relationship("r", "A", "B"))
        self.assertEqual(graph.relationship_count, 0)
        self.assertEqual(graph.outgoing("A"), ())
        graph.add_entity(entity("B"))
        graph.add_relationship(relationship("r", "A", "B"))
        self.assertEqual(ids(graph.incoming("B")), ("r",))

    def test_equal_relationship_reinsertion_does_not_duplicate_indexes(self):
        edge = relationship("r", "A", "B")
        graph = build_graph((entity("A"), entity("B")), (edge,))
        self.assertIsNone(graph.add_relationship(replace(edge)))
        self.assertEqual(graph.relationship_count, 1)
        self.assertEqual(ids(graph.outgoing("A")), ("r",))
        self.assertEqual(ids(graph.incoming("B")), ("r",))
        self.assertIs(graph.get_relationship("r"), edge)

    def test_conflicting_relationship_id_fails_without_changing_indexes(self):
        edge = relationship("r", "A", "B")
        graph = build_graph((entity("A"), entity("B"), entity("C")), (edge,))
        for conflicting in (
            replace(edge, target_entity_id="C"),
            replace(edge, confidence=Confidence.LIKELY),
            replace(edge, evidence=()),
        ):
            with self.subTest(conflicting=conflicting), self.assertRaises(DuplicateRelationshipError):
                graph.add_relationship(conflicting)
        self.assertIs(graph.get_relationship("r"), edge)
        self.assertEqual(graph.incoming("C"), ())
        self.assertEqual(ids(graph.outgoing("A")), ("r",))

    def test_distinct_relationship_ids_preserve_parallel_edges_and_unique_neighbors(self):
        graph = build_graph((entity("A"), entity("B")), (relationship("r2", "A", "B"), relationship("r1", "A", "B")))
        self.assertEqual(ids(graph.outgoing("A")), ("r1", "r2"))
        self.assertEqual(ids(graph.successors("A")), ("B",))
        self.assertEqual(ids(graph.predecessors("B")), ("A",))
        self.assertEqual(graph.relationship_count, 2)

    def test_unresolved_relationship_still_requires_existing_placeholder_entity(self):
        edge = replace(relationship("r", "A", "placeholder"), confidence=Confidence.UNRESOLVED)
        graph = build_graph((entity("A"),), ())
        with self.assertRaises(UnknownEntityError):
            graph.add_relationship(edge)
        graph.add_entity(entity("placeholder"))
        graph.add_relationship(edge)
        self.assertIs(graph.get_relationship("r").confidence, Confidence.UNRESOLVED)

    def test_unknown_lookups_raise_intentional_graph_errors(self):
        graph = CodeGraph()
        for lookup, error in (
            (graph.get_entity, UnknownEntityError),
            (graph.get_relationship, UnknownRelationshipError),
        ):
            with self.subTest(lookup=lookup), self.assertRaises(error) as raised:
                lookup("missing")
            self.assertIsInstance(raised.exception, GraphError)

    def test_invalid_insert_types_fail_clearly(self):
        graph = CodeGraph()
        for insert in (graph.add_entity, graph.add_relationship):
            with self.subTest(insert=insert), self.assertRaises(TypeError):
                insert({"id": "A"})
        self.assertEqual((graph.entity_count, graph.relationship_count), (0, 0))

    def test_query_ids_must_be_strings(self):
        graph = CodeGraph()
        for query in (
            graph.get_entity,
            graph.get_relationship,
            graph.has_entity,
            graph.has_relationship,
            graph.outgoing,
            graph.incoming,
        ):
            with self.subTest(query=query), self.assertRaises(TypeError):
                query([])

    def test_snapshots_are_immutable_and_do_not_change_after_insertions(self):
        graph = build_graph((entity("A"),), ())
        entities, edges = graph.entities(), graph.relationships()
        with self.assertRaises(TypeError):
            entities[0] = entity("X")
        graph.add_entity(entity("B"))
        graph.add_relationship(relationship("r", "A", "B"))
        self.assertEqual(ids(entities), ("A",))
        self.assertEqual(edges, ())
        self.assertEqual((graph.entity_count, graph.relationship_count), (2, 1))


class AdjacencyTests(unittest.TestCase):
    def setUp(self):
        self.graph = payment_graph()

    def test_outgoing_is_directional_and_sorted_by_relationship_id(self):
        self.assertEqual(ids(self.graph.outgoing("controller")), ("controller-call", "import"))

    def test_incoming_is_directional_and_sorted_by_relationship_id(self):
        self.assertEqual(ids(self.graph.incoming("fraud")), ("fraud-call", "import"))

    def test_outgoing_can_filter_relationship_kind(self):
        self.assertEqual(ids(self.graph.outgoing("controller", kind=RelationshipKind.CALLS)), ("controller-call",))

    def test_incoming_can_filter_relationship_kind(self):
        self.assertEqual(ids(self.graph.incoming("fraud", kind=RelationshipKind.IMPORTS)), ("import",))

    def test_successors_return_unique_entities_sorted_by_id(self):
        self.assertEqual(ids(self.graph.successors("controller")), ("fraud", "service"))
        self.assertEqual(ids(self.graph.successors("controller", kind=RelationshipKind.CALLS)), ("service",))

    def test_predecessors_return_unique_entities_sorted_by_id(self):
        self.assertEqual(ids(self.graph.predecessors("fraud")), ("controller", "service"))
        self.assertEqual(ids(self.graph.predecessors("fraud", kind=RelationshipKind.CALLS)), ("service",))

    def test_known_isolated_entity_has_empty_adjacency_and_neighbors(self):
        for query in (self.graph.outgoing, self.graph.incoming, self.graph.successors, self.graph.predecessors):
            with self.subTest(query=query):
                self.assertEqual(query("isolated"), ())

    def test_unknown_adjacency_and_neighbor_ids_raise(self):
        for query in (self.graph.outgoing, self.graph.incoming, self.graph.successors, self.graph.predecessors):
            with self.subTest(query=query), self.assertRaises(UnknownEntityError):
                query("missing")

    def test_raw_string_kind_filters_are_rejected(self):
        for query in (self.graph.outgoing, self.graph.incoming, self.graph.successors, self.graph.predecessors):
            with self.subTest(query=query), self.assertRaises(TypeError):
                query("controller", kind="CALLS")

    def test_full_snapshots_and_neighbors_ignore_insertion_order(self):
        reverse = payment_graph(reverse_insertion=True)
        self.assertEqual(
            ids(self.graph.entities()),
            ("controller", "endpoint", "fraud", "isolated", "payment", "repository", "service"),
        )
        self.assertEqual(
            ids(self.graph.relationships()),
            ("controller-call", "expose", "fraud-call", "import", "repository-call", "write"),
        )
        self.assertEqual(self.graph.entities(), reverse.entities())
        self.assertEqual(self.graph.relationships(), reverse.relationships())
        for entity_id in ("controller", "fraud", "service"):
            self.assertEqual(self.graph.outgoing(entity_id), reverse.outgoing(entity_id))
            self.assertEqual(self.graph.incoming(entity_id), reverse.incoming(entity_id))
            self.assertEqual(self.graph.successors(entity_id), reverse.successors(entity_id))
            self.assertEqual(self.graph.predecessors(entity_id), reverse.predecessors(entity_id))
