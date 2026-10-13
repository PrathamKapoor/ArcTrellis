"""Inverted index, determinism, snapshot isolation and input-honesty contracts."""

import ast
import subprocess
import sys
import unittest
from dataclasses import fields, is_dataclass
from json import dumps
from pathlib import Path
from unittest.mock import patch

from arctrellis.core import Confidence, EntityKind, Relationship, RelationshipKind
from arctrellis.graph import CodeGraph
from arctrellis.graph.errors import DuplicateEntityError
from arctrellis.query import AnalysisCompleteness
from arctrellis.retrieval import LexicalSearchIndex, build_search_index
from arctrellis.retrieval.errors import InvalidSearchIndexError, RetrievalInvariantError
from tests.retrieval.fixtures import empty_graph, entity, payment_graph, synthetic_graph


def insert_in_reverse(graph):
    """Rebuild an equivalent graph in a different insertion order."""
    entities = graph.entities()
    relationships = graph.relationships()
    rebuilt = CodeGraph()
    for item in reversed(entities):
        rebuilt.add_entity(item)
    for item in reversed(relationships):
        rebuilt.add_relationship(item)
    return rebuilt


class IndexContractTests(unittest.TestCase):
    def test_required_statistics_are_present(self):
        index = build_search_index(payment_graph())
        self.assertEqual(index.document_count, 9)
        self.assertEqual(index.term_count, len(index.postings))
        self.assertEqual(index.posting_record_count, sum(len(item) for item in index.postings.values()))
        self.assertEqual(set(index.document_lengths), {item.entity_id for item in index.documents})
        self.assertEqual(set(index.documents_by_id), {item.entity_id for item in index.documents})
        for token, postings in index.postings.items():
            self.assertEqual(index.document_frequency[token], len(postings))
            self.assertEqual(postings, tuple(sorted(postings)))
        expected_average = sum(index.document_lengths.values()) / index.document_count
        self.assertAlmostEqual(index.average_document_length, expected_average)

    def test_postings_record_weighted_term_frequencies(self):
        from arctrellis.retrieval.scoring import weighted_term_frequency

        index = build_search_index(payment_graph())
        document = index.document("class:PaymentService")
        for token in document.distinct_tokens:
            with self.subTest(token=token):
                stored = dict(index.postings[token]).get("class:PaymentService")
                self.assertEqual(stored, weighted_term_frequency(document, token))

    def test_documents_are_sorted_by_entity_id_not_insertion_order(self):
        forward = build_search_index(payment_graph())
        backward = build_search_index(insert_in_reverse(payment_graph()))
        identifiers = [item.entity_id for item in forward.documents]
        self.assertEqual(identifiers, sorted(identifiers))
        self.assertEqual(forward.documents, backward.documents)
        self.assertEqual(dict(forward.postings), dict(backward.postings))
        self.assertEqual(forward.snapshot_id, backward.snapshot_id)
        self.assertEqual(forward.to_dict(), backward.to_dict())

    def test_different_graphs_have_different_snapshot_identities(self):
        first = build_search_index(payment_graph())
        second = build_search_index(synthetic_graph(3))
        self.assertNotEqual(first.snapshot_id, second.snapshot_id)
        self.assertNotEqual(first.to_dict(), second.to_dict())

    def test_index_retains_no_graph_source_or_parser_object(self):
        index = build_search_index(payment_graph())
        self.assertNotIsInstance(index, CodeGraph)
        serialized = dumps(index.to_dict())
        self.assertNotIn("tree_sitter", serialized)
        self.assertEqual(
            sorted(index.to_dict()),
            [
                "analysis_completeness",
                "average_document_length",
                "context_capped_list_count",
                "context_edge_count",
                "context_max_neighbors_per_entity",
                "document_count",
                "posting_record_count",
                "snapshot_id",
                "source_entity_count",
                "source_relationship_count",
                "term_count",
            ],
        )
        for value in (index.documents, index.postings, index.document_lengths, index.document_frequency):
            self.assertNotIsInstance(value, (dict, list, set))

    def test_index_containers_are_read_only(self):
        index = build_search_index(payment_graph())
        with self.assertRaises(TypeError):
            index.postings["payment"] = ()
        with self.assertRaises(TypeError):
            index.document_lengths["x"] = 1
        with self.assertRaises(TypeError):
            index.documents_by_id["x"] = None
        with self.assertRaises(TypeError):
            index.document_frequency["payment"] = 1

    def test_build_does_not_mutate_or_reread_the_input_graph(self):
        graph = payment_graph()
        before_entities, before_relationships = graph.entities(), graph.relationships()
        with (
            patch("builtins.open", side_effect=AssertionError("filesystem")),
            patch("os.open", side_effect=AssertionError("filesystem")),
            patch.object(CodeGraph, "add_entity", side_effect=AssertionError("mutation")),
            patch.object(CodeGraph, "add_relationship", side_effect=AssertionError("mutation")),
        ):
            index = build_search_index(graph)
        self.assertEqual(before_entities, graph.entities())
        self.assertEqual(before_relationships, graph.relationships())
        self.assertEqual(index.document_count, len(before_entities))

    @staticmethod
    def _walk(value):
        pending = [value]
        while pending:
            current = pending.pop()
            yield current
            if isinstance(current, dict):
                pending.extend(current.values())
            elif isinstance(current, (tuple, list, set, frozenset)):
                pending.extend(current)
            elif is_dataclass(current):
                pending.extend(getattr(current, item.name) for item in fields(current))

    def test_index_never_retains_parsed_source_or_syntax_objects(self):
        from arctrellis.parsing import ParsedSource, SyntaxNode

        index = build_search_index(payment_graph())
        for value in self._walk(index):
            self.assertNotIsInstance(value, (ParsedSource, SyntaxNode, bytes, bytearray, CodeGraph))
            if isinstance(value, str):
                self.assertNotIn("tree_sitter", value)

    def test_snapshot_does_not_observe_later_graph_mutation(self):
        graph = payment_graph()
        index = build_search_index(graph)
        graph.add_entity(
            entity(
                "late:entity",
                EntityKind.FUNCTION,
                "latePayment",
                "late.py::latePayment",
                path="late.py",
                language="python",
            )
        )
        self.assertIsNone(index.document("late:entity"))
        self.assertNotIn("latepayment", index.postings)
        self.assertEqual(index.document_count, 9)
        self.assertEqual(index.source_entity_count, 9)
        fresh = build_search_index(graph)
        self.assertIsNotNone(fresh.document("late:entity"))
        self.assertNotEqual(fresh.snapshot_id, index.snapshot_id)

    def test_relationship_changes_do_not_alter_the_lexical_snapshot(self):
        graph = payment_graph()
        index = build_search_index(graph)
        graph.add_relationship(
            Relationship(
                "rel:new",
                "endpoint:get-users-id",
                RelationshipKind.CALLS,
                "function:createPayment",
                Confidence.LIKELY,
                0.85,
            )
        )
        self.assertEqual(build_search_index(graph).documents, index.documents)
        self.assertEqual(build_search_index(graph).snapshot_id, index.snapshot_id)
        self.assertNotEqual(build_search_index(graph).source_relationship_count, index.source_relationship_count)

    def test_empty_graph_index_is_valid_and_empty(self):
        index = build_search_index(empty_graph())
        self.assertEqual(index.postings, {})
        self.assertEqual(index.document_lengths, {})
        self.assertEqual(index.document_frequency, {})
        self.assertEqual(index.posting_record_count, 0)
        self.assertEqual(index.term_count, 0)
        self.assertEqual(index.average_document_length, 0.0)
        self.assertTrue(index.snapshot_id)

    def test_invalid_container_types_are_rejected(self):
        with self.assertRaises(InvalidSearchIndexError):
            build_search_index({"entities": []})
        with self.assertRaises(TypeError):
            build_search_index(payment_graph(), analysis_completeness="complete")

    def test_corrupt_enumeration_fails_explicitly(self):
        class DuplicateEnumeration(CodeGraph):
            def entities(self):
                first = super().entities()
                return first + first

        class MissingEnumeration(CodeGraph):
            def entities(self):
                return super().entities()[:-1]

        graph = DuplicateEnumeration()
        graph.add_entity(entity("a", EntityKind.MODULE, "a", "a", path="a.py"))
        with self.assertRaises(RetrievalInvariantError):
            build_search_index(graph)

        other = MissingEnumeration()
        other.add_entity(entity("a", EntityKind.MODULE, "a", "a", path="a.py"))
        other.add_entity(entity("b", EntityKind.MODULE, "b", "b", path="b.py"))
        with self.assertRaises(RetrievalInvariantError):
            build_search_index(other)

    def test_conflicting_duplicate_identity_fails_before_projection(self):
        graph = CodeGraph()
        graph.add_entity(entity("same", EntityKind.MODULE, "one", "one", path="one.py"))
        with self.assertRaises(DuplicateEntityError):
            graph.add_entity(entity("same", EntityKind.MODULE, "two", "two", path="two.py"))

    def test_index_rejects_inconsistent_statistics(self):
        index = build_search_index(payment_graph())
        wrong_lengths = dict(index.document_lengths)
        wrong_lengths["class:PaymentService"] += 1
        with self.assertRaises(RetrievalInvariantError):
            LexicalSearchIndex(
                documents=index.documents,
                postings=index.postings,
                document_lengths=wrong_lengths,
                document_frequency=index.document_frequency,
                source_entity_count=index.source_entity_count,
                source_relationship_count=index.source_relationship_count,
                snapshot_id=index.snapshot_id,
            )
        with self.assertRaises(RetrievalInvariantError):
            LexicalSearchIndex(
                documents=index.documents,
                postings={
                    token: tuple((identifier, frequency + 1) for identifier, frequency in postings)
                    for token, postings in index.postings.items()
                },
                document_lengths=index.document_lengths,
                document_frequency=index.document_frequency,
                source_entity_count=index.source_entity_count,
                source_relationship_count=index.source_relationship_count,
                snapshot_id=index.snapshot_id,
            )
        with self.assertRaises(RetrievalInvariantError):
            LexicalSearchIndex(
                documents=index.documents,
                postings=index.postings,
                document_lengths=index.document_lengths,
                document_frequency={token: 1 for token in index.document_frequency},
                source_entity_count=index.source_entity_count,
                source_relationship_count=index.source_relationship_count,
                snapshot_id=index.snapshot_id,
            )

    def test_analysis_completeness_is_caller_supplied_not_inferred(self):
        self.assertIs(build_search_index(payment_graph()).analysis_completeness, AnalysisCompleteness.UNKNOWN)
        self.assertIs(
            build_search_index(
                payment_graph(), analysis_completeness=AnalysisCompleteness.PARTIAL
            ).analysis_completeness,
            AnalysisCompleteness.PARTIAL,
        )

    def test_larger_corpus_remains_deterministic_and_bounded(self):
        first = build_search_index(synthetic_graph(200))
        second = build_search_index(insert_in_reverse(synthetic_graph(200)))
        self.assertEqual(first.document_count, 201)
        self.assertEqual(first.postings, second.postings)
        self.assertEqual(first.snapshot_id, second.snapshot_id)
        self.assertLessEqual(first.posting_record_count, first.document_count * 16)

    def test_retrieval_import_boundary_and_fresh_public_import(self):
        root = Path(__file__).resolve().parents[2] / "src/arctrellis/retrieval"
        for path in sorted(root.glob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                modules: list[str] = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    modules = [node.module]
                with self.subTest(path=path.name, modules=modules):
                    self.assertFalse(
                        any(
                            name.split(".")[0]
                            in ("tree_sitter", "sqlalchemy", "prisma", "fastapi", "requests", "httpx", "numpy")
                            for name in modules
                        )
                    )
                    self.assertFalse(
                        any(
                            name.startswith("arctrellis.indexing")
                            or name.startswith("arctrellis.parsing")
                            or name.startswith("arctrellis.ingestion")
                            for name in modules
                        )
                    )
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import arctrellis.retrieval as r; "
                "assert all(hasattr(r, name) for name in r.__all__); "
                "from arctrellis.retrieval import (build_search_index, search_symbols, search_endpoints, "
                "search_tests, search_database_operations, evaluate_retrieval); "
                'assert not any(name.startswith(("arctrellis.parsing", "arctrellis.indexing", "tree_sitter", '
                '"sqlalchemy", "prisma", "fastapi")) for name in sys.modules)',
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
