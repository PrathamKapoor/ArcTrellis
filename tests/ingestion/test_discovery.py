import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from arctrellis.ingestion import (DEFAULT_EXCLUDED_DIRECTORIES, InvalidRepositoryPathError,
    Language, RepositoryAccessError, SkipReason, scan_repository)


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, path, content="x"):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def test_empty_directory_without_git_is_valid(self):
        result = scan_repository(self.root)
        self.assertEqual(result.files, ())
        self.assertEqual(result.skipped_paths, ())
        self.assertEqual(result.file_count, 0)

    def test_nested_files_have_relative_posix_paths_and_sizes(self):
        self.write("src/nested/app.py", "abc")
        self.write("README.md", "hi")
        result = scan_repository(self.root)
        self.assertEqual([(f.path, f.size_bytes) for f in result.files], [("README.md", 2), ("src/nested/app.py", 3)])
        self.assertEqual([f.path for f in result.supported_files], ["src/nested/app.py"])

    def test_single_file(self):
        self.write("app.py")
        self.assertEqual(scan_repository(self.root).file_count, 1)

    def test_all_extensions_and_case_preservation(self):
        extensions = {"py": Language.PYTHON, "pyi": Language.PYTHON, "js": Language.JAVASCRIPT,
            "jsx": Language.JAVASCRIPT, "mjs": Language.JAVASCRIPT, "cjs": Language.JAVASCRIPT,
            "ts": Language.TYPESCRIPT, "tsx": Language.TYPESCRIPT, "mts": Language.TYPESCRIPT, "cts": Language.TYPESCRIPT}
        for extension in extensions:
            self.write(f"example.{extension}")
            self.write(f"UPPER.{extension.upper()}")
        for item in scan_repository(self.root).files:
            with self.subTest(path=item.path):
                self.assertEqual(item.language, extensions[item.path.rsplit(".", 1)[1].lower()])
        self.assertIn("UPPER.PY", [f.path for f in scan_repository(self.root).files])

    def test_unsupported_files_remain_visible(self):
        for name in ("README.md", "package.json", "Dockerfile", "diagram.png"):
            self.write(name)
        result = scan_repository(self.root)
        self.assertEqual(result.file_count, 4)
        self.assertEqual(result.supported_files, ())

    def test_default_exclusions_prune_before_descent_at_every_level(self):
        expected = {".git", "node_modules", ".venv", "venv", "env", "__pycache__", "dist",
            "build", "coverage", ".coverage", ".next", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".cache", "vendor"}
        self.assertEqual(DEFAULT_EXCLUDED_DIRECTORIES, frozenset(expected))
        for name in expected:
            self.write(f"{name}/dependency.py")
            self.write(f"nested/{name}/dependency.py")
        real_scandir = os.scandir
        def guarded(path):
            self.assertNotIn(Path(path).name, expected, "excluded directory was entered")
            return real_scandir(path)
        with patch("arctrellis.ingestion.discovery.os.scandir", side_effect=guarded):
            result = scan_repository(self.root)
        self.assertEqual(result.files, ())
        self.assertEqual(len(result.skipped_paths), 2 * len(expected))
        self.assertTrue(all(s.reason == SkipReason.EXCLUDED_DIRECTORY for s in result.skipped_paths))

    def test_hidden_directories_gitignored_files_and_excluded_name_files_remain(self):
        self.write(".github/workflows/check.yml")
        self.write(".gitignore", "ignored.py\n")
        self.write("ignored.py")
        self.write(".coverage")
        self.assertEqual([f.path for f in scan_repository(self.root).files],
            [".coverage", ".github/workflows/check.yml", ".gitignore", "ignored.py"])

    def test_custom_exclusions_replace_defaults_and_names_are_case_sensitive(self):
        self.write("custom/a.py")
        self.write("node_modules/b.js")
        self.write("DIST/c.py")
        self.assertEqual([f.path for f in scan_repository(self.root, excluded_directories={"custom"}).files],
            ["DIST/c.py", "node_modules/b.js"])
        self.assertEqual(scan_repository(self.root, excluded_directories=frozenset()).file_count, 3)

    def test_invalid_exclusions_are_rejected(self):
        for names in ({"../src"}, {""}, {"a/b"}, {"a\\b"}, {"."}):
            with self.subTest(names=names), self.assertRaises(ValueError):
                scan_repository(self.root, excluded_directories=names)
        with self.assertRaises(TypeError):
            scan_repository(self.root, excluded_directories="dist")

    def test_creation_order_and_repeated_scans_are_equal(self):
        names = ("z.py", "src/b.ts", "a.js", "README.md")
        for name in names:
            self.write(name)
        first = scan_repository(self.root)
        self.assertEqual(first, scan_repository(self.root))
        with TemporaryDirectory() as other:
            for name in reversed(names):
                target = Path(other) / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("x", encoding="utf-8")
            self.assertEqual(first, scan_repository(other))

    def test_invalid_roots_fail_explicitly(self):
        target = self.write("a.py")
        for root in (self.root / "missing", target, "", "bad\x00root"):
            with self.subTest(root=root), self.assertRaises(InvalidRepositoryPathError):
                scan_repository(root)
        with self.assertRaises(TypeError):
            scan_repository(42)

    def test_access_failure_preserves_original_cause(self):
        with patch("arctrellis.ingestion.discovery.os.scandir", side_effect=PermissionError("denied")):
            with self.assertRaises(RepositoryAccessError) as caught:
                scan_repository(self.root)
        self.assertIsInstance(caught.exception.__cause__, PermissionError)

    def test_nested_failure_never_returns_partial_inventory(self):
        self.write("a.py")
        self.write("src/b.py")
        real_scandir = os.scandir
        def failing(path):
            if Path(path).name == "src":
                raise PermissionError("nested denied")
            return real_scandir(path)
        with patch("arctrellis.ingestion.discovery.os.scandir", side_effect=failing):
            with self.assertRaises(RepositoryAccessError):
                scan_repository(self.root)

    def test_source_is_neither_read_nor_executed(self):
        self.write("malicious.py", "from pathlib import Path\nPath(__file__).with_name('executed').touch()")
        self.write("setup.py", "raise RuntimeError('must never run')")
        with patch("builtins.open", side_effect=AssertionError("content read")), patch("io.open", side_effect=AssertionError("content read")):
            result = scan_repository(self.root)
        self.assertEqual(result.file_count, 2)
        self.assertFalse((self.root / "executed").exists())
        self.assertFalse((self.root / "__pycache__").exists())
