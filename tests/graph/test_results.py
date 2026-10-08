"""Immutable public query results enforce their own structural contracts."""

from dataclasses import FrozenInstanceError, replace
import unittest

from arctrellis.graph import GraphPath, TraversalResult
from .fixtures import entity, relationship


class ResultTests(unittest.TestCase):
    def test_graph_path_accepts_connected_directed_edges_and_zero_edge_path(self):
        path = GraphPath((entity("A"), entity("B")), (relationship("r", "A", "B"),))
        self.assertEqual(len(path.entities), len(path.relationships) + 1)
        self.assertEqual(GraphPath((entity("A"),), ()).relationships, ())

    def test_graph_path_rejects_empty_and_mismatched_cardinality(self):
        for entities, relationships in (((), ()), ((entity("A"), entity("B")), ()),
                                        ((entity("A"),), (relationship("r", "A", "B"),))):
            with self.subTest(entities=entities), self.assertRaises(ValueError):
                GraphPath(entities, relationships)

    def test_graph_path_rejects_disconnected_or_reversed_edges(self):
        for edge in (relationship("r", "B", "A"), relationship("r", "A", "C")):
            with self.subTest(edge=edge), self.assertRaises(ValueError):
                GraphPath((entity("A"), entity("B")), (edge,))

    def test_result_records_require_tuples_of_domain_records(self):
        for entities in ([entity("A")], ("A",)):
            with self.subTest(entities=entities):
                with self.assertRaises(TypeError):
                    TraversalResult(entities)
                with self.assertRaises(TypeError):
                    GraphPath(entities, ())
        for edges in ([relationship("r", "A", "B")], ("r",)):
            with self.subTest(edges=edges), self.assertRaises(TypeError):
                GraphPath((entity("A"), entity("B")), edges)

    def test_traversal_result_rejects_empty_or_duplicate_entity_ids(self):
        for entities in ((), (entity("A"), entity("A"))):
            with self.subTest(entities=entities), self.assertRaises(ValueError):
                TraversalResult(entities)

    def test_results_are_immutable_hashable_value_objects(self):
        results = (GraphPath((entity("A"),), ()), TraversalResult((entity("A"),)))
        for result in results:
            with self.subTest(result=result):
                self.assertEqual(replace(result), result)
                self.assertEqual(hash(replace(result)), hash(result))
                with self.assertRaises(FrozenInstanceError):
                    result.entities = ()
                with self.assertRaises(TypeError):
                    result.entities[0] = entity("B")
