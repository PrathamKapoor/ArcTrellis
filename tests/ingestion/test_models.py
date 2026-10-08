import json
import unittest
from dataclasses import FrozenInstanceError, asdict

from arctrellis.ingestion import DiscoveredFile, Language, RepositoryInventory, SkippedPath, SkipReason


class InventoryModelTests(unittest.TestCase):
    def test_valid_file_is_hashable_and_serializable(self):
        item = DiscoveredFile("src/app.py", 12, Language.PYTHON)
        self.assertEqual(json.loads(json.dumps(asdict(item)))["language"], "python")
        self.assertEqual(hash(item), hash(DiscoveredFile("src/app.py", 12, Language.PYTHON)))

    def test_invalid_paths_are_rejected(self):
        for path in (
            "",
            "/a.py",
            "C:/a.py",
            "C:a.py",
            "../a.py",
            "src/../a.py",
            "src\\a.py",
            "src//a.py",
            "./a.py",
            "a\x00.py",
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                DiscoveredFile(path, 0)

    def test_filename_spaces_are_preserved(self):
        self.assertEqual(DiscoveredFile(" spaced.py ", 0).path, " spaced.py ")

    def test_invalid_size_and_language_are_rejected(self):
        with self.assertRaises(ValueError):
            DiscoveredFile("a.py", -1)
        for size in (True, 1.5, "1"):
            with self.subTest(size=size), self.assertRaises(TypeError):
                DiscoveredFile("a.py", size)
        with self.assertRaises(TypeError):
            DiscoveredFile("a.py", 1, "python")

    def test_unsupported_files_and_empty_inventory(self):
        self.assertIsNone(DiscoveredFile("README.md", 0).language)
        self.assertEqual(RepositoryInventory().language_counts, ())

    def test_records_and_inventory_are_immutable(self):
        item = DiscoveredFile("a.py", 0)
        inventory = RepositoryInventory((item,))
        with self.assertRaises(FrozenInstanceError):
            item.size_bytes = 2
        with self.assertRaises(FrozenInstanceError):
            inventory.files = ()
        self.assertEqual(hash(inventory), hash(RepositoryInventory((item,))))

    def test_inventory_requires_sorted_unique_tuples(self):
        a, b = DiscoveredFile("a.py", 0), DiscoveredFile("b.py", 0)
        for files in ((b, a), (a, a)):
            with self.subTest(files=files), self.assertRaises(ValueError):
                RepositoryInventory(files)
        for files in ([a], ("a.py",)):
            with self.subTest(files=files), self.assertRaises(TypeError):
                RepositoryInventory(files)

    def test_supported_subset_counts_and_order(self):
        result = RepositoryInventory(
            (
                DiscoveredFile("README.md", 1),
                DiscoveredFile("a.py", 2, Language.PYTHON),
                DiscoveredFile("b.ts", 3, Language.TYPESCRIPT),
                DiscoveredFile("c.js", 4, Language.JAVASCRIPT),
                DiscoveredFile("d.py", 5, Language.PYTHON),
            )
        )
        self.assertEqual(result.file_count, 5)
        self.assertEqual(result.supported_file_count, 4)
        self.assertEqual(result.supported_files, result.files[1:])
        self.assertEqual(
            result.language_counts, ((Language.JAVASCRIPT, 1), (Language.PYTHON, 2), (Language.TYPESCRIPT, 1))
        )

    def test_skip_validation_order_and_overlap(self):
        skip = SkippedPath("vendor", SkipReason.EXCLUDED_DIRECTORY)
        self.assertEqual(RepositoryInventory(skipped_paths=(skip,)).skipped_paths, (skip,))
        with self.assertRaises(TypeError):
            SkippedPath("vendor", "excluded_directory")
        with self.assertRaises(ValueError):
            RepositoryInventory((DiscoveredFile("vendor", 0),), (skip,))
        with self.assertRaises(ValueError):
            RepositoryInventory(skipped_paths=(skip, skip))
