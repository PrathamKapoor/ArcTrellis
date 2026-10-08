"""Source-derived lexical ownership, proof preservation and graph compatibility."""

import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import UUID

import arctrellis.extraction as extraction
from arctrellis.core import Confidence
from arctrellis.core import EntityKind as K
from arctrellis.core import RelationshipKind as R
from arctrellis.ingestion import Language, scan_repository
from arctrellis.parsing import parse_discovered_file, parse_source


class LexicalGraphTests(unittest.TestCase):
    def result(self, source, language=Language.PYTHON):
        extension = {Language.PYTHON: "py", Language.JAVASCRIPT: "js", Language.TYPESCRIPT: "ts"}[language]
        return extraction.extract_entities(parse_source("service." + extension, language, source))

    def test_public_builder_exists(self):
        self.assertTrue(callable(getattr(extraction, "build_lexical_graph", None)))

    def test_all_entities_and_exactly_one_parent_edge_for_each_child(self):
        samples = [
            (
                Language.PYTHON,
                (
                    b"import os\nclass Service:\n    def create(self):\n        import sec"
                    b"rets\n        def helper():\n            pass\n"
                ),
            ),
            (
                Language.JAVASCRIPT,
                b'import A from "m"; const arrow = () => {}; class Service { create() { function helper() {} } }',
            ),
            (
                Language.TYPESCRIPT,
                b'import type { A } from "m"; const arrow = (x: string) => x; class Service { create(): void {} }',
            ),
        ]
        for language, source in samples:
            with self.subTest(language=language):
                result = self.result(source, language)
                graph = extraction.build_lexical_graph(result)
                self.assertEqual(graph.entities(), tuple(sorted(result.entities, key=lambda e: e.id)))
                self.assertEqual(graph.entity_count, len(result.entities))
                self.assertEqual(graph.relationship_count, len(result.entities) - 1)
                self.assertEqual(graph.incoming(result.module.id), ())
                for child in result.entities[1:]:
                    (edge,) = graph.incoming(child.id)
                    self.assertEqual(
                        (edge.source_entity_id, edge.target_entity_id, edge.kind),
                        (child.parent_id, child.id, R.DEFINES),
                    )
                    self.assertEqual((edge.confidence, edge.confidence_score), (Confidence.PROVEN, 1.0))
                    (evidence,) = edge.evidence
                    self.assertEqual(evidence.location, child.location)
                    self.assertEqual(evidence.analysis_method, "lexical_parentage")
                    metadata = dict(evidence.metadata)
                    for key in ("start_byte", "end_byte", "start_line", "end_line", "start_column", "end_column"):
                        self.assertEqual(metadata[key], dict(child.metadata)[key])
                    self.assertEqual(graph.get_relationship(edge.id).evidence, edge.evidence)
                self.assertEqual({edge.kind for edge in graph.relationships()}, {R.DEFINES})

    def test_empty_modules_have_no_fabricated_parent_relationship(self):
        for language in Language:
            result = self.result(b"", language)
            graph = extraction.build_lexical_graph(result)
            self.assertEqual((graph.entity_count, graph.relationship_count), (1, 0))

    def test_repeat_builds_have_equal_snapshots_and_uuid5_proofs(self):
        result = self.result(b"def outer():\n    def inner():\n        pass\n")
        first, second = extraction.build_lexical_graph(result), extraction.build_lexical_graph(result)
        self.assertIsNot(first, second)
        self.assertEqual(first.entities(), second.entities())
        self.assertEqual(first.relationships(), second.relationships())
        for edge in first.relationships():
            self.assertEqual(UUID(edge.id).version, 5)
            self.assertEqual(UUID(edge.evidence[0].id).version, 5)
        self.assertEqual(len({e.evidence[0].id for e in first.relationships()}), 2)

    def test_proof_identity_changes_with_child_position_and_file(self):
        first = extraction.build_lexical_graph(self.result(b"def f():\n    pass\n")).relationships()[0]
        second = extraction.build_lexical_graph(self.result(b"\ndef f():\n    pass\n")).relationships()[0]
        self.assertNotEqual(first.id, second.id)
        self.assertNotEqual(first.evidence[0].id, second.evidence[0].id)
        different = extraction.extract_entities(parse_source("other.py", Language.PYTHON, b"def f():\n    pass\n"))
        third = extraction.build_lexical_graph(different).relationships()[0]
        self.assertNotEqual(first.id, third.id)
        self.assertNotEqual(first.evidence[0].id, third.evidence[0].id)

    def test_shortest_path_retains_actual_evidence_and_direction(self):
        result = self.result(b"class Service:\n    def create(self):\n        pass\n")
        graph = extraction.build_lexical_graph(result)
        cls, method = result.entities[1:]
        path = graph.shortest_path(result.module.id, method.id, relationship_kinds={R.DEFINES})
        self.assertEqual(path.entities, (result.module, cls, method))
        self.assertEqual(len(path.relationships), 2)
        for edge, child in zip(path.relationships, (cls, method), strict=True):
            self.assertIs(edge, graph.get_relationship(edge.id))
            self.assertEqual(edge.evidence[0].location, child.location)
        self.assertIsNone(graph.shortest_path(method.id, result.module.id))

    def test_import_entities_get_defines_not_resolved_dependencies(self):
        result = self.result(b"def run():\n    from pathlib import Path\n")
        graph = extraction.build_lexical_graph(result)
        (imported,) = result.entities_of_kind(K.IMPORT)
        (edge,) = graph.incoming(imported.id)
        self.assertEqual(edge.kind, R.DEFINES)
        for forbidden in (R.CONTAINS, R.IMPORTS, R.CALLS, R.INHERITS):
            self.assertFalse(any(e.kind is forbidden for e in graph.relationships()))

    def test_partial_results_keep_only_surviving_proven_edges(self):
        for language, data in [
            (Language.PYTHON, b"def good():\n    pass\ndef broken(\n"),
            (Language.JAVASCRIPT, b"function good() {} function broken( {"),
            (Language.TYPESCRIPT, b"function good() {} function broken( {"),
        ]:
            result = self.result(data, language)
            self.assertTrue(result.partial)
            graph = extraction.build_lexical_graph(result)
            self.assertEqual([e.name for e in result.entities[1:]], ["good"])
            (edge,) = graph.relationships()
            self.assertEqual(edge.confidence, Confidence.PROVEN)

    def test_invalid_type_and_corrupted_result_fail_explicitly(self):
        with self.assertRaises(TypeError):
            extraction.build_lexical_graph(None)
        result = self.result(b"def f():\n    pass\n")
        module, function = result.entities
        # Simulate a producer violating frozen-result invariants, not source recovery.
        object.__setattr__(result, "entities", (module, replace(function, parent_id="missing")))
        with self.assertRaises(extraction.SemanticExtractionError) as caught:
            extraction.build_lexical_graph(result)
        self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_builder_performs_no_filesystem_access(self):
        result = self.result(b"def f():\n    pass\n")
        with patch("builtins.open", side_effect=AssertionError("no graph-building I/O")):
            graph = extraction.build_lexical_graph(result)
        self.assertEqual(graph.relationship_count, 1)

    def test_scan_parse_extract_graph_pipeline_for_all_v1_languages(self):
        samples = {
            "a.py": b"class Service:\n    def create(self):\n        pass\n",
            "b.js": b"class Service { create() {} }",
            "c.tsx": b"class Service { create(): void {} } function Button() { return <button/>; }",
        }
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name, source in samples.items():
                (root / name).write_bytes(source)
            for file in scan_repository(root).supported_files:
                result = extraction.extract_entities(parse_discovered_file(root, file))
                graph = extraction.build_lexical_graph(result)
                (method,) = result.entities_of_kind(K.METHOD)
                path = graph.shortest_path(result.module.id, method.id)
                self.assertEqual([e.kind for e in path.entities], [K.MODULE, K.CLASS, K.METHOD])
                self.assertTrue(all(edge.evidence for edge in path.relationships))
