"""Import-boundary audit of ArcTrellis itself, never target repositories."""

import ast
import unittest
from pathlib import Path


def _native_imports(text: str) -> tuple[str, ...]:
    imports = []
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return tuple(name for name in imports if name.startswith("tree_sitter"))


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
        source = Path(__file__).resolve().parents[1] / "src/arctrellis"
        for path in sorted(source.rglob("*.py")):
            if path.relative_to(source).parts[0] == "parsing":
                continue
            with self.subTest(path=path.relative_to(source).as_posix()):
                self.assertEqual(_native_imports(path.read_text(encoding="utf-8")), ())
