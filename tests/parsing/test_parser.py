import os
import stat
import subprocess
import sys
import unittest
from dataclasses import fields, is_dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from arctrellis.ingestion import DiscoveredFile, Language, scan_repository
from arctrellis.parsing import (
    DiagnosticKind,
    ParsedSource,
    ParserConfigurationError,
    ParserExecutionError,
    SourceReadError,
    SourceTooLargeError,
    SyntaxSpan,
    UnsafeSourceError,
    UnsupportedLanguageError,
    parse_discovered_file,
    parse_source,
)


class ParserTests(unittest.TestCase):
    def test_representative_python_syntax(self):
        source = (
            b"import os\n@decorate\nasync def work(x):\n    return x\nclass Service"
            b":\n    def create(self):\n        pass\n"
        )
        result = parse_source("a.py", Language.PYTHON, source)
        kinds = {node.kind for node in result.root.walk()}
        self.assertTrue(
            {"import_statement", "decorated_definition", "function_definition", "class_definition"} <= kinds
        )
        self.assertFalse(result.has_errors)

    def test_representative_javascript_and_jsx(self):
        source = (
            b"import x from 'x'; export async function f() { return 1; } const "
            b"g = () => <div>Hello</div>; class C { m() {} }"
        )
        result = parse_source("a.jsx", Language.JAVASCRIPT, source)
        self.assertFalse(result.has_errors)
        kinds = {node.kind for node in result.root.walk()}
        self.assertTrue(
            {"function_declaration", "arrow_function", "class_declaration", "jsx_element", "import_statement"} <= kinds
        )

    def test_representative_typescript(self):
        result = parse_source(
            "a.ts",
            Language.TYPESCRIPT,
            (
                b"import {x} from 'x'; interface Payment { amount: number; } functi"
                b"on create(p: Payment): void {} class C { m(): void {} }"
            ),
        )
        self.assertFalse(result.has_errors)
        self.assertIn("interface_declaration", [node.kind for node in result.root.walk()])

    def test_tsx_uses_dedicated_grammar_and_keeps_canonical_language(self):
        result = parse_source(
            "Button.tsx",
            Language.TYPESCRIPT,
            (
                b"type Props = { label: string; }; export function Button({label}: "
                b"Props) { return <button>{label}</button>; }"
            ),
        )
        self.assertEqual(result.language, Language.TYPESCRIPT)
        self.assertFalse(result.has_errors)
        self.assertIn("jsx_element", [node.kind for node in result.root.walk()])

    def test_invalid_syntax_returns_diagnostics_for_all_languages(self):
        for path, language, source in (
            ("a.py", Language.PYTHON, b"def broken(\n return 1"),
            ("a.js", Language.JAVASCRIPT, b"function {"),
            ("a.ts", Language.TYPESCRIPT, b"interface {"),
        ):
            with self.subTest(path=path):
                result = parse_source(path, language, source)
                self.assertTrue(result.has_errors)
                self.assertTrue(result.diagnostics)
                self.assertTrue(any(n.is_error or n.is_missing for n in result.root.walk()))

    def test_anonymous_missing_token_is_preserved_and_diagnosed(self):
        result = parse_source("a.js", Language.JAVASCRIPT, b"function f() {")
        missing = next(n for n in result.root.walk() if n.is_missing)
        self.assertEqual(missing.kind, "}")
        self.assertFalse(missing.is_named)
        self.assertEqual(missing.span.start_byte, missing.span.end_byte)
        self.assertIn(DiagnosticKind.MISSING, [d.kind for d in result.diagnostics])

    def test_deep_native_tree_normalization_does_not_use_python_recursion(self):
        result = parse_source("a.js", Language.JAVASCRIPT, b"const x=" + b"[" * 1200 + b"0" + b"]" * 1200 + b";")
        self.assertGreater(sum(1 for _ in result.root.walk()), 1200)
        self.assertFalse(result.has_errors)

    def test_deep_repeated_parse_equality_and_hashing_do_not_recurse(self):
        source = b"const x=" + b"[" * 1200 + b"0" + b"]" * 1200 + b";"
        first = parse_source("a.js", Language.JAVASCRIPT, source)
        second = parse_source("a.js", Language.JAVASCRIPT, source)
        self.assertTrue(first == second)
        self.assertEqual(hash(first), hash(second))

    @unittest.skipUnless(os.name == "nt", "Windows path-component containment")
    def test_nested_drive_component_cannot_escape_root_or_trigger_io(self):
        with TemporaryDirectory() as temp:
            item = DiscoveredFile("src/D:/outside/a.py", 0, Language.PYTHON)
            with (
                patch("arctrellis.parsing.source.os.lstat") as metadata,
                patch("arctrellis.parsing.source.os.open") as opened,
            ):
                with self.assertRaises(UnsafeSourceError):
                    parse_discovered_file(temp, item)
                metadata.assert_not_called()
                opened.assert_not_called()

    def test_missing_native_runtime_becomes_typed_configuration_error(self):
        command = """import sys
from importlib.abc import MetaPathFinder
class BlockRuntime(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'tree_sitter':
            raise ImportError('runtime unavailable')
sys.meta_path.insert(0, BlockRuntime())
from arctrellis.parsing import parse_source, ParserConfigurationError
from arctrellis.ingestion import Language
try:
    parse_source('a.py', Language.PYTHON, b'x')
except ParserConfigurationError:
    pass
else:
    raise AssertionError('missing typed failure')
"""
        result = subprocess.run([sys.executable, "-c", command], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_empty_and_undecodable_bytes_are_retained_without_decoding(self):
        for source in (b"", b"x='\xff'\n"):
            self.assertEqual(parse_source("a.py", Language.PYTHON, source).source, source)

    def test_invalid_limit_and_mutable_source_inputs_are_rejected(self):
        for limit in (True, 1.5):
            with self.assertRaises(TypeError):
                parse_source("a.py", Language.PYTHON, b"", max_source_bytes=limit)
        for limit in (0, -1):
            with self.assertRaises(ValueError):
                parse_source("a.py", Language.PYTHON, b"", max_source_bytes=limit)
        with self.assertRaises(TypeError):
            parse_source("a.py", Language.PYTHON, bytearray(b"x"))

    def test_configuration_and_execution_failures_are_typed(self):
        with patch("arctrellis.parsing.registry.import_module", side_effect=ImportError("grammar unavailable")):
            with self.assertRaises(ParserConfigurationError) as caught:
                parse_source("a.py", Language.PYTHON, b"x")
            self.assertIsInstance(caught.exception.__cause__, ImportError)
        with patch("arctrellis.parsing.parser._new_parser") as factory:
            factory.return_value.parse.side_effect = RuntimeError("native failure")
            with self.assertRaises(ParserExecutionError) as caught:
                parse_source("a.py", Language.PYTHON, b"x")
            self.assertIsInstance(caught.exception.__cause__, RuntimeError)

    def test_other_public_packages_do_not_load_native_parser(self):
        command = (
            "import sys; import arctrellis.core, arctrellis.graph, arctrellis."
            "ingestion; assert not any(n.startswith('tree_sitter') for n in sy"
            "s.modules)"
        )
        result = subprocess.run([sys.executable, "-c", command], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_named_nodes_fields_exact_bytes_and_unicode_columns(self):
        source = "def work():\n    return 'é'\n".encode()
        result = parse_source("a.py", Language.PYTHON, source)
        function = result.root.children[0]
        name = function.child_by_field("name")
        self.assertEqual(result.bytes_for(name), b"work")
        self.assertEqual(name.span, SyntaxSpan(4, 8, 1, 4, 1, 8))
        string = next(n for n in result.root.walk() if n.kind == "string")
        self.assertEqual(string.span.end_column - string.span.start_column, 4)
        self.assertEqual(result.source, source)
        self.assertTrue(all(n.is_named or n.is_error or n.is_missing for n in result.root.walk()))
        self.assertNotIn("(", [n.kind for n in result.root.walk()])

    def test_repeat_parsing_is_equal_and_normalized_fields_are_owned_values(self):
        result = parse_source("a.py", Language.PYTHON, b"x=1\n")
        self.assertEqual(result, parse_source("a.py", Language.PYTHON, b"x=1\n"))
        pending = [result]
        while pending:
            value = pending.pop()
            self.assertFalse(type(value).__module__.startswith("tree_sitter"))
            if is_dataclass(value):
                pending.extend(getattr(value, field.name) for field in fields(value))
            elif isinstance(value, tuple):
                pending.extend(value)

    def test_size_limit_is_inclusive_and_never_truncates(self):
        self.assertEqual(parse_source("a.py", Language.PYTHON, b"x=1", max_source_bytes=3).source, b"x=1")
        with self.assertRaises(SourceTooLargeError):
            parse_source("a.py", Language.PYTHON, b"x=1", max_source_bytes=2)

    def test_scan_to_parse_pipeline_reads_bytes_without_execution(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            source = b"from pathlib import Path\nPath(__file__).with_name('executed').touch()\n"
            (root / "src/payment.py").write_bytes(source)
            item = scan_repository(root).supported_files[0]
            result = parse_discovered_file(root, item)
            self.assertIsInstance(result, ParsedSource)
            self.assertEqual(result.source, source)
            self.assertFalse((root / "src/executed").exists())
            self.assertFalse((root / "src/__pycache__").exists())

    def test_unsupported_inventory_file_is_rejected(self):
        with TemporaryDirectory() as temp:
            (Path(temp) / "README.md").touch()
            with self.assertRaises(UnsupportedLanguageError):
                parse_discovered_file(temp, scan_repository(temp).files[0])

    def test_deleted_or_directory_source_is_rejected(self):
        with TemporaryDirectory() as temp:
            target = Path(temp) / "a.py"
            target.write_bytes(b"x=1")
            item = scan_repository(temp).supported_files[0]
            target.unlink()
            with self.assertRaises(SourceReadError) as caught:
                parse_discovered_file(temp, item)
            self.assertIsInstance(caught.exception.__cause__, FileNotFoundError)
            target.mkdir()
            with self.assertRaises(SourceReadError):
                parse_discovered_file(temp, item)

    def test_current_file_size_not_stale_inventory_is_enforced(self):
        with TemporaryDirectory() as temp:
            target = Path(temp) / "a.py"
            target.write_bytes(b"x")
            item = scan_repository(temp).supported_files[0]
            target.write_bytes(b"x=1")
            with self.assertRaises(SourceTooLargeError):
                parse_discovered_file(temp, item, max_source_bytes=2)

    def test_discovered_source_exact_limit_is_allowed(self):
        with TemporaryDirectory() as temp:
            (Path(temp) / "a.py").write_bytes(b"x=1")
            result = parse_discovered_file(temp, scan_repository(temp).supported_files[0], max_source_bytes=3)
            self.assertEqual(result.source, b"x=1")

    def test_read_failure_preserves_os_error(self):
        with TemporaryDirectory() as temp:
            (Path(temp) / "a.py").write_bytes(b"x=1")
            item = scan_repository(temp).supported_files[0]
            with (
                patch("arctrellis.parsing.source.os.read", side_effect=PermissionError("read denied")),
                self.assertRaises(SourceReadError) as caught,
            ):
                parse_discovered_file(temp, item)
            self.assertIsInstance(caught.exception.__cause__, PermissionError)

    def test_growth_past_limit_during_read_is_rejected_before_parsing(self):
        with TemporaryDirectory() as temp:
            (Path(temp) / "a.py").write_bytes(b"x")
            item = scan_repository(temp).supported_files[0]
            with (
                patch("arctrellis.parsing.source.os.read", return_value=b"xxxx"),
                patch("arctrellis.parsing.parser._new_parser") as factory,
            ):
                with self.assertRaises(SourceTooLargeError):
                    parse_discovered_file(temp, item, max_source_bytes=3)
                factory.assert_not_called()

    def test_descriptor_identity_change_aborts_and_closes_descriptor(self):
        with TemporaryDirectory() as temp:
            (Path(temp) / "a.py").write_bytes(b"x")
            item = scan_repository(temp).supported_files[0]
            real_fstat, real_close = os.fstat, os.close

            def changed_identity(descriptor):
                info = real_fstat(descriptor)
                return SimpleNamespace(st_mode=info.st_mode, st_dev=info.st_dev, st_ino=info.st_ino + 1)

            with (
                patch("arctrellis.parsing.source.os.fstat", side_effect=changed_identity),
                patch("arctrellis.parsing.source.os.close", wraps=real_close) as closed,
            ):
                with self.assertRaises(SourceReadError):
                    parse_discovered_file(temp, item)
                closed.assert_called_once()

    def test_mtime_change_during_read_aborts(self):
        with TemporaryDirectory() as temp:
            (Path(temp) / "a.py").write_bytes(b"x")
            item = scan_repository(temp).supported_files[0]
            real_fstat = os.fstat
            calls = 0

            def changed_mtime(descriptor):
                nonlocal calls
                calls += 1
                info = real_fstat(descriptor)
                if calls == 1:
                    return info
                return SimpleNamespace(st_size=info.st_size, st_mtime_ns=info.st_mtime_ns + 1)

            with (
                patch("arctrellis.parsing.source.os.fstat", side_effect=changed_mtime),
                self.assertRaises(SourceReadError),
            ):
                parse_discovered_file(temp, item)

    def test_observed_link_or_reparse_metadata_is_refused_before_open(self):
        from arctrellis.parsing.source import _ordinary

        for info in (
            SimpleNamespace(st_mode=stat.S_IFLNK),
            SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT),
        ):
            with self.subTest(info=info), self.assertRaises(UnsafeSourceError):
                _ordinary(info, Path("a.py"), False)

    @unittest.skipUnless(os.name == "nt", "Windows junction fixture")
    def test_source_parent_replaced_with_junction_is_refused(self):
        with TemporaryDirectory() as temp, TemporaryDirectory() as outside:
            root = Path(temp)
            parent = root / "src"
            parent.mkdir()
            (parent / "a.py").write_bytes(b"x=1")
            item = scan_repository(root).supported_files[0]
            (parent / "a.py").unlink()
            parent.rmdir()
            (Path(outside) / "a.py").write_bytes(b"x=2")
            made = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(parent), outside],
                capture_output=True,
                text=True,
                check=False,
            )
            if made.returncode:
                self.skipTest(f"junction creation unavailable: {made.stderr}")
            try:
                with self.assertRaises(UnsafeSourceError):
                    parse_discovered_file(root, item)
            finally:
                os.rmdir(parent)

    def test_file_replaced_with_symlink_is_refused(self):
        with TemporaryDirectory() as temp:
            target = Path(temp) / "a.py"
            target.write_bytes(b"x=1")
            item = scan_repository(temp).supported_files[0]
            other = Path(temp) / "other.py"
            other.write_bytes(b"x=2")
            target.unlink()
            try:
                target.symlink_to(other)
            except OSError as error:
                self.skipTest(f"symlink creation unavailable: {error}")
            with self.assertRaises(SourceReadError):
                parse_discovered_file(temp, item)
