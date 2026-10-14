"""Import-boundary audit of ArcTrellis itself, never target repositories."""

import ast
import unittest
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src/arctrellis"

#: Modules that would give ArcTrellis a way to reach a network, spawn a process or
#: deserialize an untrusted object. http.server is the deliberate exception: it is
#: the local read-only listener and it never makes an outbound connection.
FORBIDDEN_IMPORTS = (
    "subprocess",
    "socket",
    "ssl",
    "ctypes",
    "multiprocessing",
    "pickle",
    "shelve",
    "urllib.request",
    "urllib.error",
    "http.client",
    "ftplib",
    "smtplib",
    "telnetlib",
    "webbrowser",
)

FORBIDDEN_CALLS = ("eval", "exec", "compile", "__import__")


def _imports(text: str) -> tuple[str, ...]:
    imports = []
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return tuple(imports)


def _native_imports(text: str) -> tuple[str, ...]:
    return tuple(name for name in _imports(text) if name.startswith("tree_sitter"))


def _forbidden(text: str) -> tuple[str, ...]:
    found = {name for name in _imports(text) if name.split(".")[0] in FORBIDDEN_IMPORTS or name in FORBIDDEN_IMPORTS}
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            found.add(node.func.id)
    return tuple(sorted(found))


class ArchitectureTests(unittest.TestCase):
    def test_database_adapters_have_no_runtime_orm_imports(self):
        source = Path(__file__).resolve().parents[1] / "src/arctrellis/database"
        for path in sorted(source.glob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    modules = [node.module]
                with self.subTest(path=path.name, modules=modules):
                    self.assertFalse(any(name.split(".")[0] in ("sqlalchemy", "prisma") for name in modules))

    def test_import_audit_detects_native_modules_independent_of_formatting(self):
        self.assertEqual(_native_imports("import tree_sitter as native"), ("tree_sitter",))
        self.assertEqual(_native_imports("from tree_sitter_python import language"), ("tree_sitter_python",))
        self.assertEqual(_native_imports("from arctrellis.parsing import ParsedSource"), ())

    def test_native_imports_remain_inside_parsing(self):
        for path in sorted(SOURCE_ROOT.rglob("*.py")):
            if path.relative_to(SOURCE_ROOT).parts[0] == "parsing":
                continue
            with self.subTest(path=path.relative_to(SOURCE_ROOT).as_posix()):
                self.assertEqual(_native_imports(path.read_text(encoding="utf-8")), ())

    def test_no_network_process_or_dynamic_execution_primitive_is_reachable(self):
        for path in sorted(SOURCE_ROOT.rglob("*.py")):
            with self.subTest(path=path.relative_to(SOURCE_ROOT).as_posix()):
                self.assertEqual(
                    _forbidden(path.read_text(encoding="utf-8")),
                    (),
                    "ArcTrellis must not reach a network, spawn a process or evaluate code",
                )

    def test_only_the_local_api_module_binds_a_socket(self):
        listeners = [
            path.relative_to(SOURCE_ROOT).as_posix()
            for path in sorted(SOURCE_ROOT.rglob("*.py"))
            if any(name in _imports(path.read_text(encoding="utf-8")) for name in ("http.server", "socketserver"))
        ]
        self.assertEqual(sorted(listeners), ["api/app.py", "api/server.py"])
