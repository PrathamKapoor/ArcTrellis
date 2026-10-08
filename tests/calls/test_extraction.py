import unittest
from dataclasses import replace

from arctrellis.calls import CallExtractionError, extract_call_sites
from arctrellis.extraction import extract_entities
from arctrellis.ingestion import Language
from arctrellis.parsing import SyntaxNode, parse_source


class ExtractionTests(unittest.TestCase):
    def test_destructuring_defaults_and_constructor_arguments_are_body_calls(self):
        for language, path in ((Language.JAVASCRIPT, "a.js"), (Language.TYPESCRIPT, "a.ts")):
            actual, _ = self.extract(
                "function f() { const {x = helper(), [key()]: y} = obj; new Service(helper()); }", language, path
            )
            self.assertEqual(actual, [("f", ("helper",)), ("f", ("key",)), ("f", ("helper",))])

    def test_deep_owned_syntax_traversal_is_iterative(self):
        parsed = parse_source("a.py", Language.PYTHON, b"run()")
        (child,) = parsed.root.children
        for _ in range(1100):
            child = SyntaxNode("block", child.span, children=(child,))
        parsed = replace(parsed, root=replace(parsed.root, children=(child,)))
        sites = extract_call_sites(parsed, extract_entities(parsed))
        self.assertEqual([s.callee_parts for s in sites], [("run",)])

    def test_comments_in_optional_gap_do_not_execute_or_change_owner(self):
        actual, _ = self.extract("function f() { helper /* ordinary comment */ (); }", Language.JAVASCRIPT, "a.js")
        self.assertEqual(actual, [("f", ("helper",))])

    def test_comment_and_type_literal_optional_spelling_is_not_optional_invocation(self):
        for language, path, source in (
            (Language.JAVASCRIPT, "a.js", "function f() { helper /* ?. */ (); helper?.(); }"),
            (Language.TYPESCRIPT, "a.ts", 'function f() { helper /* ?. */ (); helper<"?.">(); helper?.<"?.">(); }'),
        ):
            actual, _ = self.extract(source, language, path)
            self.assertEqual(actual, [("f", ("helper",))] * (1 if language is Language.JAVASCRIPT else 2))

    def test_exports_bound_classes_and_nested_class_owners(self):
        actual, _ = self.extract(
            "export default function f() { helper(); }\nconst S = class { run() { helper(); } };",
            Language.TYPESCRIPT,
            "a.ts",
        )
        self.assertEqual(actual, [("f", ("helper",)), ("run", ("helper",))])
        actual, _ = self.extract("def outer():\n    class S:\n        def run(self):\n            helper()\n")
        self.assertEqual(actual, [("run", ("helper",))])

    def extract(self, source, language=Language.PYTHON, path="a.py"):
        parsed = parse_source(path, language, source.encode())
        entities = extract_entities(parsed)
        sites = extract_call_sites(parsed, entities)
        self.assertEqual(sites, extract_call_sites(parsed, entities))
        by_id = {e.id: e for e in entities.entities}
        return [(by_id[s.owner_entity_id].name, s.callee_parts) for s in sites], sites

    def test_python_execution_bodies_and_nested_owners(self):
        source = """@deco(factory())
def outer(x=default(), y: annotation()=None) -> result():
    helper()
    def inner():
        util.save()
    if True:
        another()
class S(base()):
    value = factory()
    @decorate()
    def run(self, x=default()):
        self.validate()
        cls.create()
        service.repository.save()
outer()
"""
        actual, _ = self.extract(source)
        self.assertEqual(
            actual,
            [
                ("outer", ("helper",)),
                ("inner", ("util", "save")),
                ("outer", ("another",)),
                ("run", ("self", "validate")),
                ("run", ("cls", "create")),
                ("run", ("service", "repository", "save")),
                ("a", ("outer",)),
            ],
        )

    def test_python_control_flow_and_unsupported_scopes(self):
        actual, _ = self.extract("""def run():
    for x in items():
        step()
    while condition():
        step()
    try:
        check()
    except Exception:
        recover()
    callback = lambda: hidden()
    obj[key]()
    factory()()
    super().run()
""")
        self.assertEqual(
            [p for _, p in actual], [("items",), ("step",), ("condition",), ("step",), ("check",), ("recover",)]
        )

    def test_script_bodies_bindings_methods_and_headers(self):
        source = """@deco()
class S extends base() {
  value = make();
  @mark()
  run(x=default()) { this.check(); function inner() { util.save(); } }
  field = () => helper();
}
const f = function named(x=default()) { check(); };
const g = () => check();
function outer(x=default()) { if (true) { inside(); } }
main();
"""
        actual, _ = self.extract(source, Language.TYPESCRIPT, "a.ts")
        self.assertEqual(
            actual,
            [
                ("run", ("this", "check")),
                ("inner", ("util", "save")),
                ("field", ("helper",)),
                ("f", ("check",)),
                ("g", ("check",)),
                ("outer", ("inside",)),
                ("a", ("main",)),
            ],
        )

    def test_script_dynamic_optional_new_object_and_jsx_omissions(self):
        for language, path in ((Language.JAVASCRIPT, "a.jsx"), (Language.TYPESCRIPT, "a.tsx")):
            actual, _ = self.extract(
                """function Button() {
 return <button>{render()}</button>;
}
obj[key](); factory()(); obj?.run(); fn?.(); new Service();
const obj = { method() { hidden(); } };
const x = visible();
""",
                language,
                path,
            )
            self.assertEqual(actual, [("Button", ("render",)), ("a", ("visible",))])

    def test_recovery_retains_unaffected_sibling_only(self):
        for source, language, path in (
            ("def good():\n    helper()\ndef broken(\n", Language.PYTHON, "a.py"),
            ("function good() { helper(); } function broken( {", Language.JAVASCRIPT, "a.js"),
            ("function good(): void { helper(); } function broken( {", Language.TYPESCRIPT, "a.ts"),
        ):
            actual, _ = self.extract(source, language, path)
            self.assertEqual(actual, [("good", ("helper",))])

    def test_coordinates_unicode_and_mismatched_input(self):
        actual, sites = self.extract("def café():\n    café()\n")
        self.assertEqual(actual, [("café", ("café",))])
        site = sites[0]
        self.assertEqual((site.location.start_line, site.span.start_column, site.span.end_column), (2, 4, 11))
        p = parse_source("a.py", Language.PYTHON, b"run()")
        result = extract_entities(p)
        with self.assertRaises(CallExtractionError):
            extract_call_sites(replace(p, path="b.py"), result)
