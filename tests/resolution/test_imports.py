import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from arctrellis.core import Confidence, EntityKind, RelationshipKind
from arctrellis.indexing import index_repository
from arctrellis.resolution import ImportResolution, ImportResolutionStatus, resolve_imports


class ImportResolutionTests(unittest.TestCase):
    def index(self, sources):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, source in sources.items():
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(source, encoding="utf-8")
            return index_repository(root)

    def resolve(self, sources):
        index = self.index(sources)
        self.assertTrue(index.is_complete)
        return index, resolve_imports(index)

    def test_python_catalog(self):
        for path, statement in (
            ("util.py", "import util"),
            ("pkg/util.py", "from pkg.util import Thing"),
            ("pkg/__init__.py", "from pkg import util"),
            ("src/pkg/util.py", "import pkg.util"),
            ("src/pkg/util.py", "import src.pkg.util"),
        ):
            with self.subTest(path=path, statement=statement):
                index, result = self.resolve({"app.py": statement, path: ""})
                self.assertEqual(result.resolved_count, 1)
                target = result.graph.get_entity(result.resolutions[0].target_module_id)
                self.assertEqual(target.qualified_name, path)
                self.assertEqual(target.kind, EntityKind.MODULE)
                self.assertEqual(index.graph.relationship_count + 1, result.graph.relationship_count)

    def test_python_relative(self):
        for current, statement, target in (
            ("pkg/app.py", "from .util import thing", "pkg/util.py"),
            ("pkg/services/app.py", "from ..util import thing", "pkg/util.py"),
            ("pkg/__init__.py", "from .util import thing", "pkg/util.py"),
            ("src/pkg/app.py", "from .util import thing", "src/pkg/util.py"),
            ("pkg/app.py", "from . import thing", "pkg/__init__.py"),
        ):
            with self.subTest(current=current):
                _, result = self.resolve({current: statement, target: ""})
                self.assertEqual(result.resolved_count, 1)
                self.assertEqual(result.graph.get_entity(result.resolutions[0].target_module_id).qualified_name, target)

    def test_python_ambiguity_and_no_symbol_resolution(self):
        _, result = self.resolve(
            {
                "app.py": "import pkg\nfrom pkg import Thing\nimport external",
                "pkg.py": "",
                "pkg/__init__.py": "",
                "pkg/Thing.py": "",
            }
        )
        self.assertEqual((result.resolved_count, result.ambiguous_count, result.unresolved_count), (0, 2, 1))
        self.assertEqual(len(tuple(e for e in result.graph.relationships() if e.kind is RelationshipKind.IMPORTS)), 0)
        for resolution in result.resolutions:
            if resolution.status is ImportResolutionStatus.AMBIGUOUS:
                self.assertEqual(len(resolution.candidate_module_ids), 2)

    def test_ecmascript_candidates(self):
        for current, literal, target in (
            ("app.js", "./service", "service.js"),
            ("app.ts", "./service", "service.ts"),
            ("app.ts", "./service.ts", "service.ts"),
            ("pkg/app.js", "../util", "util.js"),
            ("app.js", "./service", "service/index.tsx"),
            ("app.ts", "./legacy", "legacy.js"),
        ):
            with self.subTest(current=current, literal=literal, target=target):
                _, result = self.resolve({current: f'import x from "{literal}";', target: ""})
                self.assertEqual(result.resolved_count, 1)
                self.assertEqual(result.graph.get_entity(result.resolutions[0].target_module_id).qualified_name, target)

    def test_ecmascript_unsupported_and_ambiguous(self):
        _, result = self.resolve(
            {
                "app.ts": """import A from "./service";
import B from "react";
import C from "@/service";
import D from "../../escape";
import E from "./service.js";
import F from "./serv\\x69ce";
""",
                "service.ts": "",
                "service.tsx": "",
            }
        )
        self.assertEqual((result.resolved_count, result.unresolved_count, result.ambiguous_count), (0, 5, 1))
        self.assertEqual(len(tuple(e for e in result.graph.relationships() if e.kind is RelationshipKind.IMPORTS)), 0)
        reasons = {r.reason for r in result.resolutions}
        self.assertTrue({"non_relative_specifier", "outside_root", "escaped_or_dynamic_literal"}.issubset(reasons))

    def test_type_only_side_effect_and_commonjs(self):
        _, result = self.resolve(
            {
                "app.ts": (
                    'import type { Thing } from "./types";\nimport "./types";\nfunction '
                    'run() { const t = require("./types"); }'
                ),
                "types.ts": "export type Thing = string;",
            }
        )
        self.assertEqual(result.resolved_count, 3)
        owners = [
            result.graph.get_entity(e.source_entity_id).kind
            for e in tuple(e for e in result.graph.relationships() if e.kind is RelationshipKind.IMPORTS)
        ]
        self.assertEqual(owners.count(EntityKind.MODULE), 2)
        self.assertEqual(owners.count(EntityKind.FUNCTION), 1)

    def test_python_scopes_evidence_confidence(self):
        _, result = self.resolve(
            {
                "app.py": "def run():\n    import util\nclass Service:\n    def create(self):\n        import util\n",
                "util.py": "",
            }
        )
        edges = tuple(e for e in result.graph.relationships() if e.kind is RelationshipKind.IMPORTS)
        self.assertEqual(len(edges), 2)
        self.assertEqual(
            {result.graph.get_entity(e.source_entity_id).kind for e in edges}, {EntityKind.FUNCTION, EntityKind.METHOD}
        )
        for edge in edges:
            self.assertEqual(edge.confidence, Confidence.LIKELY)
            self.assertEqual(edge.confidence_score, 0.90)
            self.assertEqual(edge.evidence[0].analysis_method, "python_static_import_resolution")
            self.assertEqual(edge.evidence[0].location.file_path, "app.py")
            self.assertIn(edge.evidence[0].location.start_line, (2, 5))
            self.assertEqual(result.graph.get_relationship(edge.id), edge)
        self.assertTrue(
            all(
                e.confidence is Confidence.PROVEN
                for e in tuple(e for e in result.graph.relationships() if e.kind is RelationshipKind.DEFINES)
            )
        )

    def test_determinism_original_graph_and_no_reads(self):
        index = self.index({"app.py": "import util\nimport util\n", "util.py": ""})
        base = index.graph.entities(), index.graph.relationships()
        with (
            patch("builtins.open", side_effect=AssertionError("resolver reopened source")),
            patch("pathlib.Path.open", side_effect=AssertionError("resolver reopened source")),
        ):
            a, b = resolve_imports(index), resolve_imports(index)
        self.assertEqual(a.resolutions, b.resolutions)
        self.assertEqual((a.graph.entities(), a.graph.relationships()), (b.graph.entities(), b.graph.relationships()))
        self.assertEqual(base, (index.graph.entities(), index.graph.relationships()))
        self.assertEqual(len(tuple(e for e in a.graph.relationships() if e.kind is RelationshipKind.IMPORTS)), 2)
        self.assertEqual(
            len(
                {
                    e.evidence[0].id
                    for e in tuple(e for e in a.graph.relationships() if e.kind is RelationshipKind.IMPORTS)
                }
            ),
            2,
        )

    def test_empty_and_partial(self):
        _, empty = self.resolve({})
        self.assertEqual(empty.resolutions, ())
        index = self.index({"app.py": "import util\ndef broken(", "util.py": ""})
        self.assertFalse(index.is_complete)
        self.assertEqual(resolve_imports(index).resolved_count, 1)

    def test_root_index_and_python_literal_dot_filename(self):
        _, result = self.resolve({"app.js": 'import "./";', "index.js": ""})
        self.assertEqual(result.resolved_count, 1)
        _, result = self.resolve({"app.py": "import pkg.util", "pkg.util.py": ""})
        self.assertEqual(result.unresolved_count, 1)

    def test_directory_specifiers_do_not_match_files(self):
        for specifier in ("./service/", "./service.js/", "./service.js/.", "./service.js/.."):
            with self.subTest(specifier=specifier):
                _, result = self.resolve({"app.js": f'import "{specifier}";', "service.js": ""})
                self.assertEqual(result.unresolved_count, 1)
        _, result = self.resolve({"app.js": 'import "./service/";', "service.js": "", "service/index.ts": ""})
        self.assertEqual(result.resolved_count, 1)
        self.assertEqual(
            result.graph.get_entity(result.resolutions[0].target_module_id).qualified_name, "service/index.ts"
        )

    def test_conservative_catalog_boundaries(self):
        _, result = self.resolve({"app.py": "import pkg.util", "pkg/util.py": "", "src/pkg/util.py": ""})
        self.assertEqual(result.ambiguous_count, 1)
        _, result = self.resolve({"pkg/app.py": "from ...outside import x", "outside.py": ""})
        self.assertEqual(result.unresolved_count, 1)
        _, result = self.resolve({"app.js": 'import "./serv%69ce.js";', "serv%69ce.js": ""})
        self.assertEqual(result.unresolved_count, 1)

    def test_result_validation(self):
        R, S = ImportResolution, ImportResolutionStatus
        valid = R("i", S.RESOLVED, "t", ("t",), "unique_module")
        with self.assertRaises(AttributeError):
            valid.reason = "changed"
        for args in [
            ("i", S.RESOLVED, None, (), "x"),
            ("i", S.AMBIGUOUS, None, ("a",), "x"),
            ("i", S.UNRESOLVED, "t", (), "x"),
            ("i", S.AMBIGUOUS, None, ("b", "a"), "x"),
        ]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                R(*args)
