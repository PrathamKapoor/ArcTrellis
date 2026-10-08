import unittest
from dataclasses import replace
from unittest.mock import patch

from arctrellis.calls import (
    CallResolution,
    CallResolutionInvariantError,
    CallResolutionStatus,
    resolve_calls,
)
from arctrellis.core import Confidence, EntityKind, RelationshipKind
from arctrellis.resolution import resolve_imports

from .fixtures import mixed_sources
from .test_indexing import index_sources


class ResolutionTests(unittest.TestCase):
    def test_script_static_block_bindings_are_not_visible_to_methods(self):
        for path in ("a.js", "a.ts"):
            _, _, result, edges = self.resolve(
                {path: "class S { static { function helper() {} } run() { helper(); } }"}
            )
            self.assertEqual((result.unresolved_count, len(edges)), (1, 0))
            _, _, result, edges = self.resolve(
                {path: "function helper() {} class S { static { function helper() {} } run() { helper(); } }"}
            )
            self.assertEqual(result.resolved_count, 1)
            self.assertEqual(result.graph.get_entity(edges[0].target_entity_id).qualified_name, path + "::helper")

    def test_import_decisions_must_match_preserved_import_evidence(self):
        index = index_sources(
            {"app.py": "from util import f\nf()", "util.py": "def f(): pass", "other.py": "def f(): pass"}
        )
        imports = resolve_imports(index)
        other = next(e.id for e in index.graph.entities() if e.kind is EntityKind.MODULE and e.name == "other")
        corrupted = replace(
            imports,
            resolutions=(replace(imports.resolutions[0], target_module_id=other, candidate_module_ids=(other,)),),
        )
        with self.assertRaises(CallResolutionInvariantError):
            resolve_calls(index, corrupted)

    def test_python_class_namespace_is_not_a_method_closure(self):
        _, _, result, edges = self.resolve(
            {
                "util.py": "def helper(): pass",
                "app.py": "class S:\n    from util import helper\n    def run(self):\n        helper()\n",
            }
        )
        self.assertEqual((result.unresolved_count, len(edges)), (1, 0))
        _, _, result, edges = self.resolve(
            {
                "util.py": "def helper(): pass",
                "app.py": (
                    "def helper(): pass\nclass S:\n    from util import helper\n    def run(self):\n        helper()\n"
                ),
            }
        )
        self.assertEqual(result.resolved_count, 1)
        self.assertEqual(result.graph.get_entity(edges[0].target_entity_id).qualified_name, "app.py::helper")

    def test_mixed_end_to_end_confidence_evidence_and_repeatability(self):
        index, imports, result, edges = self.resolve(mixed_sources())
        self.assertEqual(
            (index.call_site_count, result.resolved_count, result.unresolved_count, result.ambiguous_count, len(edges)),
            (6, 4, 1, 1, 4),
        )
        self.assertEqual(imports.resolved_count, 3)
        self.assertEqual(sorted(e.confidence_score for e in edges), [0.75, 0.75, 0.75, 0.85])
        fresh = index_sources(mixed_sources())
        fresh_imports = resolve_imports(fresh)
        rerun = resolve_calls(fresh, fresh_imports)
        self.assertEqual(index.call_sites, fresh.call_sites)
        self.assertEqual(imports.resolutions, fresh_imports.resolutions)
        self.assertEqual(result.resolutions, rerun.resolutions)
        self.assertEqual(result.graph.relationships(), rerun.graph.relationships())

    def resolve(self, sources):
        index = index_sources(sources)
        imports = resolve_imports(index)
        base = imports.graph.relationships()
        result = resolve_calls(index, imports)
        self.assertEqual(imports.graph.relationships(), base)
        self.assertEqual(len(result.resolutions), index.call_site_count)
        self.assertEqual(
            result.resolved_count + result.unresolved_count + result.ambiguous_count, index.call_site_count
        )
        edges = [e for e in result.graph.relationships() if e.kind is RelationshipKind.CALLS]
        self.assertEqual(len(edges), result.resolved_count)
        sites = {s.id: s for s in index.call_sites}
        for edge in edges:
            self.assertEqual(edge.confidence, Confidence.LIKELY)
            self.assertIn(edge.confidence_score, (0.85, 0.75))
            decision = next(
                d
                for d in result.resolutions
                if d.target_entity_id == edge.target_entity_id
                and sites[d.call_site_id].owner_entity_id == edge.source_entity_id
                and sites[d.call_site_id].location == edge.evidence[0].location
                and str(sites[d.call_site_id].span.start_byte) == dict(edge.evidence[0].metadata)["start_byte"]
            )
            site = sites[decision.call_site_id]
            self.assertEqual(edge.evidence[0].location, site.location)
            self.assertEqual(edge.evidence[0].analysis_method, decision.resolution_method)
            for coordinate in ("start_byte", "end_byte", "start_column", "end_column", "start_line", "end_line"):
                self.assertEqual(dict(edge.evidence[0].metadata)[coordinate], str(getattr(site.span, coordinate)))
            self.assertEqual(result.graph.get_relationship(edge.id), edge)
        self.assertTrue(all(e.confidence is Confidence.PROVEN for e in base if e.kind is RelationshipKind.DEFINES))
        return index, imports, result, edges

    def test_python_lexical_nested_recursion_duplicates_unknown_and_chain(self):
        index, _, result, edges = self.resolve(
            {
                "a.py": """def c():
    pass
def b():
    c()
def a():
    b()
def outer():
    def helper():
        pass
    helper()
def recur():
    recur()
def duplicate():
    pass
def duplicate():
    pass
def run():
    duplicate()
    missing()
    service.repository.save()
"""
            }
        )
        self.assertEqual((result.resolved_count, result.unresolved_count, result.ambiguous_count), (4, 2, 1))
        self.assertTrue(all(e.confidence_score == 0.85 for e in edges))
        self.assertEqual({e.evidence[0].analysis_method for e in edges}, {"python_lexical_call_resolution"})
        entities = {e.name: e for e in index.graph.entities()}
        path = result.graph.shortest_path(
            entities["a"].id, entities["c"].id, relationship_kinds={RelationshipKind.CALLS}
        )
        self.assertEqual([e.name for e in path.entities], ["a", "b", "c"])
        self.assertEqual([e.evidence[0].location.start_line for e in path.relationships], [6, 4])

    def test_script_lexical_bindings_nested_recursive_ambiguity(self):
        for path in ("a.js", "a.ts"):
            _, _, result, edges = self.resolve(
                {
                    path: """function helper() {}
const run = () => helper();
function outer() { function inner() {} inner(); }
function recur() { recur(); }
function dup() {} function dup() {} dup(); missing();
"""
                }
            )
            self.assertEqual((result.resolved_count, result.unresolved_count, result.ambiguous_count), (3, 1, 1))
            self.assertTrue(all(e.confidence_score == 0.85 for e in edges))
            self.assertEqual({e.evidence[0].analysis_method for e in edges}, {"ecmascript_lexical_call_resolution"})

    def test_direct_same_class_python_self_cls_and_script_this(self):
        cases = {
            "a.py": """class Base:
    def inherited(self):
        pass
class S(Base):
    def validate(self):
        pass
    @classmethod
    def run(cls):
        cls.validate()
    def check(self):
        self.validate()
        self.inherited()
        self.unknown()
        super().inherited()
""",
            "a.js": """class Base { inherited() {} }
class S extends Base { validate = () => {};
run() { this.validate(); this.inherited(); this.unknown(); super.inherited(); } }
""",
            "a.ts": """class Base { inherited() {} }
class S extends Base { validate() {} run() { this.validate(); this.inherited(); this.unknown(); super.inherited(); } }
""",
        }
        for path, source in cases.items():
            _, _, result, edges = self.resolve({path: source})
            self.assertEqual(result.resolved_count, 2 if path.endswith("py") else 1)
            self.assertTrue(all(e.confidence_score == 0.85 for e in edges))
            prefix = "python" if path.endswith("py") else "ecmascript"
            self.assertEqual({e.evidence[0].analysis_method for e in edges}, {prefix + "_same_class_method_resolution"})

    def test_duplicate_methods_are_ambiguous(self):
        for path, source in (
            ("a.py", "class S:\n    def f(self): pass\n    def f(self): pass\n    def run(self): self.f()\n"),
            ("a.js", "class S { f() {} f() {} run() { this.f(); } }"),
        ):
            _, _, result, edges = self.resolve({path: source})
            self.assertEqual((result.ambiguous_count, len(edges)), (1, 0))

    def test_python_imported_symbols_aliases_modules_and_local_imports(self):
        _, _, result, edges = self.resolve(
            {
                "util.py": "def validate():\n    pass\n",
                "app.py": """from util import validate as check
import util
check()
util.validate()
def run():
    from util import validate
    validate()
class S:
    def run(self):
        from util import validate
        validate()
""",
            }
        )
        self.assertEqual(result.resolved_count, 4)
        self.assertTrue(all(e.confidence_score == 0.75 for e in edges))
        self.assertEqual(
            {result.graph.get_entity(e.source_entity_id).kind for e in edges},
            {EntityKind.MODULE, EntityKind.FUNCTION, EntityKind.METHOD},
        )
        self.assertEqual(
            {e.evidence[0].analysis_method for e in edges},
            {"python_imported_symbol_call_resolution", "python_imported_module_member_resolution"},
        )

    def test_script_named_alias_namespace_and_commonjs_members(self):
        for path in ("app.js", "app.ts"):
            _, _, result, edges = self.resolve(
                {
                    "util.ts": "export function validate() {}",
                    path: """import { validate as check } from "./util";
import * as util from "./util";
check(); util.validate();
function run() { const local = require("./util"); local.validate(); }
""",
                }
            )
            self.assertEqual((result.resolved_count, result.unresolved_count), (3, 1))
            self.assertTrue(all(e.confidence_score == 0.75 for e in edges))
            self.assertEqual(
                {e.evidence[0].analysis_method for e in edges},
                {"ecmascript_imported_symbol_call_resolution", "ecmascript_imported_module_member_resolution"},
            )

    def test_import_negative_cases_and_direct_module_targets_only(self):
        _, _, result, edges = self.resolve(
            {
                "util.ts": "export function validate() {} function outer() { function hidden() {} }",
                "app.ts": """import type { validate } from "./util";
import defaultCallable from "./util";
import { missing, hidden } from "./util";
import * as bare from "external";
validate(); defaultCallable(); missing(); hidden(); bare.validate();
const callable = require("./util"); callable();
""",
            }
        )
        self.assertEqual((result.resolved_count, result.unresolved_count, len(edges)), (0, 7, 0))
        _, _, result, edges = self.resolve(
            {
                "pkg/util.py": "def validate(): pass",
                "app.py": "import pkg.util\npkg.validate()\nfrom pkg.util import validate\nvalidate.member()",
            }
        )
        self.assertEqual((result.resolved_count, result.unresolved_count, len(edges)), (0, 2, 0))

    def test_import_ambiguity_and_duplicate_visible_bindings(self):
        for sources in (
            {"util.py": "def f(): pass\ndef f(): pass", "app.py": "from util import f\nf()"},
            {"util.py": "def f(): pass", "app.py": "from util import f\nfrom util import f\nf()"},
        ):
            _, _, result, edges = self.resolve(sources)
            self.assertEqual((result.ambiguous_count, len(edges)), (1, 0))
        _, _, result, edges = self.resolve(
            {
                "util.js": "export function f() {}",
                "util.ts": "export function f() {}",
                "app.js": 'import { f } from "./util"; f();',
            }
        )
        self.assertEqual((result.unresolved_count, len(edges)), (1, 0))

    def test_nearest_import_shadows_farther_function(self):
        _, _, result, edges = self.resolve(
            {
                "util.py": "def f(): pass",
                "app.py": """def f(): pass
def run():
    from util import f
    f()
""",
            }
        )
        self.assertEqual(result.resolved_count, 1)
        self.assertEqual(result.graph.get_entity(edges[0].target_entity_id).qualified_name, "util.py::f")
        self.assertEqual(edges[0].confidence_score, 0.75)

    def test_repeatability_no_reads_original_snapshot_and_separate_sites(self):
        index = index_sources({"a.py": "def helper(): pass\ndef run():\n    helper()\n    helper()\n"})
        imports = resolve_imports(index)
        base = imports.graph.entities(), imports.graph.relationships()
        with (
            patch("builtins.open", side_effect=AssertionError("read")),
            patch("pathlib.Path.open", side_effect=AssertionError("read")),
        ):
            a, b = resolve_calls(index, imports), resolve_calls(index, imports)
        self.assertEqual(a.resolutions, b.resolutions)
        self.assertEqual(a.graph.relationships(), b.graph.relationships())
        self.assertEqual(base, (imports.graph.entities(), imports.graph.relationships()))
        edges = [e for e in a.graph.relationships() if e.kind is RelationshipKind.CALLS]
        self.assertEqual(len({e.id for e in edges}), 2)
        self.assertEqual(len({e.evidence[0].id for e in edges}), 2)
        with self.assertRaises(CallResolutionInvariantError):
            resolve_calls(index, resolve_imports(index_sources({"different.py": ""})))

    def test_resolution_record_invariants(self):
        s = CallResolutionStatus
        good = CallResolution("site", s.RESOLVED, "target", ("target",), "unique", "python_lexical_call_resolution")
        with self.assertRaises(AttributeError):
            good.reason = "changed"
        for change in (
            {"target_entity_id": None},
            {"candidate_entity_ids": ()},
            {"status": s.UNRESOLVED},
            {"resolution_method": None},
        ):
            with self.assertRaises((ValueError, TypeError)):
                replace(good, **change)
