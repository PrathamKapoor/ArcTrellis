"""Bounded breadth-first reachability and evidence-preserving path contracts."""

import unittest

from arctrellis.core import RelationshipKind
from arctrellis.graph import UnknownEntityError

from .fixtures import build_graph, entity, ids, payment_graph, relationship


class TraversalTests(unittest.TestCase):
    def setUp(self):
        self.graph = payment_graph()

    def test_forward_depth_zero_contains_only_start(self):
        self.assertEqual(ids(self.graph.traverse_forward("endpoint", 0).entities), ("endpoint",))

    def test_forward_depth_one_contains_direct_neighbors(self):
        self.assertEqual(ids(self.graph.traverse_forward("controller", 1).entities), ("controller", "service", "fraud"))

    def test_forward_depth_two_discovers_each_reachable_node_once(self):
        self.assertEqual(
            ids(self.graph.traverse_forward("controller", 2).entities), ("controller", "service", "fraud", "repository")
        )

    def test_forward_depth_three_reaches_database_operation(self):
        self.assertEqual(
            ids(self.graph.traverse_forward("controller", 3).entities),
            ("controller", "service", "fraud", "repository", "payment"),
        )

    def test_reverse_traversal_follows_incoming_edges(self):
        self.assertEqual(
            ids(self.graph.traverse_reverse("payment", 3).entities), ("payment", "repository", "service", "controller")
        )
        self.assertEqual(ids(self.graph.traverse_reverse("payment", 0).entities), ("payment",))

    def test_forward_and_reverse_kind_filters_constrain_every_step(self):
        kinds = {RelationshipKind.CALLS}
        self.assertEqual(
            ids(self.graph.traverse_forward("controller", 10, relationship_kinds=kinds).entities),
            ("controller", "service", "fraud", "repository"),
        )
        self.assertEqual(
            ids(self.graph.traverse_reverse("fraud", 10, relationship_kinds=kinds).entities),
            ("fraud", "service", "controller"),
        )
        self.assertEqual(
            ids(self.graph.traverse_forward("endpoint", 10, relationship_kinds=kinds).entities), ("endpoint",)
        )

    def test_empty_kind_filter_follows_no_edges(self):
        for traverse in (self.graph.traverse_forward, self.graph.traverse_reverse):
            self.assertEqual(ids(traverse("controller", 10, relationship_kinds=set()).entities), ("controller",))

    def test_cycle_and_self_loop_terminate_without_repeated_nodes(self):
        graph = build_graph(
            tuple(entity(name) for name in ("A", "B", "C")),
            (
                relationship("ab", "A", "B"),
                relationship("bc", "B", "C"),
                relationship("ca", "C", "A"),
                relationship("self", "A", "A"),
            ),
        )
        self.assertEqual(ids(graph.traverse_forward("A", 100).entities), ("A", "B", "C"))
        self.assertEqual(ids(graph.traverse_reverse("A", 100).entities), ("A", "C", "B"))
        self.assertEqual(ids(graph.traverse_forward("A", 1).entities), ("A", "B"))

    def test_parallel_edges_do_not_repeat_traversed_entities(self):
        graph = build_graph(
            (entity("A"), entity("B")), (relationship("first", "A", "B"), relationship("second", "A", "B"))
        )
        self.assertEqual(ids(graph.traverse_forward("A", 10).entities), ("A", "B"))

    def test_traversal_results_ignore_insertion_order(self):
        reverse = payment_graph(reverse_insertion=True)
        for start in ("controller", "payment", "endpoint"):
            for depth in (0, 1, 2, 10):
                for kinds in (
                    None,
                    set(),
                    {RelationshipKind.CALLS},
                    {RelationshipKind.CALLS, RelationshipKind.EXPOSES},
                ):
                    with self.subTest(start=start, depth=depth, kinds=kinds):
                        self.assertEqual(
                            self.graph.traverse_forward(start, depth, relationship_kinds=kinds),
                            reverse.traverse_forward(start, depth, relationship_kinds=kinds),
                        )
                        self.assertEqual(
                            self.graph.traverse_reverse(start, depth, relationship_kinds=kinds),
                            reverse.traverse_reverse(start, depth, relationship_kinds=kinds),
                        )

    def test_traversal_rejects_unknown_start(self):
        for traverse in (self.graph.traverse_forward, self.graph.traverse_reverse):
            with self.subTest(traverse=traverse), self.assertRaises(UnknownEntityError):
                traverse("missing", 0)

    def test_traversal_rejects_negative_and_noninteger_depth(self):
        for traverse in (self.graph.traverse_forward, self.graph.traverse_reverse):
            with self.assertRaises(ValueError):
                traverse("controller", -1)
            for depth in (True, 1.5, "2", None):
                with self.subTest(depth=depth), self.assertRaises(TypeError):
                    traverse("controller", depth)

    def test_traversal_and_path_reject_invalid_kind_collections(self):
        for kinds in ([RelationshipKind.CALLS], "CALLS", {"CALLS"}, {1}):
            with self.subTest(kinds=kinds):
                with self.assertRaises(TypeError):
                    self.graph.traverse_forward("controller", 2, relationship_kinds=kinds)
                with self.assertRaises(TypeError):
                    self.graph.traverse_reverse("controller", 2, relationship_kinds=kinds)
                with self.assertRaises(TypeError):
                    self.graph.shortest_path("controller", "service", relationship_kinds=kinds)


class ShortestPathTests(unittest.TestCase):
    def setUp(self):
        self.graph = payment_graph()

    def test_shortest_direct_path_retains_original_relationship_and_evidence(self):
        path = self.graph.shortest_path("controller", "service")
        self.assertEqual(ids(path.entities), ("controller", "service"))
        self.assertEqual(ids(path.relationships), ("controller-call",))
        self.assertIs(path.relationships[0], self.graph.get_relationship("controller-call"))
        self.assertIs(path.relationships[0].evidence[0], self.graph.get_relationship("controller-call").evidence[0])
        self.assertEqual(path.relationships[0].evidence[0].location.start_line, 61)

    def test_shortest_multi_hop_path_retains_every_edge_in_order(self):
        path = self.graph.shortest_path("endpoint", "payment")
        self.assertEqual(ids(path.entities), ("endpoint", "controller", "service", "repository", "payment"))
        self.assertEqual(ids(path.relationships), ("expose", "controller-call", "repository-call", "write"))
        self.assertEqual(len(path.entities), len(path.relationships) + 1)

    def test_shortest_path_prefers_fewer_edges_over_lexically_first_long_route(self):
        graph = build_graph(
            tuple(entity(name) for name in ("A", "B", "C", "D", "E")),
            (
                relationship("01-long", "A", "B"),
                relationship("02-short", "A", "D"),
                relationship("bc", "B", "C"),
                relationship("ce", "C", "E"),
                relationship("de", "D", "E"),
            ),
        )
        self.assertEqual(ids(graph.shortest_path("A", "E").entities), ("A", "D", "E"))

    def test_same_node_path_contains_one_entity_and_no_edges(self):
        path = self.graph.shortest_path("controller", "controller")
        self.assertEqual(ids(path.entities), ("controller",))
        self.assertEqual(path.relationships, ())

    def test_no_path_returns_none_for_known_nodes(self):
        self.assertIsNone(self.graph.shortest_path("endpoint", "isolated"))
        self.assertIsNone(self.graph.shortest_path("service", "controller"))

    def test_shortest_path_rejects_unknown_source(self):
        with self.assertRaises(UnknownEntityError):
            self.graph.shortest_path("missing", "controller")

    def test_shortest_path_rejects_unknown_target(self):
        with self.assertRaises(UnknownEntityError):
            self.graph.shortest_path("controller", "missing")

    def test_shortest_path_filters_relationship_kinds_at_every_hop(self):
        path = self.graph.shortest_path("controller", "fraud", relationship_kinds={RelationshipKind.CALLS})
        self.assertEqual(ids(path.entities), ("controller", "service", "fraud"))
        self.assertEqual(ids(path.relationships), ("controller-call", "fraud-call"))
        self.assertIsNone(self.graph.shortest_path("endpoint", "service", relationship_kinds={RelationshipKind.CALLS}))

    def test_empty_kind_filter_allows_only_same_node_paths(self):
        self.assertIsNone(self.graph.shortest_path("controller", "service", relationship_kinds=set()))
        self.assertEqual(
            ids(self.graph.shortest_path("controller", "controller", relationship_kinds=frozenset()).entities),
            ("controller",),
        )

    def test_equal_length_paths_break_ties_by_sorted_adjacency_ids(self):
        entities = tuple(entity(name) for name in ("A", "B", "C", "D"))
        edges = (
            relationship("a-to-c", "A", "C"),
            relationship("z-to-b", "A", "B"),
            relationship("c-to-d", "C", "D"),
            relationship("b-to-d", "B", "D"),
        )
        first, second = build_graph(entities, edges), build_graph(entities[::-1], edges[::-1])
        self.assertEqual(ids(first.shortest_path("A", "D").entities), ("A", "C", "D"))
        self.assertEqual(first.shortest_path("A", "D"), second.shortest_path("A", "D"))

    def test_parallel_edge_paths_choose_lower_relationship_id(self):
        graph = build_graph((entity("A"), entity("B")), (relationship("z", "A", "B"), relationship("a", "A", "B")))
        self.assertEqual(ids(graph.shortest_path("A", "B").relationships), ("a",))

    def test_shortest_path_terminates_on_cycles_and_self_loops(self):
        graph = build_graph(
            tuple(entity(name) for name in ("A", "B", "C", "D")),
            (
                relationship("ab", "A", "B"),
                relationship("bc", "B", "C"),
                relationship("ca", "C", "A"),
                relationship("aa", "A", "A"),
            ),
        )
        self.assertEqual(ids(graph.shortest_path("A", "C").entities), ("A", "B", "C"))
        self.assertIsNone(graph.shortest_path("A", "D"))
