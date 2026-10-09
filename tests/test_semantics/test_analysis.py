import tempfile
import unittest
from pathlib import Path

from arctrellis.calls import resolve_calls
from arctrellis.core import Confidence, EntityKind, RelationshipKind
from arctrellis.indexing import index_repository
from arctrellis.resolution import resolve_imports
from arctrellis.test_semantics import analyze_tests


def analyze(sources):
    with tempfile.TemporaryDirectory() as directory:
        for path, source in sources.items():
            Path(directory, path).write_text(source, encoding="utf-8")
        index = index_repository(directory)
    imports = resolve_imports(index)
    calls = resolve_calls(index, imports)
    return index, calls, analyze_tests(index, imports, calls)


class TestSemanticsTests(unittest.TestCase):
    def test_callback_destructuring_and_named_function_shadowing(self):
        cases = (
            'test("x", () => { const {validate} = obj; validate(); });',
            'test("x", ({validate}) => { validate(); });',
            'describe("s", () => { const {validate} = obj; test("x", () => { validate(); }); });',
            'test("x", function validate() { validate(); });',
            'describe("s", function validate() { test("x", () => { validate(); }); });',
        )
        for extension in ("js", "ts"):
            for source in cases:
                with self.subTest(extension=extension, source=source):
                    _, _, result = analyze({f"a.{extension}": "function validate() {} " + source})
                    self.assertEqual(result.test_count, 1)
                    self.assertEqual(result.resolved_test_relationship_count, 0)
                    test_id = result.test_entities[0].id
                    self.assertFalse(result.graph.outgoing(test_id, kind=RelationshipKind.CALLS))

    def test_callback_binding_and_optional_call_boundaries(self):
        _, _, result = analyze(
            {
                "a.js": (
                    'function validate() {}\ntest?.("optional", () => { validate(); });'
                    'test("parameter", (validate) => { validate(); });'
                    'test("local", () => { const validate = other; validate(); });'
                )
            }
        )
        self.assertEqual([t.name for t in result.test_entities], ["parameter", "local"])
        self.assertEqual(result.resolved_test_relationship_count, 0)

    def test_memory_and_immutable_observations(self):
        from dataclasses import FrozenInstanceError, fields, is_dataclass

        from arctrellis.parsing import ParsedSource, SyntaxNode

        index, _, result = analyze({"a.js": 'test("x", () => { unknown(); });'})
        pending = [index.test_observations, result.observations]
        while pending:
            value = pending.pop()
            self.assertNotIsInstance(value, (bytes, bytearray, ParsedSource, SyntaxNode))
            if isinstance(value, tuple):
                pending.extend(value)
            elif is_dataclass(value):
                pending.extend(getattr(value, f.name) for f in fields(value))
        with self.assertRaises(FrozenInstanceError):
            result.observations[0].name = "changed"

    def test_test_methods_resolve_production_methods(self):
        _, _, result = analyze(
            {
                "a.py": (
                    "class TestPayments:\n    def create(self): pass\n"
                    "    def test_create(self):\n        self.create()\n"
                )
            }
        )
        edge = next(e for e in result.graph.relationships() if e.kind is RelationshipKind.TESTS)
        self.assertEqual(result.graph.get_entity(edge.target_entity_id).kind, EntityKind.METHOD)

    def test_framework_graph_preserved_and_endpoint_not_tested(self):
        from arctrellis.frameworks import resolve_framework_flow, resolve_http_endpoints
        from tests.frameworks.test_endpoints import analyze as framework_analyze

        index, imports, calls, endpoints = framework_analyze(
            {
                "a.py": (
                    "from fastapi import FastAPI, Depends\napp = FastAPI()\ndef auth(): pass\n"
                    '@app.get("/x", dependencies=[Depends(auth)])\ndef handler(): pass\n'
                    "def test_handler():\n    handler()\n"
                )
            }
        )
        flow = resolve_framework_flow(index, imports, calls, endpoints)
        result = analyze_tests(index, imports, calls, base_graph=flow.graph)
        self.assertTrue(set(flow.graph.relationships()) <= set(result.graph.relationships()))
        self.assertEqual(result.resolved_test_relationship_count, 1)
        self.assertFalse(
            any(
                result.graph.get_entity(e.target_entity_id).kind is EntityKind.API_ENDPOINT
                for e in result.graph.relationships()
                if e.kind is RelationshipKind.TESTS
            )
        )
        self.assertEqual(endpoints.graph.entities(), resolve_http_endpoints(index, imports, calls).graph.entities())

    def test_observation_and_snapshot_validation(self):
        from dataclasses import replace

        index, calls, result = analyze({"a.py": "def test_x(): pass\n"})
        with self.assertRaises(ValueError):
            replace(result.observations[0], id="forged")
        with self.assertRaises(TypeError):
            replace(result.observations[0], metadata={"decorator_0": "x"})
        with self.assertRaises(ValueError):
            replace(index, test_observations=())
        calls.graph.add_entity(result.test_entities[0])
        with self.assertRaises(ValueError):
            analyze_tests(index, resolve_imports(index), calls)

    def test_python_declarations_and_false_positives(self):
        _, _, result = analyze(
            {
                "a.py": (
                    "def test_one(): pass\ndef ordinary():\n    def test_helper(): pass\n"
                    "class TestPayments:\n    def test_method(self): pass\n"
                    "class Production:\n    def test_no(self): pass\n"
                    "@decorator\ndef test_decorated(): pass\ndef test_one(): pass\n"
                )
            }
        )
        self.assertEqual(
            [t.name for t in result.test_entities], ["test_one", "test_method", "test_decorated", "test_one"]
        )
        self.assertEqual(len({t.id for t in result.test_entities}), 4)
        self.assertEqual(result.unlinked_test_count, 4)

    def test_script_syntax(self):
        for extension in ("js", "ts"):
            with self.subTest(extension=extension):
                _, _, result = analyze(
                    {
                        f"a.{extension}": (
                            'test("one", () => {}); it("two", function() {});'
                            'describe("suite", () => { test("three", () => {}); });'
                            'obj.test("no", () => {}); service.it("no", () => {});'
                            "test(name, () => {}); test(`dynamic ${name}`, () => {});"
                            'function production() { test("no", () => {}); }'
                        )
                    }
                )
                self.assertEqual([t.name for t in result.test_entities], ["one", "two", "three"])

    def test_direct_evidence_no_transitive_or_test_targets(self):
        index, calls, result = analyze(
            {
                "service.py": "def inner(): pass\ndef create_payment():\n    inner()\n",
                "test_service.py": (
                    "from service import create_payment\ndef test_create_payment():\n"
                    "    assert create_payment()\n    missing()\n    test_other()\n"
                    "def test_other(): pass\n"
                ),
            }
        )
        edges = [e for e in result.graph.relationships() if e.kind is RelationshipKind.TESTS]
        self.assertEqual(len(edges), 1)
        edge = edges[0]
        self.assertEqual(result.graph.get_entity(edge.source_entity_id).kind, EntityKind.TEST)
        self.assertEqual(result.graph.get_entity(edge.target_entity_id).name, "create_payment")
        self.assertEqual((edge.confidence, edge.confidence_score), (Confidence.LIKELY, 0.85))
        self.assertEqual(edge.evidence[0].location.start_line, 3)
        self.assertEqual(edge.evidence[0].analysis_method, "python_direct_test_call")
        self.assertTrue(set(calls.graph.relationships()) <= set(result.graph.relationships()))
        self.assertFalse(any(e.kind is EntityKind.TEST for e in index.graph.entities()))
        path = result.graph.shortest_path(edge.source_entity_id, edge.target_entity_id)
        self.assertEqual(path.relationships, (edge,))

    def test_script_imported_call_and_nested_callback_omission(self):
        _, _, result = analyze(
            {
                "service.js": "export function validate() {}",
                "service.test.js": (
                    'import { validate } from "./service";\ntest("validates", () => {\n'
                    "validate(); (() => { validate(); })();\n});"
                ),
            }
        )
        self.assertEqual(result.resolved_test_relationship_count, 1)
        edge = next(e for e in result.graph.relationships() if e.kind is RelationshipKind.TESTS)
        self.assertEqual(edge.evidence[0].analysis_method, "ecmascript_direct_test_call")
        self.assertEqual(edge.evidence[0].location.start_line, 3)

    def test_ambiguous_call_has_no_test_edge(self):
        _, _, result = analyze({"a.py": "def f(): pass\ndef f(): pass\ndef test_x():\n    f()\n"})
        self.assertEqual(result.resolved_test_relationship_count, 0)

    def test_deterministic_and_malformed(self):
        sources = {"a.py": "def test_good(): pass\ndef test_bad(:\n", "a.js": 'test("good", () => {});'}
        first = analyze(sources)[2]
        second = analyze(sources)[2]
        self.assertEqual(first.observations, second.observations)
        self.assertEqual(first.graph.entities(), second.graph.entities())
        self.assertEqual(first.graph.relationships(), second.graph.relationships())
        self.assertTrue(all(t.name != "test_bad" for t in first.test_entities))
