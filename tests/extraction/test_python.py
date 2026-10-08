import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from arctrellis.core import EntityKind
from arctrellis.extraction import (
    SemanticExtractionError,
    SourceDecodingError,
    UnsupportedExtractionLanguageError,
    extract_python_entities,
)
from arctrellis.ingestion import Language, scan_repository
from arctrellis.parsing import SyntaxNode, parse_discovered_file, parse_source


class PythonExtractionTests(unittest.TestCase):
    def extract(self, source, path="src/a.py"):
        raw = source.encode() if isinstance(source, str) else source
        return extract_python_entities(parse_source(path, Language.PYTHON, raw))

    def test_empty_module_has_path_identity_and_inclusive_location(self):
        result = self.extract(b"")
        self.assertFalse(result.partial)
        self.assertEqual(len(result.entities), 1)
        module = result.module
        self.assertEqual((module.name, module.qualified_name, module.parent_id), ("a", "src/a.py", None))
        self.assertEqual((module.location.start_line, module.location.end_line), (1, 1))
        self.assertEqual(module.language, "python")

    def test_function_signature_location_and_module_parent(self):
        result = self.extract("def create_payment(amount: int) -> bool:\n    return True\n")
        function = result.entities[1]
        self.assertEqual(function.kind, EntityKind.FUNCTION)
        self.assertEqual(function.name, "create_payment")
        self.assertEqual(function.qualified_name, "src/a.py::create_payment")
        self.assertEqual(function.parent_id, result.module.id)
        self.assertEqual(function.signature, "def create_payment(amount: int) -> bool")
        self.assertEqual((function.location.start_line, function.location.end_line), (1, 2))
        self.assertEqual(dict(function.metadata)["start_byte"], "0")

    def test_nearest_scope_handles_classes_methods_functions_and_control_flow(self):
        source = """class Outer:
    class Inner:
        if True:
            async def run(self):
                def validate():
                    pass
                from pathlib import Path
    import platform
def outer():
    if True:
        def inner():
            import secrets
"""
        result = self.extract(source)
        named = {entity.name: entity for entity in result.entities}
        for name, kind, parent in (
            ("Outer", EntityKind.CLASS, "a"),
            ("Inner", EntityKind.CLASS, "Outer"),
            ("run", EntityKind.METHOD, "Inner"),
            ("validate", EntityKind.FUNCTION, "run"),
            ("Path", EntityKind.IMPORT, "run"),
            ("platform", EntityKind.IMPORT, "Outer"),
            ("outer", EntityKind.FUNCTION, "a"),
            ("inner", EntityKind.FUNCTION, "outer"),
            ("secrets", EntityKind.IMPORT, "inner"),
        ):
            with self.subTest(name=name):
                self.assertEqual(named[name].kind, kind)
                self.assertEqual(named[name].parent_id, named[parent].id)
        self.assertEqual(named["validate"].qualified_name, "src/a.py::Outer.Inner.run.validate")
        self.assertEqual(dict(named["run"].metadata)["is_async"], "true")

    def test_async_module_function_and_descriptor_decorators_remain_lexical(self):
        result = self.extract(
            "async def fetch():\n    pass\nclass C:\n    @staticmethod\n    def s("
            "): pass\n    @property\n    def p(self): pass\n"
        )
        self.assertEqual(dict(result.entities[1].metadata)["is_async"], "true")
        self.assertEqual([e.kind for e in result.entities[3:]], [EntityKind.METHOD, EntityKind.METHOD])

    def test_decorated_definitions_have_one_entity_wrapper_span_and_numbered_decorators(self):
        result = self.extract(
            '@router.post("/payments")\n@audit\ndef create():\n    pass\n@dataclas'
            "s\nclass Payment:\n    amount: int\n    @classmethod\n    def make(cl"
            "s): pass\n"
        )
        self.assertEqual(
            [e.kind for e in result.entities],
            [EntityKind.MODULE, EntityKind.FUNCTION, EntityKind.CLASS, EntityKind.METHOD],
        )
        function, cls, method = result.entities[1:]
        self.assertEqual(function.location.start_line, 1)
        self.assertEqual(function.signature, "def create()")
        self.assertEqual(dict(function.metadata)["decorator.0"], '@router.post("/payments")')
        self.assertEqual(dict(function.metadata)["decorator.1"], "@audit")
        self.assertEqual(cls.location.start_line, 5)
        self.assertEqual(method.location.start_line, 8)
        self.assertEqual(dict(method.metadata)["decorator.0"], "@classmethod")

    def test_multiline_signatures_annotations_inline_bodies_and_header_comments(self):
        source = (
            "def f(\n    x: dict[str, int],\n) -> str: # comment: retained outsi"
            'de signature\n    # another: comment\n    return "x"\nclass C(Base, '
            "Other): pass\n"
        )
        result = self.extract(source)
        self.assertEqual(result.entities[1].signature, "def f(\n    x: dict[str, int],\n) -> str")
        self.assertEqual(result.entities[2].signature, "class C(Base, Other)")

    def test_duplicate_declarations_determinism_and_revision_movement(self):
        source = "def process(): pass\ndef process(): pass\n"
        result = self.extract(source)
        self.assertEqual(result, self.extract(source))
        self.assertEqual(result.entities[1].qualified_name, result.entities[2].qualified_name)
        self.assertNotEqual(result.entities[1].id, result.entities[2].id)
        self.assertNotEqual(result.entities[1].id, self.extract("\n" + source).entities[1].id)

    def test_utf8_bom_cookie_and_unicode_names(self):
        for source in (
            "def café(): pass\n".encode(),
            b"\xef\xbb\xbfdef f(): pass\n",
            b'# coding: latin-1\ndef f():\n    return "caf\xe9"\n',
        ):
            with self.subTest(source=source):
                result = self.extract(source)
                self.assertEqual(len(result.entities), 2)
        self.assertEqual(self.extract("def café(): pass\n").entities[1].name, "café")

    def test_decoding_failures_are_typed_and_chained(self):
        for source in (b"# coding: not-a-codec\ndef f(): pass\n", b"\xff"):
            with self.subTest(source=source), self.assertRaises(SourceDecodingError) as caught:
                self.extract(source)
            self.assertIsNotNone(caught.exception.__cause__)

    def test_malformed_declarations_are_skipped_but_unaffected_siblings_survive(self):
        result = self.extract("def good(): pass\ndef broken(\n    return 1\n")
        self.assertTrue(result.partial)
        self.assertEqual([e.name for e in result.entities], ["a", "good"])
        self.assertFalse(any(e.name in ("ERROR", "MISSING", "<unknown>") for e in result.entities))

    def test_recovery_in_declaration_body_skips_entire_semantic_subtree(self):
        result = self.extract("def bad():\n    x = (\ndef good(): pass\n")
        self.assertTrue(result.partial)
        self.assertFalse(any(e.name == "bad" for e in result.entities))

    def test_wrong_language_and_nonmodule_root_fail_explicitly(self):
        parsed = parse_source("a.js", Language.JAVASCRIPT, b"function f() {}")
        with self.assertRaises(UnsupportedExtractionLanguageError):
            extract_python_entities(parsed)
        parsed = parse_source("a.py", Language.PYTHON, b"x")
        with self.assertRaises(SemanticExtractionError):
            extract_python_entities(replace(parsed, root=parsed.root.children[0]))

    def test_lambda_return_annotation_keeps_internal_top_level_colons(self):
        result = self.extract("def f() -> lambda: int:\n    pass\ndef g() -> lambda x: x:\n    pass\n")
        self.assertEqual(result.entities[1].signature, "def f() -> lambda: int")
        self.assertEqual(result.entities[2].signature, "def g() -> lambda x: x")

    def test_signature_rows_use_only_newlines_not_unicode_separators_or_formfeeds(self):
        for source, expected in (
            ('def f(\n    x: "a\u2028b",\n): pass\n', 'def f(\n    x: "a\u2028b",\n)'),
            ("def f(\f\n    x,\n): pass\n", "def f(\f\n    x,\n)"),
        ):
            with self.subTest(source=source):
                self.assertEqual(self.extract(source).entities[1].signature, expected)

    def test_empty_suite_is_partial_even_without_parser_diagnostics(self):
        parsed = parse_source("a.py", Language.PYTHON, b"def f():\n")
        self.assertFalse(parsed.has_errors)
        result = extract_python_entities(parsed)
        self.assertTrue(result.partial)
        self.assertEqual(len(result.entities), 1)

    def test_missing_identifier_and_recovery_children_cannot_define_identity(self):
        parsed = parse_source("a.py", Language.PYTHON, b"def f(): pass")
        definition = parsed.root.children[0]
        without_name = replace(definition, children=tuple(c for c in definition.children if c.field_name != "name"))
        result = extract_python_entities(replace(parsed, root=replace(parsed.root, children=(without_name,))))
        self.assertTrue(result.partial)
        self.assertEqual(len(result.entities), 1)
        missing_name = replace(definition.children[0], is_missing=True)
        recovery = replace(definition, children=(missing_name, *definition.children[1:]))
        result = extract_python_entities(replace(parsed, root=replace(parsed.root, children=(recovery,))))
        self.assertTrue(result.partial)
        self.assertEqual(len(result.entities), 1)

    def test_non_utf8_identifier_is_partial_under_current_byte_parser(self):
        result = self.extract("# coding: latin-1\ndef café(): pass\n".encode("latin-1"))
        self.assertTrue(result.partial)
        self.assertEqual([e.kind for e in result.entities], [EntityKind.MODULE])

    def test_outputs_are_canonical_values_with_no_native_fields(self):
        import json
        from dataclasses import asdict

        from arctrellis.core import CodeEntity

        result = self.extract("import os\ndef f(): pass\n")
        self.assertTrue(all(type(e) is CodeEntity for e in result.entities))
        self.assertIn('"partial": false', json.dumps(asdict(result)))
        self.assertEqual(len({e.id for e in result.entities}), len(result.entities))

    def test_no_variables_lambdas_referenced_symbols_tests_or_routes_are_inferred(self):
        result = self.extract('x = lambda a: a\n@router.get("/")\ndef test_payment():\n    print(x)\n')
        self.assertEqual([e.kind for e in result.entities], [EntityKind.MODULE, EntityKind.FUNCTION])

    def test_deep_normalized_control_tree_uses_no_recursive_walk(self):
        parsed = parse_source("a.py", Language.PYTHON, b"def f(): pass")
        child = parsed.root.children[0]
        for _ in range(1200):
            child = SyntaxNode("if_statement", parsed.root.span, children=(child,))
        result = extract_python_entities(
            replace(parsed, root=SyntaxNode("module", parsed.root.span, children=(child,)))
        )
        self.assertEqual(len(result.entities), 2)

    def test_scan_parse_extract_pipeline_never_executes_target_and_entities_fit_graph(self):
        from arctrellis.graph import CodeGraph

        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "src/payments").mkdir(parents=True)
            marker = root / "executed"
            code = (
                f"import pathlib\npathlib.Path({str(marker)!r}).touch()\n"
                "class Service:\n    def create(self):\n        def helper(): pass\n"
            )
            (root / "src/payments/service.py").write_text(code, encoding="utf-8")
            item = scan_repository(root).supported_files[0]
            parsed = parse_discovered_file(root, item)
            with patch("builtins.open", side_effect=AssertionError("extraction must not open files")):
                result = extract_python_entities(parsed)
            self.assertFalse(marker.exists())
            self.assertEqual(
                [e.kind for e in result.entities],
                [EntityKind.MODULE, EntityKind.IMPORT, EntityKind.CLASS, EntityKind.METHOD, EntityKind.FUNCTION],
            )
            graph = CodeGraph()
            for entity in result.entities:
                graph.add_entity(entity)
            self.assertEqual(graph.entity_count, len(result.entities))
            self.assertEqual(graph.relationship_count, 0)
