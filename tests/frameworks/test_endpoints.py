"""Public framework contracts over real normalized and repository pipelines."""

import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from arctrellis.calls import resolve_calls
from arctrellis.core import Confidence, RelationshipKind
from arctrellis.extraction import extract_entities
from arctrellis.frameworks import (
    EndpointResolutionStatus,
    Framework,
    extract_framework_observations,
    resolve_http_endpoints,
)
from arctrellis.indexing import index_repository
from arctrellis.ingestion import Language
from arctrellis.parsing import parse_source
from arctrellis.resolution import resolve_imports


def analyze(sources):
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for path, source in sources.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source, encoding="utf-8")
        index = index_repository(root)
        imports = resolve_imports(index)
        calls = resolve_calls(index, imports)
        endpoints = resolve_http_endpoints(index, imports, calls)
        return index, imports, calls, endpoints


class FrameworkContracts(unittest.TestCase):
    def test_fastapi_verbs_alias_async_and_evidence(self):
        for verb in ("get", "post", "put", "patch", "delete", "options", "head"):
            with self.subTest(verb=verb):
                index, _, calls, result = analyze(
                    {
                        "api.py": "from fastapi import FastAPI as API\napp = API()\n"
                        f'@app.{verb}("/payments")\nasync def create(): pass\n'
                    }
                )
                self.assertEqual(result.endpoint_count, 1)
                self.assertEqual(result.resolved_handler_count, 1)
                endpoint = result.endpoints[0]
                self.assertEqual(endpoint.name, verb.upper() + " /payments")
                self.assertEqual(endpoint.parent_id, index.route_observations[0].owner_module_id)
                self.assertEqual(dict(endpoint.metadata)["framework"], "fastapi")
                edges = [
                    e for e in result.graph.relationships() if e.id not in {r.id for r in calls.graph.relationships()}
                ]
                self.assertEqual({e.kind for e in edges}, {RelationshipKind.DEFINES, RelationshipKind.EXPOSES})
                for edge in edges:
                    self.assertEqual((edge.confidence, edge.confidence_score), (Confidence.PROVEN, 1.0))
                    self.assertEqual(edge.evidence[0].location.file_path, "api.py")
                    self.assertEqual(edge.evidence[0].location.start_line, 3)
                    self.assertEqual(edge.evidence[0].location.end_line, 3)
                    self.assertEqual(
                        dict(edge.evidence[0].metadata)["start_byte"], str(index.route_observations[0].span.start_byte)
                    )

    def test_router_paths_remain_local_and_mounts_are_not_routes(self):
        _, _, _, result = analyze(
            {
                "api.py": "from fastapi import FastAPI, APIRouter\napp = FastAPI()\n"
                'router = APIRouter(prefix="/users")\n@router.get("/{id}")\n'
                'def read(): pass\napp.include_router(router, prefix="/v1")\n'
            }
        )
        self.assertEqual([e.name for e in result.endpoints], ["GET /{id}"])
        self.assertEqual(dict(result.endpoints[0].metadata)["path_completeness"], "local")

    def test_flask_default_and_explicit_methods_without_runtime_expansion(self):
        for suffix, names in (
            ("", ["GET /x"]),
            (', methods=["POST", "GET"]', ["GET /x", "POST /x"]),
            (', methods=("PATCH",)', ["PATCH /x"]),
            (', methods={"DELETE"}', ["DELETE /x"]),
        ):
            with self.subTest(suffix=suffix):
                _, _, _, result = analyze(
                    {
                        "api.py": "from flask import Flask as Application\napp = Application(__name__)\n"
                        f'@app.route("/x"{suffix})\ndef handler(): pass\n'
                    }
                )
                self.assertEqual(sorted(e.name for e in result.endpoints), names)
                self.assertEqual(result.resolved_handler_count, 1)
                self.assertEqual(
                    len([r for r in result.graph.relationships() if r.kind is RelationshipKind.EXPOSES]), len(names)
                )

    def test_express_import_forms_router_languages_and_verbs(self):
        for path in ("api.js", "api.ts", "api.tsx"):
            for constructor in ('import express from "express";', 'const express = require("express");'):
                for receiver in ("express()", "express.Router()"):
                    for verb in ("get", "post", "put", "patch", "delete", "options", "head"):
                        with self.subTest(path=path, receiver=receiver, verb=verb, constructor=constructor):
                            _, _, _, result = analyze(
                                {path: constructor + f'\nlet app = {receiver};\nfunction h(){{}}\napp.{verb}("/x", h);'}
                            )
                            self.assertEqual(result.endpoint_count, 1)
                            exposes = [r for r in result.graph.relationships() if r.kind is RelationshipKind.EXPOSES]
                            self.assertEqual(len(exposes), 1)
                            self.assertEqual(
                                (exposes[0].confidence, exposes[0].confidence_score), (Confidence.LIKELY, 0.85)
                            )

    def test_fake_frameworks_and_rebound_constructor_or_receiver_are_rejected(self):
        sources = [
            (
                "a.py",
                'class Router:\n def get(self, x): pass\nrouter = Router()\n@router.get("/fake")\ndef fake(): pass\n',
            ),
            ("a.py", 'class App:\n def route(self, x): pass\napp = App()\n@app.route("/fake")\ndef fake(): pass\n'),
            ("a.js", 'const app = customFactory(); function h(){} app.get("/fake", h);'),
            ("a.py", 'from unrelated import FastAPI\napp=FastAPI()\n@app.get("/fake")\ndef fake(): pass\n'),
            ("a.py", 'from fastapi import FastAPI\nFastAPI=Fake\napp=FastAPI()\n@app.get("/fake")\ndef fake(): pass\n'),
            ("a.py", 'from fastapi import FastAPI\napp=FastAPI()\napp=Fake()\n@app.get("/fake")\ndef fake(): pass\n'),
            (
                "a.js",
                'import express from "express"; express = fake; const app=express(); '
                'function h(){} app.get("/fake", h);',
            ),
            (
                "a.js",
                'import express from "express"; const app=express(); app=other; function h(){} app.get("/fake", h);',
            ),
        ]
        for path, source in sources:
            with self.subTest(source=source):
                index, _, _, result = analyze({path: source})
                self.assertEqual(index.route_observation_count, 0)
                self.assertEqual(result.endpoint_count, 0)

    def test_internal_module_named_like_framework_does_not_prove_runtime_framework(self):
        for dependency in ("def FastAPI(): return fake\n", "# coding: unknown_encoding\n"):
            with self.subTest(dependency=dependency):
                _, _, _, result = analyze(
                    {
                        "fastapi.py": dependency,
                        "api.py": 'from fastapi import FastAPI\napp=FastAPI()\n@app.get("/x")\ndef h(): pass\n',
                    }
                )
                self.assertEqual(result.endpoint_count, 0)
                self.assertEqual(result.resolutions[0].status, EndpointResolutionStatus.UNSUPPORTED)

    def test_shadowed_require_and_python_context_bindings_are_rejected(self):
        for path, source in (
            (
                "a.js",
                'function require(x){ return fake; } const express=require("express"); '
                'const app=express(); function h(){} app.get("/x",h);',
            ),
            (
                "a.py",
                "from fastapi import FastAPI\napp=FastAPI()\nwith manager() as app:\n pass\n"
                '@app.get("/x")\ndef h(): pass\n',
            ),
            (
                "a.py",
                "from fastapi import FastAPI\napp=FastAPI()\ntry:\n pass\nexcept Exception as app:\n pass\n"
                '@app.get("/x")\ndef h(): pass\n',
            ),
            (
                "a.py",
                "from fastapi import FastAPI\napp=FastAPI()\nmatch other:\n case app: pass\n"
                '@app.get("/x")\ndef h(): pass\n',
            ),
            (
                "a.py",
                'from fastapi import FastAPI\napp=FastAPI()\n(app := other)\n@app.get("/x")\ndef h(): pass\n',
            ),
        ):
            with self.subTest(path=path, source=source):
                _, _, _, result = analyze({path: source})
                self.assertEqual(result.endpoint_count, 0)

    def test_wildcard_conditional_import_and_class_import_shadows_are_not_framework_provenance(self):
        for source in (
            'from fastapi import FastAPI\nfrom fake import *\napp=FastAPI()\n@app.get("/x")\ndef h(): pass\n',
            'if condition:\n from fastapi import FastAPI\napp=FastAPI()\n@app.get("/x")\ndef h(): pass\n',
            "from fastapi import FastAPI\napp=FastAPI()\nclass C:\n from fake import app\n"
            ' @app.get("/x")\n def h(self): pass\n',
        ):
            with self.subTest(source=source):
                _, _, _, result = analyze({"a.py": source})
                self.assertEqual(result.endpoint_count, 0)

    def test_duplicate_option_keywords_do_not_prove_route_registration(self):
        for framework, constructor, registration in (
            ("fastapi", "FastAPI()", 'app.get("/x", status_code=200, status_code=404)'),
            ("flask", "Flask(__name__)", 'app.route("/x", endpoint="a", endpoint="b")'),
        ):
            with self.subTest(framework=framework):
                name = "FastAPI" if framework == "fastapi" else "Flask"
                _, _, _, result = analyze(
                    {"a.py": f"from {framework} import {name}\napp={constructor}\n@{registration}\ndef h(): pass\n"}
                )
                self.assertEqual(result.endpoint_count, 0)

    def test_shadowed_require_does_not_resolve_express_imported_handler(self):
        _, _, _, result = analyze(
            {
                "handlers.js": "export function h(){}",
                "a.js": 'import express from "express"; function require(x){return fake;} '
                'const handlers=require("./handlers"); const app=express(); app.get("/x",handlers.h);',
            }
        )
        self.assertEqual(result.endpoint_count, 1)
        self.assertEqual(result.unresolved_handler_count, 1)

    def test_invalid_argument_shapes_and_express_settings_getter_are_not_routes(self):
        for registration in (
            'app.get("/x", "extra")',
            'app.get("/x", path="/y")',
            'app.get(rule="/x")',
            'app.get("/x", **options)',
        ):
            with self.subTest(registration=registration):
                _, _, _, result = analyze(
                    {"a.py": f"from fastapi import FastAPI\napp=FastAPI()\n@{registration}\ndef h(): pass\n"}
                )
                self.assertEqual(result.endpoint_count, 0)
        for registration in ('app.get("/setting")', 'app.get("/x", 123, h)'):
            with self.subTest(registration=registration):
                _, _, _, result = analyze(
                    {"a.js": 'import express from "express"; const app=express(); function h(){} ' + registration + ";"}
                )
                self.assertEqual(result.endpoint_count, 0)

    def test_explicit_module_handler_rebinding_is_not_selected(self):
        _, _, _, result = analyze(
            {"a.js": 'import express from "express"; const app=express(); function h(){} h=other; app.get("/x",h);'}
        )
        self.assertEqual(result.endpoint_count, 1)
        self.assertEqual(result.unresolved_handler_count, 1)

    def test_block_only_handler_is_not_visible_at_module_registration(self):
        for declaration in ("{ let h=()=>{}; }", "{ function h(){} }"):
            with self.subTest(declaration=declaration):
                _, _, _, result = analyze(
                    {"a.js": 'import express from "express"; const app=express(); ' + declaration + ' app.get("/x",h);'}
                )
                self.assertEqual(result.endpoint_count, 1)
                self.assertEqual(result.unresolved_handler_count, 1)

    def test_dynamic_paths_and_method_lists_do_not_fabricate_endpoints(self):
        for expression in ("path", 'f"/{value}"', '"/x" + suffix', '"/escaped\\x2fx"'):
            with self.subTest(expression=expression):
                _, _, _, result = analyze(
                    {"api.py": f"from fastapi import FastAPI\napp=FastAPI()\n@app.get({expression})\ndef h(): pass\n"}
                )
                self.assertEqual(result.endpoint_count, 0)
                self.assertEqual(result.resolutions[0].status, EndpointResolutionStatus.UNSUPPORTED)
        _, _, _, result = analyze(
            {
                "api.py": "from flask import Flask\napp=Flask(__name__)\n"
                '@app.route("/x", methods=methods)\ndef h(): pass\n'
            }
        )
        self.assertEqual(result.endpoint_count, 0)

    def test_express_last_argument_middleware_and_inline_handlers(self):
        _, _, _, result = analyze(
            {
                "api.js": 'import express from "express"; const app=express();\n'
                "function auth(){} function handler(){}\n"
                'app.get("/x", auth, handler);\napp.post("/y", auth, (req,res)=>res.send("x"));\n'
                'app.use("/mounted", handler); app.route("/chain").get(handler);'
            }
        )
        self.assertEqual(
            (result.endpoint_count, result.resolved_handler_count, result.unresolved_handler_count), (2, 1, 1)
        )
        self.assertEqual(result.observations[0].pre_handler_argument_count, 1)
        exposes = [r for r in result.graph.relationships() if r.kind is RelationshipKind.EXPOSES]
        self.assertEqual(result.graph.get_entity(exposes[0].target_entity_id).name, "handler")
        self.assertFalse(any(r.kind is RelationshipKind.APPLIES_MIDDLEWARE for r in result.graph.relationships()))

    def test_express_imported_alias_and_namespace_handlers(self):
        for clause, reference in (
            ("{ handler }", "handler"),
            ("{ handler as serve }", "serve"),
            ("* as routes", "routes.handler"),
        ):
            with self.subTest(clause=clause):
                _, _, _, result = analyze(
                    {
                        "handlers.ts": "export function handler() {}",
                        "app.ts": f'import express from "express"; import {clause} from "./handlers";\n'
                        f'const app=express(); app.get("/x", {reference});',
                    }
                )
                self.assertEqual(result.resolved_handler_count, 1)
                edge = next(r for r in result.graph.relationships() if r.kind is RelationshipKind.EXPOSES)
                self.assertEqual((edge.confidence, edge.confidence_score), (Confidence.LIKELY, 0.75))
                self.assertEqual(result.graph.get_entity(edge.target_entity_id).qualified_name, "handlers.ts::handler")

    def test_ambiguous_unknown_default_and_type_only_handlers_have_no_edge(self):
        for prefix, reference, status in (
            ("function h(){} function h(){}", "h", EndpointResolutionStatus.AMBIGUOUS),
            ("", "missing", EndpointResolutionStatus.UNRESOLVED),
            ('import h from "./handlers";', "h", EndpointResolutionStatus.UNRESOLVED),
            ('import type {h} from "./handlers";', "h", EndpointResolutionStatus.UNRESOLVED),
        ):
            with self.subTest(prefix=prefix):
                _, _, _, result = analyze(
                    {
                        "handlers.ts": "export function h() {}",
                        "app.ts": 'import express from "express"; const app=express(); '
                        + prefix
                        + f' app.get("/x", {reference});',
                    }
                )
                self.assertEqual(result.endpoint_count, 1)
                self.assertEqual(result.resolutions[0].status, status)
                self.assertFalse(any(r.kind is RelationshipKind.EXPOSES for r in result.graph.relationships()))

    def test_duplicate_registrations_and_multiple_decorators_remain_distinct(self):
        _, _, _, result = analyze(
            {
                "api.py": 'from fastapi import FastAPI\napp=FastAPI()\n@app.get("/x")\n@app.post("/x")\ndef a(): pass\n'
                '@app.get("/x")\ndef b(): pass\n'
            }
        )
        self.assertEqual((result.observation_count, result.endpoint_count), (3, 3))
        self.assertEqual(len({e.id for e in result.endpoints}), 3)
        self.assertEqual(
            len({r.evidence[0].id for r in result.graph.relationships() if r.kind is RelationshipKind.EXPOSES}), 3
        )

    def test_final_nested_same_name_does_not_replace_decorated_handler(self):
        for body in (
            '@app.get("/x")\ndef h():\n def h(): pass\n',
            'class C:\n @app.get("/x")\n def h(self):\n  def h(): pass\n',
        ):
            with self.subTest(body=body):
                _, _, _, result = analyze({"a.py": "from fastapi import FastAPI\napp=FastAPI()\n" + body})
                self.assertEqual(result.resolved_handler_count, 1)
                edge = next(r for r in result.graph.relationships() if r.kind is RelationshipKind.EXPOSES)
                self.assertNotIn(".h.h", result.graph.get_entity(edge.target_entity_id).qualified_name)

    def test_observation_immutability_determinism_and_no_reextraction(self):
        parsed = parse_source(
            "api.py", Language.PYTHON, b'from fastapi import FastAPI\napp=FastAPI()\n@app.get("/x")\ndef h(): pass\n'
        )
        entities = extract_entities(parsed)
        with patch("arctrellis.extraction.extract_entities", side_effect=AssertionError("reextraction")):
            observations = extract_framework_observations(parsed, entities)
        self.assertEqual(observations, extract_framework_observations(parsed, entities))
        self.assertEqual(observations[0].framework, Framework.FASTAPI)
        hash(observations[0])
        with self.assertRaises(FrozenInstanceError):
            observations[0].route_path = "/other"

    def test_partial_failed_and_memory_boundary(self):
        index, _, _, result = analyze(
            {
                "api.py": 'from fastapi import FastAPI\napp=FastAPI()\n@app.get("/ok")\ndef ok(): pass\n'
                '@app.post("/broken")\ndef broken(:\n pass\n'
            }
        )
        self.assertFalse(index.is_complete)
        self.assertEqual([e.name for e in result.endpoints], ["GET /ok"])
        self.assertFalse(hasattr(index, "source"))
        self.assertFalse(hasattr(index, "parsed"))
        self.assertEqual(index.file_results[0].route_observation_count, index.route_observation_count)

    def test_trace_and_resolution_perform_no_source_reads_or_input_mutation(self):
        index, imports, calls, expected = analyze(
            {
                "api.py": "from fastapi import FastAPI\napp=FastAPI()\ndef validate(): pass\n"
                '@app.post("/payments")\ndef create():\n validate()\n'
            }
        )
        before = calls.graph.relationships()
        with (
            patch("builtins.open", side_effect=AssertionError("source reread")),
            patch.object(Path, "open", side_effect=AssertionError("source reread")),
        ):
            result = resolve_http_endpoints(index, imports, calls)
        self.assertEqual(result.resolutions, expected.resolutions)
        self.assertEqual(result.graph.relationships(), expected.graph.relationships())
        self.assertEqual(calls.graph.relationships(), before)
        endpoint = result.endpoints[0]
        target = next(e for e in result.graph.entities() if e.name == "validate")
        path = result.graph.shortest_path(endpoint.id, target.id)
        self.assertIsNotNone(path)
        self.assertEqual([r.kind for r in path.relationships], [RelationshipKind.EXPOSES, RelationshipKind.CALLS])
        self.assertEqual([r.evidence[0].location.start_line for r in path.relationships], [4, 6])


if __name__ == "__main__":
    unittest.main()
