import subprocess
import sys
import unittest
from dataclasses import fields, is_dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory

from arctrellis.core import SourceLocation
from arctrellis.indexing import FileIndexStatus, index_repository
from arctrellis.parsing import ParsedSource, SyntaxNode, SyntaxSpan


def index_sources(sources):
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for path, source in sources.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.encode() if isinstance(source, str) else source)
        return index_repository(root)


class IndexingTests(unittest.TestCase):
    def test_escaped_script_callees_are_omitted_without_aborting_index(self):
        for path in ("a.js", "a.ts"):
            result = index_sources({path: r"function f() {} \u0066();"})
            self.assertTrue(result.is_complete)
            self.assertEqual(result.call_sites, ())

    def test_target_source_is_not_executed(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "executed"
            (root / "target.py").write_text(
                "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('unsafe')\n", encoding="utf-8"
            )
            result = index_repository(root)
            self.assertTrue(result.is_complete)
            self.assertFalse(marker.exists())

    def test_public_packages_import_in_fresh_process_in_any_order(self):
        for first in ("indexing", "resolution", "calls"):
            command = (
                f"import arctrellis.{first}; from arctrellis.calls import resolve_calls; "
                "from arctrellis.indexing import index_repository"
            )
            completed = subprocess.run([sys.executable, "-c", command], capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_mixed_observations_counts_and_order_without_syntax_retention(self):
        sources = {
            "a.py": "def run():\n    helper()\n",
            "b.js": "const run = () => helper();",
            "c.ts": "function run(): void { helper(); }",
        }
        a, b = index_sources(sources), index_sources(sources)
        self.assertEqual(a.call_sites, b.call_sites)
        self.assertEqual([s.path for s in a.call_sites], ["a.py", "b.js", "c.ts"])
        self.assertEqual([f.call_site_count for f in a.file_results], [1, 1, 1])
        self.assertEqual((a.entity_count, a.relationship_count, a.call_site_count), (9, 6, 3))
        pending = [a.call_sites, a.file_results, a.inventory, a.graph.entities(), a.graph.relationships()]
        while pending:
            value = pending.pop()
            self.assertNotIsInstance(value, (ParsedSource, SyntaxNode, bytes, BaseException))
            if is_dataclass(value):
                pending.extend(getattr(value, f.name) for f in fields(value))
            elif isinstance(value, tuple):
                pending.extend(value)

    def test_partial_failed_counts_and_owner_validation(self):
        result = index_sources({"a.py": "def good():\n    helper()\ndef broken(\n", "b.js": b"// \xff"})
        self.assertEqual([f.status for f in result.file_results], [FileIndexStatus.PARTIAL, FileIndexStatus.FAILED])
        self.assertEqual([f.call_site_count for f in result.file_results], [1, 0])
        self.assertEqual(result.call_site_count, 1)
        with self.assertRaises(ValueError):
            replace(result, call_sites=())
        with self.assertRaises(ValueError):
            replace(result, call_sites=(replace(result.call_sites[0], owner_entity_id="missing"),))
        with self.assertRaises(ValueError):
            replace(
                result,
                call_sites=(
                    replace(
                        result.call_sites[0],
                        span=SyntaxSpan(900, 905, 90, 0, 90, 5),
                        location=SourceLocation("a.py", 90, 90),
                    ),
                ),
            )
