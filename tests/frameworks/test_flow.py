"""Pre-handler contracts: source sites, precise roles, uncertainty and ownership."""

import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from unittest.mock import patch

from arctrellis.core import Confidence, RelationshipKind
from arctrellis.frameworks import EndpointResolutionStatus as Status
from tests.frameworks.test_endpoints import analyze


def flow(sources):
    from arctrellis.frameworks import resolve_framework_flow

    index, imports, calls, endpoints = analyze(sources)
    return index, endpoints, resolve_framework_flow(index, imports, calls, endpoints)


def applied(result):
    return [r for r in result.graph.relationships() if r.kind is RelationshipKind.APPLIES_MIDDLEWARE]


EXPRESS = 'import express from "express";\nconst app = express();\n'
FASTAPI = "from fastapi import FastAPI, Depends\napp = FastAPI()\n"
FLASK = "from flask import Flask\napp = Flask(__name__)\n"


class PreHandlerTests(unittest.TestCase):
    def test_pre_handler_provenance_cannot_be_replaced_by_other_framework_import(self):
        from arctrellis.frameworks.flow_models import _pre_id

        index, _, _ = flow(
            {
                "api.py": "from flask import Flask\nfrom fastapi import FastAPI\n"
                "app = Flask(__name__)\napi = FastAPI()\n@app.before_request\ndef auth(): pass\n"
                '@api.get("/x")\ndef handler(): pass\n'
            }
        )
        p = replace(index.pre_handler_observations[0], binding=index.route_observations[0].binding)
        p = replace(p, id=_pre_id(p))
        with self.assertRaises(ValueError):
            replace(index, pre_handler_observations=(p,))

    def test_depends_requires_actual_fastapi_depends_import(self):
        from arctrellis.frameworks.flow_models import _pre_id

        index, _, _ = flow(
            {
                "api.py": FASTAPI + "def auth(): pass\n"
                '@app.get("/x", dependencies=[Depends(auth)])\ndef handler(): pass\n'
            }
        )
        p = index.pre_handler_observations[0]
        with self.assertRaises(ValueError):
            replace(p, provenance_import_id=None)
        wrong = replace(p, provenance_import_id=p.binding.import_entity_id)
        wrong = replace(wrong, id=_pre_id(wrong))
        with self.assertRaises(ValueError):
            replace(index, pre_handler_observations=(wrong,))

    def test_class_scoped_depends_and_callable_shadows_are_deferred(self):
        for shadow in ("Depends = custom", "def auth(): pass", "from custom import Depends"):
            with self.subTest(shadow=shadow):
                _, _, result = flow(
                    {
                        "api.py": FASTAPI + "def auth(): pass\nclass C:\n    " + shadow + "\n"
                        '    @app.get("/x", dependencies=[Depends(auth)])\n    def handler(self): pass\n'
                    }
                )
                self.assertEqual(len(result.endpoints), 1)
                self.assertFalse(applied(result))

    def test_express_preserves_argument_order_and_excludes_handler(self):
        index, base, result = flow(
            {
                "app.js": EXPRESS
                + 'function z() {}\nfunction a() {}\nfunction handler() {}\napp.get("/x", z, a, handler);\n'
            }
        )
        self.assertEqual([p.callable_reference for p in result.pre_handler_observations], [("z",), ("a",)])
        self.assertEqual([p.order_index for p in result.pre_handler_observations], [0, 1])
        self.assertEqual(index.pre_handler_observation_count, 2)
        self.assertEqual(index.file_results[0].pre_handler_observation_count, 2)
        self.assertEqual(result.resolved_pre_handler_count, 2)
        self.assertEqual(len(applied(result)), 2)
        for edge in applied(result):
            self.assertEqual((edge.confidence, edge.confidence_score), (Confidence.LIKELY, 0.85))
            self.assertEqual(edge.evidence[0].analysis_method, "express_local_route_middleware")
            self.assertEqual(dict(edge.evidence[0].metadata)["semantic_kind"], "route_middleware")
            self.assertEqual(edge.source_entity_id, base.endpoints[0].id)
            self.assertTrue(
                result.graph.shortest_path(
                    edge.source_entity_id,
                    edge.target_entity_id,
                    relationship_kinds={RelationshipKind.APPLIES_MIDDLEWARE},
                )
            )
        self.assertFalse(applied(base))

    def test_express_imported_named_alias_namespace(self):
        for imported, reference in [
            ('import {auth as check} from "./security";', "check"),
            ('import * as security from "./security";', "security.auth"),
        ]:
            with self.subTest(imported=imported):
                _, _, result = flow(
                    {
                        "app.ts": EXPRESS
                        + imported
                        + f'\nfunction handler() {{}}\napp.post("/x", {reference}, handler);',
                        "security.ts": "export function auth() {}",
                    }
                )
                edge = applied(result)[0]
                self.assertEqual(edge.confidence_score, 0.75)
                self.assertEqual(edge.evidence[0].analysis_method, "express_imported_route_middleware")

    def test_express_unknown_duplicate_factory_and_inline_explicit(self):
        _, _, result = flow(
            {
                "app.js": EXPRESS + "function auth() {}\nfunction auth() {}\n"
                'function handler() {}\napp.get("/x", missing, auth, factory(), (r,s,n)=>{}, handler);'
            }
        )
        self.assertEqual(
            [r.status for r in result.pre_handler_resolutions],
            [Status.UNRESOLVED, Status.AMBIGUOUS, Status.UNSUPPORTED, Status.UNSUPPORTED],
        )
        self.assertFalse(applied(result))

    def test_express_rebound_reference_not_resolved(self):
        _, _, result = flow(
            {
                "app.js": EXPRESS + "function auth() {}\nauth = other;\n"
                'function handler() {}\napp.get("/x", auth, handler);'
            }
        )
        self.assertEqual(result.unresolved_pre_handler_count, 1)
        self.assertFalse(applied(result))

    def test_fastapi_direct_alias_order_and_evidence(self):
        _, _, result = flow(
            {
                "api.py": "from fastapi import FastAPI, Depends as Dependency\napp = FastAPI()\n"
                'def z(): pass\ndef a(): pass\n@app.get("/x", dependencies=[Dependency(z), Dependency(a)])\n'
                "async def handler(): pass\n"
            }
        )
        self.assertEqual([p.callable_reference for p in result.pre_handler_observations], [("z",), ("a",)])
        self.assertEqual([p.order_index for p in result.pre_handler_observations], [0, 1])
        for edge in applied(result):
            self.assertEqual(edge.confidence_score, 0.85)
            self.assertEqual(edge.evidence[0].location.start_line, 5)
            self.assertEqual(edge.evidence[0].analysis_method, "fastapi_local_dependency")
            self.assertEqual(dict(edge.evidence[0].metadata)["semantic_kind"], "dependency")

    def test_fastapi_imported_dependency(self):
        for imp, reference in [("from security import auth as check", "check"), ("import security", "security.auth")]:
            with self.subTest(imp=imp):
                _, _, result = flow(
                    {
                        "api.py": FASTAPI
                        + imp
                        + f'\n@app.get("/x", dependencies=(Depends({reference}),))\ndef handler(): pass\n',
                        "security.py": "def auth(): pass\n",
                    }
                )
                self.assertEqual(applied(result)[0].confidence_score, 0.75)
                self.assertEqual(applied(result)[0].evidence[0].analysis_method, "fastapi_imported_dependency")

    def test_fastapi_custom_depends_factory_and_parameter_are_not_resolved(self):
        for declaration, dependency in [
            ("from custom import Depends", "Depends(auth)"),
            ("", "custom(auth)"),
            ("", "Depends(factory())"),
            ("", "Depends(lambda: auth())"),
        ]:
            with self.subTest(dependency=dependency):
                _, _, result = flow(
                    {
                        "api.py": FASTAPI + declaration + "\ndef auth(): pass\n"
                        f'@app.get("/x", dependencies=[{dependency}])\ndef handler(value=Depends(auth)): pass\n'
                    }
                )
                self.assertFalse(applied(result))
                self.assertEqual(len(result.endpoints), 1)
                self.assertLessEqual(len(result.pre_handler_observations), 1)

    def test_fastapi_rebound_depends_and_callable_rejected(self):
        for extra in ("Depends = custom\n", "auth = other\n"):
            with self.subTest(extra=extra):
                _, _, result = flow(
                    {
                        "api.py": FASTAPI
                        + "def auth(): pass\n"
                        + extra
                        + '@app.get("/x", dependencies=[Depends(auth)])\ndef handler(): pass\n'
                    }
                )
                self.assertFalse(applied(result))

    def test_flask_hooks_apply_to_exact_app_and_preserve_declared_order(self):
        _, _, result = flow(
            {
                "api.py": FLASK + "other = Flask(__name__)\n"
                "@app.before_request\ndef z(): pass\n@app.before_request\ndef a(): pass\n"
                '@app.route("/x", methods=["GET", "POST"])\ndef handler(): pass\n'
                '@other.route("/other")\ndef other_handler(): pass\n'
            }
        )
        self.assertEqual(result.resolved_pre_handler_count, 2)
        self.assertEqual(len(applied(result)), 4)
        for edge in applied(result):
            self.assertNotEqual(result.graph.get_entity(edge.source_entity_id).name, "GET /other")
            self.assertEqual((edge.confidence, edge.confidence_score), (Confidence.PROVEN, 1.0))
            self.assertEqual(edge.evidence[0].analysis_method, "flask_before_request_hook")
            self.assertEqual(dict(edge.evidence[0].metadata)["semantic_kind"], "request_hook")
        self.assertEqual([p.order_index for p in result.pre_handler_observations], [0, 1])

    def test_false_frameworks_and_unsupported_hooks_ignored(self):
        _, _, result = flow(
            {
                "fake.py": 'app = Fake()\n@app.before_request\ndef auth(): pass\n@app.get("/x")\ndef handler(): pass\n',
                "fake.js": 'const app = custom(); function auth(){} function handler(){} app.get("/x", auth, handler);',
            }
        )
        self.assertFalse(result.pre_handler_observations)
        self.assertFalse(applied(result))
        _, _, result = flow(
            {"api.py": FLASK + '@app.after_request\ndef auth(): pass\n@app.route("/x")\ndef handler(): pass\n'}
        )
        self.assertFalse(applied(result))

    def test_call_graph_preserved_without_middleware_to_handler_calls(self):
        _, base, result = flow(
            {
                "app.js": EXPRESS + "function auth(){} function service(){} "
                'function handler(){service();} app.get("/x", auth, handler);'
            }
        )
        original = [r for r in base.graph.relationships() if r.kind is RelationshipKind.CALLS]
        self.assertEqual(original, [r for r in result.graph.relationships() if r.kind is RelationshipKind.CALLS])
        self.assertEqual(len(original), 1)

    def test_observations_immutable_deterministic_and_source_free(self):
        sources = {
            "api.py": FASTAPI + 'def auth(): pass\n@app.get("/x", dependencies=[Depends(auth)])\ndef handler(): pass\n'
        }
        index, _, first = flow(sources)
        _, _, second = flow(sources)
        self.assertEqual(first.pre_handler_observations, second.pre_handler_observations)
        self.assertEqual(first.pre_handler_resolutions, second.pre_handler_resolutions)
        self.assertEqual(first.graph.relationships(), second.graph.relationships())
        observation = first.pre_handler_observations[0]
        hash(observation)
        with self.assertRaises(FrozenInstanceError):
            observation.order_index = 5
        with self.assertRaises(ValueError):
            replace(observation, order_index=-1)
        pending = [index]
        while pending:
            obj = pending.pop()
            self.assertNotIsInstance(obj, bytes)
            self.assertNotIn(type(obj).__name__, ("ParsedSource", "SyntaxNode"))
            if is_dataclass(obj):
                pending.extend(getattr(obj, f.name) for f in fields(obj))
            elif isinstance(obj, tuple):
                pending.extend(obj)

    def test_resolution_does_not_read_sources_and_rejects_stale_framework_graph(self):
        from arctrellis.frameworks import FrameworkResolutionInvariantError, resolve_framework_flow

        index, imports, calls, endpoints = analyze(
            {
                "api.py": FASTAPI
                + 'def auth(): pass\n@app.get("/x", dependencies=[Depends(auth)])\ndef handler(): pass\n'
            }
        )
        with patch("builtins.open", side_effect=AssertionError("source reread")):
            result = resolve_framework_flow(index, imports, calls, endpoints)
        self.assertEqual(result.resolved_pre_handler_count, 1)
        endpoints.graph.add_relationship(applied(result)[0])
        with self.assertRaises(FrameworkResolutionInvariantError):
            resolve_framework_flow(index, imports, calls, endpoints)

    def test_partial_failed_files_preserve_safe_siblings_only(self):
        from arctrellis.frameworks import FrameworkExtractionError
        from arctrellis.frameworks.flow_extraction import extract_pre_handler_observations

        def fail_one(parsed, entities, routes):
            if parsed.path == "bad.js":
                raise FrameworkExtractionError("target source must not leak")
            return extract_pre_handler_observations(parsed, entities, routes)

        with patch("arctrellis.indexing.repository.extract_pre_handler_observations", side_effect=fail_one):
            index, _, result = flow(
                {
                    "api.py": FASTAPI
                    + 'def auth(): pass\n@app.get("/x", dependencies=[Depends(auth)])\ndef handler(): pass\n'
                    "def broken(:\n",
                    "bad.js": "function bad(){}",
                }
            )
        self.assertEqual(index.partial_file_count, 1)
        self.assertEqual(index.failed_file_count, 1)
        self.assertEqual(result.resolved_pre_handler_count, 1)
        self.assertEqual(index.file_results[1].pre_handler_observation_count, 0)
        self.assertNotIn("target source", index.file_results[1].error_message)

    def test_type_only_and_default_imports_never_resolve_middleware(self):
        for imp in ('import type {auth} from "./security";', 'import auth from "./security";'):
            with self.subTest(imp=imp):
                _, _, result = flow(
                    {
                        "api.ts": EXPRESS + imp + 'function handler(){} app.get("/x", auth, handler);',
                        "security.ts": "export function auth(){}",
                    }
                )
                self.assertFalse(applied(result))
                self.assertEqual(result.unresolved_pre_handler_count, 1)

    def test_hook_decorator_location_is_not_callable_declaration(self):
        _, _, result = flow(
            {"api.py": FLASK + '@app.before_request\ndef auth(): pass\n@app.route("/x")\ndef handler(): pass\n'}
        )
        proof = applied(result)[0].evidence[0]
        self.assertEqual((proof.location.start_line, proof.location.end_line), (3, 3))
        self.assertEqual(dict(proof.metadata)["order_scope"], "file_app")

    def test_pre_handler_identity_and_route_containment_are_checked(self):
        from arctrellis.frameworks import FrameworkResolutionInvariantError, resolve_framework_flow

        index, imports, calls, endpoints = analyze(
            {
                "api.py": FASTAPI
                + 'def auth(): pass\n@app.get("/x", dependencies=[Depends(auth)])\ndef handler(): pass\n'
            }
        )
        p = index.pre_handler_observations[0]
        with self.assertRaises(ValueError):
            replace(index, pre_handler_observations=(replace(p, id="wrong"),))
        with self.assertRaises(ValueError):
            replace(index, file_results=(replace(index.file_results[0], pre_handler_observation_count=0),))
        calls.graph.add_relationship(replace(calls.graph.relationships()[0], id="extra"))
        with self.assertRaises(FrameworkResolutionInvariantError):
            resolve_framework_flow(index, imports, calls, endpoints)
