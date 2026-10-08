import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import arctrellis.indexing as indexing
from arctrellis.core import Confidence
from arctrellis.core import EntityKind as K
from arctrellis.core import RelationshipKind as R
from arctrellis.parsing import ParsedSource, SourceReadError, SyntaxNode


class RepositoryTests(unittest.TestCase):
    def index(self, files):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name, source in files.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source)
            return indexing.index_repository(root)

    def test_empty_and_unsupported_only_are_complete(self):
        for files in ({}, {"README.md": b"documentation"}):
            result = self.index(files)
            self.assertTrue(result.is_complete)
            self.assertEqual(result.supported_file_count, 0)
            self.assertEqual(result.file_results, ())
            self.assertEqual(result.entity_count, 0)

    def test_mixed_sources_structural_edges_and_traversal(self):
        files = {
            "backend/service.py": b"class Service:\n    def create(self):\n        pass\n",
            "worker.js": b"class Worker { run() {} }",
            "frontend/api.ts": b"function api(x: string): void {}",
            "frontend/Button.tsx": b"function Button() { return <button/>; }",
            "README.md": b"doc",
            "node_modules/ignored.js": b"function ignored() {}",
        }
        result = self.index(files)
        self.assertEqual(
            (
                result.supported_file_count,
                result.complete_file_count,
                result.partial_file_count,
                result.failed_file_count,
            ),
            (4, 4, 0, 0),
        )
        self.assertTrue(result.is_complete)
        self.assertEqual(
            [f.path for f in result.file_results], sorted(set(files) - {"README.md", "node_modules/ignored.js"})
        )
        structural = [e for e in result.graph.entities() if e.kind is K.FILE]
        self.assertEqual(len(structural), 4)
        for file in structural:
            self.assertIsNone(file.parent_id)
            self.assertIsNone(file.location)
            (membership,) = result.graph.outgoing(file.id)
            self.assertEqual(
                (membership.kind, membership.confidence, membership.confidence_score),
                (R.DEFINES, Confidence.PROVEN, 1.0),
            )
            self.assertEqual(membership.evidence[0].analysis_method, "file_module_membership")
            module = result.graph.get_entity(membership.target_entity_id)
            self.assertEqual(membership.evidence[0].location, module.location)
        method = next(e for e in result.graph.entities() if e.kind is K.METHOD and e.language == "python")
        file = next(e for e in structural if e.qualified_name == "backend/service.py")
        path = result.graph.shortest_path(file.id, method.id)
        self.assertEqual([e.kind for e in path.entities], [K.FILE, K.MODULE, K.CLASS, K.METHOD])
        self.assertTrue(all(edge.evidence for edge in path.relationships))

    def test_one_file_per_language_and_repeatability(self):
        for name, source in [
            ("a.py", b"def f():\n    pass\n"),
            ("a.js", b"function f() {}"),
            ("a.ts", b"function f(): void {}"),
        ]:
            a, b = self.index({name: source}), self.index({name: source})
            self.assertEqual(a.file_results, b.file_results)
            self.assertEqual(a.graph.entities(), b.graph.entities())
            self.assertEqual(a.graph.relationships(), b.graph.relationships())
            self.assertEqual((a.entity_count, a.relationship_count), (3, 2))

    def test_partial_and_failed_are_explicit(self):
        result = self.index(
            {"a.py": b"def good():\n    pass\ndef broken(\n", "b.js": b"// \xff", "c.ts": b"function good() {}"}
        )
        self.assertEqual(
            [f.status for f in result.file_results],
            [indexing.FileIndexStatus.PARTIAL, indexing.FileIndexStatus.FAILED, indexing.FileIndexStatus.COMPLETE],
        )
        self.assertFalse(result.is_complete)
        self.assertGreater(result.file_results[0].diagnostic_count, 0)
        self.assertEqual(result.file_results[1].entity_count, 0)
        self.assertEqual(result.file_results[1].error_type, "SourceDecodingError")

    def test_read_failure_continues_with_other_files_without_retaining_error(self):
        from arctrellis.indexing.repository import parse_discovered_file

        def fail_one(root, file, **kwargs):
            if file.path == "a.py":
                raise SourceReadError("secret source detail must not leak")
            return parse_discovered_file(root, file, **kwargs)

        with patch("arctrellis.indexing.repository.parse_discovered_file", side_effect=fail_one):
            result = self.index({"a.py": b"", "b.py": b"def b():\n    pass\n"})
        self.assertEqual((result.failed_file_count, result.complete_file_count), (1, 1))
        self.assertNotIn("secret", result.file_results[0].error_message)
        self.assertFalse(result.is_complete)

    def test_discovery_failure_aborts(self):
        from arctrellis.ingestion import InvalidRepositoryPathError

        with TemporaryDirectory() as directory, self.assertRaises(InvalidRepositoryPathError):
            indexing.index_repository(Path(directory) / "missing")

    def test_merge_collisions_abort_instead_of_becoming_file_failure(self):
        from arctrellis.indexing.repository import _file_entity

        def collide(file, size):
            return replace(_file_entity(file, size), id="collision")

        with (
            patch("arctrellis.indexing.repository._file_entity", side_effect=collide),
            self.assertRaises(indexing.RepositoryIndexInvariantError),
        ):
            self.index({"a.py": b"", "b.py": b""})

    def test_file_identity_is_stable_across_content_changes(self):
        a, b = self.index({"a.py": b""}), self.index({"a.py": b"def f():\n    pass\n"})
        self.assertEqual(
            next(e.id for e in a.graph.entities() if e.kind is K.FILE),
            next(e.id for e in b.graph.entities() if e.kind is K.FILE),
        )

    def test_repository_summary_contains_no_trees_bytes_or_exceptions(self):
        result = self.index({"a.py": b"def f():\n    pass\n"})
        pending = [result.inventory, result.file_results, result.graph.entities(), result.graph.relationships()]
        while pending:
            value = pending.pop()
            self.assertNotIsInstance(value, (ParsedSource, SyntaxNode, bytes, BaseException))
            if is_dataclass(value):
                pending.extend(getattr(value, f.name) for f in fields(value))
            elif isinstance(value, tuple):
                pending.extend(value)

    def test_summary_validation_and_immutability(self):
        result = self.index({"a.py": b""})
        (file,) = result.file_results
        with self.assertRaises(FrozenInstanceError):
            file.entity_count = 0
        for kwargs in (
            {"entity_count": -1},
            {"status": "COMPLETE"},
            {"diagnostic_count": True},
            {"error_type": "error"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises((TypeError, ValueError)):
                replace(file, **kwargs)
        with self.assertRaises(ValueError):
            replace(result, file_results=())
