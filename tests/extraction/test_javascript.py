"""JS/TS canonical semantics, without runtime execution or resolution."""

import json
import unittest
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import arctrellis.extraction as extraction
from arctrellis.core import EntityKind as K
from arctrellis.ingestion import Language, scan_repository
from arctrellis.parsing import parse_discovered_file, parse_source


class JavaScriptExtractionTests(unittest.TestCase):
    def extract(self, text, language=Language.JAVASCRIPT, path=None):
        path = path or ("src/app.ts" if language is Language.TYPESCRIPT else "src/app.js")
        parsed = parse_source(path, language, text.encode("utf-8"))
        self.assertFalse(parsed.has_errors, parsed.diagnostics)
        return extraction.extract_entities(parsed)

    def test_public_apis_exist(self):
        for name in ("extract_entities", "extract_javascript_entities", "extract_typescript_entities"):
            self.assertTrue(callable(getattr(extraction, name, None)), name)

    def test_empty_modules_and_tsx(self):
        for language, path in [
            (Language.JAVASCRIPT, "src/a.js"),
            (Language.TYPESCRIPT, "src/a.ts"),
            (Language.TYPESCRIPT, "src/a.tsx"),
        ]:
            with self.subTest(path=path):
                r = self.extract("", language, path)
                self.assertEqual(len(r.entities), 1)
                self.assertEqual((r.module.name, r.module.qualified_name, r.module.parent_id), ("a", path, None))
                self.assertEqual(r.module.language, language.value)

    def test_declarations_async_generators_and_signatures(self):
        r = self.extract("function create(x) {} async function fetch() {} function* items() {}")
        create, fetch, items = r.entities_of_kind(K.FUNCTION)
        self.assertEqual(create.signature, "function create(x)")
        self.assertEqual(create.qualified_name, "src/app.js::create")
        self.assertEqual(create.parent_id, r.module.id)
        self.assertEqual(dict(fetch.metadata)["is_async"], "true")
        self.assertEqual(dict(items.metadata)["is_generator"], "true")

    def test_callable_bindings(self):
        r = self.extract("const create = (x) => x; let fetch = async x => x; const run = function internal() {};")
        self.assertEqual([e.name for e in r.entities[1:]], ["create", "fetch", "run"])
        self.assertTrue(all(e.kind is K.FUNCTION for e in r.entities[1:]))
        self.assertEqual(r.entities[1].signature, "create = (x) =>")
        self.assertEqual(dict(r.entities[2].metadata)["is_async"], "true")
        self.assertEqual(dict(r.entities[3].metadata)["declaration_form"], "callable_binding")

    def test_class_binding_and_nested_class(self):
        r = self.extract("const Outer = class Internal { run() { class Inner {} } };")
        outer, run, inner = r.entities[1:]
        self.assertEqual((outer.kind, outer.name), (K.CLASS, "Outer"))
        self.assertEqual((run.kind, run.parent_id), (K.METHOD, outer.id))
        self.assertEqual((inner.kind, inner.parent_id), (K.CLASS, run.id))

    def test_method_modifiers(self):
        r = self.extract(
            "class Service { constructor(x) {} async create() {} static run() "
            "{} get value() {} set value(x) {} *items() {} }"
        )
        methods = r.entities_of_kind(K.METHOD)
        self.assertEqual([e.name for e in methods], ["constructor", "create", "run", "value", "value", "items"])
        for entity, key in zip(
            methods, ["is_constructor", "is_async", "is_static", "is_getter", "is_setter", "is_generator"], strict=True
        ):
            self.assertEqual(dict(entity.metadata)[key], "true")
        self.assertNotEqual(methods[3].id, methods[4].id)

    def test_callable_class_fields(self):
        for language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            r = self.extract("class Service { create = () => {}; run = function () {}; }", language)
            self.assertEqual([e.kind for e in r.entities], [K.MODULE, K.CLASS, K.METHOD, K.METHOD])
            self.assertEqual(dict(r.entities[2].metadata)["declaration_form"], "callable_field")

    def test_static_callable_field_preserves_member_modifiers(self):
        r = self.extract("class C { static run = () => {}; }")
        self.assertEqual(dict(r.entities[2].metadata)["is_static"], "true")
        self.assertEqual(r.entities[2].signature, "static run = () =>")

    def test_export_modifier_scan_excludes_decorator_arguments(self):
        r = self.extract("@dec(default) export class C {}", Language.TYPESCRIPT)
        self.assertEqual(dict(r.entities[1].metadata)["is_default_export"], "false")

    def test_control_flow_and_nested_function_scope(self):
        r = self.extract(
            "function outer() { if (true) { function inner() {} } } class C { run() { function nested() {} } }"
        )
        outer, inner, cls, method, nested = r.entities[1:]
        self.assertEqual((inner.kind, inner.parent_id), (K.FUNCTION, outer.id))
        self.assertEqual((nested.kind, nested.parent_id), (K.FUNCTION, method.id))
        self.assertEqual(method.parent_id, cls.id)

    def test_duplicates_and_determinism(self):
        for language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            a = self.extract("function same() {} function same() {}", language)
            b = self.extract("function same() {} function same() {}", language)
            self.assertEqual(a, b)
            first, second = a.entities_of_kind(K.FUNCTION)
            self.assertEqual(first.qualified_name, second.qualified_name)
            self.assertNotEqual(first.id, second.id)

    def test_export_metadata(self):
        r = self.extract(
            "export function create() {} export default function named() {} export const arrow = () => {};"
        )
        self.assertEqual([e.name for e in r.entities[1:]], ["create", "named", "arrow"])
        for entity in r.entities[1:]:
            self.assertEqual(dict(entity.metadata)["is_exported"], "true")
        self.assertEqual(dict(r.entities[2].metadata)["is_default_export"], "true")

    def test_intentional_omissions_do_not_fabricate_scopes(self):
        r = self.extract(
            "const obj = { run() { function inside() {} } }; (() => { function"
            " hidden() {} })(); const {x} = factory(); export default function"
            " () {}"
        )
        self.assertEqual(len(r.entities), 1)
        self.assertFalse(r.partial)

    def test_object_methods_inside_class_static_blocks_are_not_class_methods(self):
        for language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            r = self.extract("class C { static { use({ run() { function hidden() {} } }); } }", language)
            self.assertEqual([e.kind for e in r.entities], [K.MODULE, K.CLASS])
            self.assertFalse(r.partial)

    def test_jsx_function(self):
        r = self.extract("function Button() { return <button>Hello</button>; }", path="src/app.jsx")
        self.assertEqual([e.name for e in r.entities[1:]], ["Button"])

    def test_typescript_signatures_and_syntax_only_types(self):
        r = self.extract(
            (
                "interface Payment { amount: number; } type ID = string; enum Mode"
                " { A } function create<T>(x: T): number { return 1; } class C ext"
                "ends Base implements API { run(x: string): number { return 1; } }"
            ),
            Language.TYPESCRIPT,
        )
        fn, cls, method = r.entities[1:]
        self.assertEqual(fn.signature, "function create<T>(x: T): number")
        self.assertEqual(cls.signature, "class C extends Base implements API")
        self.assertEqual(method.signature, "run(x: string): number")
        self.assertEqual([e.kind for e in r.entities], [K.MODULE, K.FUNCTION, K.CLASS, K.METHOD])

    def test_tsx(self):
        r = self.extract(
            "export function Button() { return <button>Hello</button>; }", Language.TYPESCRIPT, "src/Button.tsx"
        )
        self.assertEqual(r.entities[1].kind, K.FUNCTION)
        self.assertFalse(r.partial)

    def test_decorators_include_source_and_exclude_signature(self):
        r = self.extract(
            "@sealed\nexport class C {\n @logged\n static run() {}\n @audit field = () => {};\n}", Language.TYPESCRIPT
        )
        cls, method, field = r.entities[1:]
        self.assertEqual(cls.location.start_line, 1)
        self.assertEqual(method.location.start_line, 3)
        self.assertEqual(dict(cls.metadata)["decorator.0"], "@sealed")
        self.assertEqual(dict(method.metadata)["decorator.0"], "@logged")
        self.assertEqual(dict(field.metadata)["decorator.0"], "@audit")
        self.assertEqual(method.signature, "static run()")
        self.assertNotIn("@", field.signature)

    def test_partial_recovery_retains_unaffected_sibling(self):
        for language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            p = parse_source(
                "a.js" if language is Language.JAVASCRIPT else "a.ts",
                language,
                b"function good() {}\nfunction broken( {",
            )
            self.assertTrue(p.has_errors)
            r = extraction.extract_entities(p)
            self.assertTrue(r.partial)
            self.assertEqual([e.name for e in r.entities[1:]], ["good"])

    def test_wrong_language_and_strict_decoding(self):
        p = parse_source("a.py", Language.PYTHON, b"")
        for function in (extraction.extract_javascript_entities, extraction.extract_typescript_entities):
            with self.assertRaises(extraction.UnsupportedExtractionLanguageError):
                function(p)
        p = parse_source("a.js", Language.JAVASCRIPT, b"// \xff")
        with self.assertRaises(extraction.SourceDecodingError) as caught:
            extraction.extract_entities(p)
        self.assertIsInstance(caught.exception.__cause__, UnicodeError)

    def test_normalized_outputs_and_no_direct_native_imports(self):
        r = self.extract("function caf\u00e9() {}")
        self.assertEqual(r.entities[1].name, "caf\u00e9")
        json.dumps(asdict(r))
        for path in Path("src/arctrellis/extraction").glob("*.py"):
            self.assertNotRegex(path.read_text(), r"(?:from|import)\s+tree_sitter")

    def test_pipeline_no_execution_and_no_extractor_reads(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "executed.txt"
            source = (
                'require("fs").writeFileSync(' + json.dumps(str(marker)) + ', "executed"); '
                'function create() { throw new Error("do not execute"); }'
            )
            for path in ("a.js", "b.ts", "c.tsx"):
                (root / path).write_text(source, encoding="utf-8")
            for file in scan_repository(root).supported_files:
                p = parse_discovered_file(root, file)
                with patch("builtins.open", side_effect=AssertionError("no extraction I/O")):
                    r = extraction.extract_entities(p)
                self.assertEqual(r.entities[1].name, "create")
                self.assertFalse(marker.exists())


class JavaScriptImportTests(unittest.TestCase):
    extract = JavaScriptExtractionTests.extract

    def imports(self, text, language=Language.JAVASCRIPT):
        return self.extract(text, language).entities_of_kind(K.IMPORT)

    def test_es_binding_forms(self):
        cases = [
            ('import D from "m";', [("D", "default", "default")]),
            ('import { A, B as Bee } from "m";', [("A", "named", "A"), ("Bee", "named", "B")]),
            ('import * as ns from "m";', [("ns", "namespace", "*")]),
            ('import D, { A } from "m";', [("D", "default", "default"), ("A", "named", "A")]),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                entities = self.imports(text)
                self.assertEqual(
                    [(e.name, dict(e.metadata)["import_form"], dict(e.metadata)["imported_name"]) for e in entities],
                    expected,
                )
                self.assertTrue(all(dict(e.metadata)["module"] == "m" for e in entities))
                self.assertTrue(all(dict(e.metadata)["binding"] == e.name for e in entities))

    def test_side_effect_has_no_fake_binding(self):
        (e,) = self.imports('import "side-effect";')
        self.assertEqual(e.name, "side-effect")
        self.assertEqual(dict(e.metadata)["binding"], "")
        self.assertEqual(dict(e.metadata)["import_form"], "side_effect")

    def test_empty_named_import_is_a_complete_unbound_site(self):
        for language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            r = self.extract('import {} from "m";', language)
            self.assertFalse(r.partial)
            (e,) = r.entities_of_kind(K.IMPORT)
            self.assertEqual(dict(e.metadata)["binding"], "")
            self.assertEqual(dict(e.metadata)["module"], "m")

    def test_literal_spelling_remains_exact_without_escape_evaluation(self):
        (e,) = self.imports(r'import x from "a\u0062";')
        self.assertEqual(dict(e.metadata)["module"], r"a\u0062")
        self.assertEqual(dict(e.metadata)["module_literal"], r'"a\u0062"')

    def test_type_only_imports_and_keyword_binding(self):
        entities = self.imports(
            'import type D from "m"; import { type A, B as Bee, type as t } from "m";', Language.TYPESCRIPT
        )
        self.assertEqual([dict(e.metadata)["is_type_only"] for e in entities], ["true", "true", "false", "false"])

    def test_static_require_and_local_scope(self):
        r = self.extract('const express = require("express"); function run() { const svc = require("./service"); }')
        imports = r.entities_of_kind(K.IMPORT)
        self.assertEqual([e.name for e in imports], ["express", "svc"])
        self.assertEqual(dict(imports[1].metadata)["module"], "./service")
        self.assertEqual(imports[1].parent_id, r.entities_of_kind(K.FUNCTION)[0].id)
        self.assertEqual(dict(imports[0].metadata)["import_form"], "require")

    def test_dynamic_require_and_destructuring_omitted(self):
        r = self.extract('const a = require(variable); const { b } = require("m"); const c = require("m", "n");')
        self.assertEqual(r.entities_of_kind(K.IMPORT), ())
