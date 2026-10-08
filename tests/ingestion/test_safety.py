"""Link, reparse-point and incomplete-scan boundaries."""

import os
from pathlib import Path
import stat
import subprocess
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from arctrellis.ingestion import InvalidRepositoryPathError, RepositoryAccessError, SkipReason, scan_repository
from arctrellis.ingestion import discovery


class DiscoverySafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def symlink(self, name, target, directory=False):
        link = self.root / name
        try:
            link.symlink_to(target, target_is_directory=directory)
        except OSError as error:
            self.skipTest(f"symbolic link creation unavailable: {error}")
        self.addCleanup(link.unlink)
        return link

    def test_file_link_is_skipped_not_read(self):
        target = self.root / "original.py"
        target.write_text("x", encoding="utf-8")
        self.symlink("linked.py", target)
        result = scan_repository(self.root, excluded_directories=set())
        self.assertEqual([f.path for f in result.files], ["original.py"])
        self.assertEqual([(s.path, s.reason) for s in result.skipped_paths], [("linked.py", SkipReason.SYMBOLIC_LINK)])

    def test_external_directory_link_is_not_traversed(self):
        with TemporaryDirectory() as outside:
            (Path(outside) / "secret.py").write_text("x", encoding="utf-8")
            self.symlink("external", outside, True)
            result = scan_repository(self.root)
            self.assertEqual(result.files, ())
            self.assertEqual(result.skipped_paths[0].reason, SkipReason.SYMBOLIC_LINK)

    def test_symlink_cycle_terminates(self):
        self.symlink("cycle", self.root, True)
        result = scan_repository(self.root)
        self.assertEqual(result.files, ())
        self.assertEqual(result.skipped_paths[0].path, "cycle")

    def test_broken_link_is_reported_without_resolving(self):
        self.symlink("broken", self.root / "missing")
        self.assertEqual(scan_repository(self.root).skipped_paths[0].reason, SkipReason.SYMBOLIC_LINK)

    def test_linked_root_and_linked_root_ancestor_are_rejected(self):
        target = self.root / "ordinary"
        (target / "nested").mkdir(parents=True)
        link = self.symlink("indirect", target, True)
        for root in (link, link / "nested"):
            with self.subTest(root=root), self.assertRaises(InvalidRepositoryPathError):
                scan_repository(root)

    @unittest.skipUnless(os.name == "nt", "Windows junction fixture")
    def test_windows_junction_is_skipped_and_rejected_as_root(self):
        with TemporaryDirectory() as outside:
            (Path(outside) / "secret.py").write_text("x", encoding="utf-8")
            link = self.root / "junction"
            # Native filesystem fixture creation only; no target scripts execute.
            result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), outside],
                                    capture_output=True, text=True, check=False)
            if result.returncode:
                self.skipTest(f"junction creation unavailable: {result.stderr.strip()}")
            try:
                self.assertTrue(link.is_junction())
                inventory = scan_repository(self.root)
                self.assertEqual(inventory.files, ())
                self.assertEqual([(s.path, s.reason) for s in inventory.skipped_paths], [("junction", SkipReason.JUNCTION)])
                for root in (link, link / "nested"):
                    with self.subTest(root=root), self.assertRaises(InvalidRepositoryPathError):
                        scan_repository(root)
            finally:
                os.rmdir(link)
            self.assertTrue((Path(outside) / "secret.py").exists())

    def test_simulated_other_reparse_point_is_skipped(self):
        metadata = SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,
                                   st_reparse_tag=123)
        entry = SimpleNamespace(name="indirect", stat=lambda **kwargs: metadata)
        with patch("arctrellis.ingestion.discovery.os.scandir") as mocked:
            mocked.return_value.__enter__.return_value = iter((entry,))
            result = scan_repository(self.root)
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(result.skipped_paths[0].reason, SkipReason.REPARSE_POINT)

    def test_simulated_symbolic_link_metadata_never_descends(self):
        metadata = SimpleNamespace(st_mode=stat.S_IFLNK)
        entry = SimpleNamespace(name="cycle", stat=lambda **kwargs: metadata)
        with patch("arctrellis.ingestion.discovery.os.scandir") as mocked:
            mocked.return_value.__enter__.return_value = iter((entry,))
            result = scan_repository(self.root, excluded_directories=set())
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(result.files, ())
        self.assertEqual(result.skipped_paths[0].reason, SkipReason.SYMBOLIC_LINK)

    def test_simulated_nonregular_object_is_skipped(self):
        metadata = SimpleNamespace(st_mode=stat.S_IFIFO)
        entry = SimpleNamespace(name="pipe", stat=lambda **kwargs: metadata)
        with patch("arctrellis.ingestion.discovery.os.scandir") as mocked:
            mocked.return_value.__enter__.return_value = iter((entry,))
            result = scan_repository(self.root)
        self.assertEqual(result.files, ())
        self.assertEqual(result.skipped_paths[0].reason, SkipReason.NON_REGULAR_FILE)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "named pipes cannot be created with os.mkfifo on this platform")
    def test_named_pipe_is_skipped_without_opening(self):
        os.mkfifo(self.root / "pipe")
        result = scan_repository(self.root)
        self.assertEqual(result.files, ())
        self.assertEqual(result.skipped_paths[0].reason, SkipReason.NON_REGULAR_FILE)

    def test_entry_stat_failure_aborts_scan(self):
        entry = SimpleNamespace(name="a.py")
        def fail(**kwargs):
            self.assertFalse(kwargs["follow_symlinks"])
            raise FileNotFoundError("entry vanished")
        entry.stat = fail
        with patch("arctrellis.ingestion.discovery.os.scandir") as mocked:
            mocked.return_value.__enter__.return_value = iter((entry,))
            with self.assertRaises(RepositoryAccessError) as caught:
                scan_repository(self.root)
        self.assertIsInstance(caught.exception.__cause__, FileNotFoundError)

    def test_enumeration_failure_after_a_file_aborts_scan(self):
        target = self.root / "a.py"
        target.write_text("x", encoding="utf-8")
        with os.scandir(self.root) as entries:
            entry = next(entries)
        def failing_iterator():
            yield entry
            raise PermissionError("iteration denied")
        with patch("arctrellis.ingestion.discovery.os.scandir") as mocked:
            mocked.return_value.__enter__.return_value = failing_iterator()
            with self.assertRaises(RepositoryAccessError) as caught:
                scan_repository(self.root)
        self.assertIsInstance(caught.exception.__cause__, PermissionError)

    def test_root_metadata_access_failure_is_not_invalid_or_empty(self):
        with patch("arctrellis.ingestion.discovery.os.lstat", side_effect=PermissionError("root denied")):
            with self.assertRaises(RepositoryAccessError) as caught:
                scan_repository(self.root)
        self.assertIsInstance(caught.exception.__cause__, PermissionError)

    def test_directory_replacement_is_detected_before_descent(self):
        expected = os.lstat(self.root)
        replacement = SimpleNamespace(st_mode=stat.S_IFDIR, st_dev=expected.st_dev, st_ino=expected.st_ino + 1)
        with patch("arctrellis.ingestion.discovery.os.lstat", return_value=replacement):
            with self.assertRaises(RepositoryAccessError):
                discovery._check_directory(self.root, expected)

    def test_replacement_with_link_fails_even_with_matching_identity(self):
        expected = os.lstat(self.root)
        replacement = SimpleNamespace(st_mode=stat.S_IFLNK, st_dev=expected.st_dev, st_ino=expected.st_ino)
        with patch("arctrellis.ingestion.discovery.os.lstat", return_value=replacement):
            with self.assertRaises(RepositoryAccessError):
                discovery._check_directory(self.root, expected)
