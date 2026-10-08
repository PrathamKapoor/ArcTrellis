"""Static composition preserves local facts and carries all contributing proof."""

import unittest

from arctrellis.core import Confidence, RelationshipKind
from tests.frameworks.test_flow import EXPRESS, applied, flow

FASTAPI_ROUTER = "from fastapi import APIRouter, Depends, FastAPI\n"


def effective(result):
    return [e for e in result.endpoints if dict(e.metadata)["path_completeness"] == "effective"]


class RouterCompositionTests(unittest.TestCase):
    def test_http_join_contract_preserves_root_trailing_slashes_and_parameters(self):
        from arctrellis.frameworks import join_http_paths

        for prefix, route, expected in [
            ("", "/users", "/users"),
            ("/api", "/users", "/api/users"),
            ("/api/", "/users", "/api/users"),
            ("/api", "/", "/api/"),
            ("", "/", "/"),
            ("/", "/", "/"),
            ("/api", "/{id}", "/api/{id}"),
        ]:
            with self.subTest(prefix=prefix, route=route):
                self.assertEqual(join_http_paths(prefix, route), expected)

    def test_fastapi_prefix_without_mount_preserves_local_endpoint(self):
        _, _, result = flow(
            {
                "api.py": FASTAPI_ROUTER + 'router = APIRouter(prefix="/users")\n'
                '@router.get("/{id}")\ndef handler(): pass\n'
            }
        )
        self.assertEqual([e.name for e in effective(result)], ["GET /users/{id}"])
        self.assertEqual([e.name for e in result.local_endpoints], ["GET /{id}"])
        self.assertEqual(len(result.router_prefix_observations), 1)

    def test_fastapi_include_composes_both_prefixes(self):
        _, _, result = flow(
            {
                "api.py": FASTAPI_ROUTER + 'router = APIRouter(prefix="/payments")\n'
                '@router.post("/")\ndef handler(): pass\napp = FastAPI()\napp.include_router(router, prefix="/api")\n'
            }
        )
        self.assertEqual([e.name for e in effective(result)], ["POST /api/payments/"])
        self.assertEqual(len(result.local_endpoints), 1)
        self.assertEqual(result.resolved_mount_count, 1)
        edge = result.graph.outgoing(effective(result)[0].id, kind=RelationshipKind.EXPOSES)[0]
        self.assertEqual((edge.confidence, edge.confidence_score), (Confidence.PROVEN, 1.0))
        methods = {e.analysis_method for e in edge.evidence}
        self.assertIn("fastapi_router_prefix", methods)
        self.assertIn("fastapi_router_mount", methods)
        self.assertIn("fastapi_decorated_handler", methods)
        self.assertTrue(all(e.location.file_path == "api.py" for e in edge.evidence))

    def test_fastapi_no_prefix_and_empty_mount_do_not_duplicate_same_path(self):
        for mount in ("", "app = FastAPI()\napp.include_router(router)\n"):
            with self.subTest(mount=mount):
                _, _, result = flow(
                    {
                        "api.py": FASTAPI_ROUTER + "router = APIRouter()\n"
                        '@router.get("/users")\ndef handler(): pass\n' + mount
                    }
                )
                self.assertFalse(effective(result))
                self.assertEqual(len(result.endpoints), 1)

    def test_fastapi_multiple_and_duplicate_mounts_remain_distinct(self):
        _, _, result = flow(
            {
                "api.py": FASTAPI_ROUTER + "router = APIRouter()\n"
                '@router.get("/users")\ndef handler(): pass\napp = FastAPI()\n'
                'app.include_router(router, prefix="/api")\napp.include_router(router, prefix="/api")\n'
                'app.include_router(router, prefix="/legacy")\n'
            }
        )
        values = effective(result)
        self.assertEqual(sorted(e.name for e in values), ["GET /api/users", "GET /api/users", "GET /legacy/users"])
        self.assertEqual(len({e.id for e in values}), 3)

    def test_fastapi_dynamic_constructor_and_mount_prefix_create_no_effective_endpoint(self):
        for prefix, mount in [("prefix", '"/api"'), ('"/users"', "prefix")]:
            with self.subTest(prefix=prefix):
                _, _, result = flow(
                    {
                        "api.py": FASTAPI_ROUTER + f"router = APIRouter(prefix={prefix})\n"
                        '@router.get("/x")\ndef handler(): pass\napp = FastAPI()\n'
                        f"app.include_router(router, prefix={mount})\n"
                    }
                )
                self.assertFalse(effective(result))
                self.assertEqual(len(result.local_endpoints), 1)
                self.assertEqual(result.mount_resolutions[0].status.value, "unsupported")

    def test_fastapi_dependency_and_handler_proofs_survive_effective_trace(self):
        _, _, result = flow(
            {
                "api.py": FASTAPI_ROUTER
                + 'def auth(): pass\ndef validate(): pass\nrouter = APIRouter(prefix="/payments")\n'
                '@router.post("/", dependencies=[Depends(auth)])\ndef handler(): validate()\n'
                'app = FastAPI()\napp.include_router(router, prefix="/api")\n'
            }
        )
        endpoint = effective(result)[0]
        middleware = result.graph.outgoing(endpoint.id, kind=RelationshipKind.APPLIES_MIDDLEWARE)[0]
        self.assertEqual(result.graph.get_entity(middleware.target_entity_id).name, "auth")
        self.assertEqual(middleware.confidence_score, 0.85)
        self.assertGreaterEqual(len(middleware.evidence), 3)
        target = next(e for e in result.graph.entities() if e.name == "validate")
        path = result.graph.shortest_path(
            endpoint.id, target.id, relationship_kinds={RelationshipKind.EXPOSES, RelationshipKind.CALLS}
        )
        self.assertEqual([r.kind for r in path.relationships], [RelationshipKind.EXPOSES, RelationshipKind.CALLS])

    def test_nested_router_cycles_are_explicitly_unsupported_and_terminate(self):
        _, _, result = flow(
            {
                "api.py": FASTAPI_ROUTER + "a = APIRouter()\nb = APIRouter()\n"
                '@a.get("/x")\ndef handler(): pass\na.include_router(b)\nb.include_router(a)\n'
            }
        )
        self.assertFalse(effective(result))
        self.assertEqual([r.status.value for r in result.mount_resolutions], ["unsupported", "unsupported"])

    def test_express_mount_retains_handler_and_route_middleware(self):
        _, _, result = flow(
            {
                "app.ts": EXPRESS + "const router = express.Router();\n"
                'function auth(){} function handler(){}\nrouter.get("/users", auth, handler);\napp.use("/api",router);'
            }
        )
        endpoint = effective(result)[0]
        self.assertEqual(endpoint.name, "GET /api/users")
        self.assertEqual(len(result.local_endpoints), 1)
        exposes = result.graph.outgoing(endpoint.id, kind=RelationshipKind.EXPOSES)[0]
        middleware = result.graph.outgoing(endpoint.id, kind=RelationshipKind.APPLIES_MIDDLEWARE)[0]
        self.assertEqual((exposes.confidence_score, middleware.confidence_score), (0.85, 0.85))
        self.assertEqual(result.graph.get_entity(middleware.target_entity_id).name, "auth")
        self.assertGreater(len(exposes.evidence), 1)
        self.assertEqual(len(applied(result)), 2)

    def test_express_multiple_mounts_and_trailing_join(self):
        _, _, result = flow(
            {
                "app.js": EXPRESS + "const router = express.Router();\n"
                'function handler(){} router.get("/",handler); app.use("/api/",router); app.use("/legacy",router);'
            }
        )
        self.assertEqual(sorted(e.name for e in effective(result)), ["GET /api/", "GET /legacy/"])

    def test_express_use_function_or_dynamic_prefix_is_not_static_mount(self):
        for call in (
            'app.use("/x",handler);',
            "app.use(handler);",
            "app.use(prefix,router);",
            'app.use("/x",factory());',
            'app.use("/x",router,handler);',
        ):
            with self.subTest(call=call):
                _, _, result = flow(
                    {
                        "app.js": EXPRESS + "const router = express.Router();\n"
                        'function handler(){} router.get("/users",handler);' + call
                    }
                )
                self.assertFalse(effective(result))

    def test_fake_or_rebound_router_never_composes(self):
        for router in ("const router = custom();", "const router = express.Router(); router = custom();"):
            with self.subTest(router=router):
                _, _, result = flow(
                    {
                        "app.js": EXPRESS
                        + router
                        + 'function handler(){} router.get("/users",handler); app.use("/api",router);'
                    }
                )
                self.assertFalse(effective(result))

    def test_cross_file_router_mounts_deferred_without_canonical_router_declarations(self):
        _, _, result = flow(
            {
                "routes.py": FASTAPI_ROUTER + 'router = APIRouter()\n@router.get("/x")\ndef handler(): pass\n',
                "app.py": "from fastapi import FastAPI\nfrom routes import router\napp = FastAPI()\n"
                'app.include_router(router,prefix="/api")\n',
            }
        )
        self.assertFalse(effective(result))
        self.assertEqual(result.unresolved_mount_count, 1)

    def test_repeated_full_flow_is_deterministic_and_base_unchanged(self):
        sources = {
            "app.js": EXPRESS + "const router = express.Router(); function auth(){} function handler(){}"
            'router.get("/users",auth,handler); app.use("/api",router);'
        }
        index, base, first = flow(sources)
        _, _, second = flow(sources)
        self.assertEqual(first.mount_resolutions, second.mount_resolutions)
        self.assertEqual(first.router_mount_observations, second.router_mount_observations)
        self.assertEqual(first.endpoints, second.endpoints)
        self.assertEqual(first.graph.relationships(), second.graph.relationships())
        self.assertEqual(len(base.endpoints), 1)
        self.assertEqual(index.router_observation_count, 2)

    def test_fastapi_mount_only_includes_routes_registered_before_include(self):
        _, _, result = flow(
            {
                "api.py": FASTAPI_ROUTER + "router = APIRouter()\n"
                "app = FastAPI()\n"
                'app.include_router(router, prefix="/api")\n'
                '@router.get("/late")\n'
                "def handler(): pass\n"
            }
        )
        self.assertEqual(result.resolved_mount_count, 1)
        self.assertEqual(len(result.local_endpoints), 1)
        self.assertFalse(effective(result))

    def test_router_and_app_constructor_aliases_are_supported(self):
        _, _, result = flow(
            {
                "api.py": "from fastapi import APIRouter as R, FastAPI as A\n"
                'router = R(prefix="/users")\n'
                '@router.get("/")\n'
                "def handler(): pass\n"
                "app = A()\n"
                'app.include_router(router, prefix="/api")\n'
            }
        )
        self.assertEqual([e.name for e in effective(result)], ["GET /api/users/"])

    def test_commonjs_express_mount_is_static_and_preserves_unresolved_handler(self):
        _, _, result = flow(
            {
                "api.cjs": 'const express = require("express"); '
                "const app = express(); "
                "const router = express.Router(); "
                'router.get("/users", unknown); '
                'app.use("/api", router);'
            }
        )
        self.assertEqual([e.name for e in effective(result)], ["GET /api/users"])
        self.assertFalse(result.graph.outgoing(effective(result)[0].id, kind=RelationshipKind.EXPOSES))

    def test_mounting_module_owns_effective_and_every_proof_survives(self):
        _, _, result = flow(
            {
                "api.py": FASTAPI_ROUTER + 'router = APIRouter(prefix="/users")\n'
                '@router.get("/")\n'
                "def handler(): pass\n"
                "app = FastAPI()\n"
                'app.include_router(router, prefix="/api")\n'
            }
        )
        endpoint = effective(result)[0]
        defines = result.graph.incoming(endpoint.id, kind=RelationshipKind.DEFINES)[0]
        self.assertEqual(defines.source_entity_id, endpoint.parent_id)
        self.assertEqual((defines.confidence, defines.confidence_score), (Confidence.PROVEN, 1.0))
        self.assertGreaterEqual(len(defines.evidence), 4)
        self.assertEqual(dict(endpoint.metadata)["composition_scope"], "application")

    def test_router_records_are_frozen_and_index_does_not_retain_source(self):
        from dataclasses import FrozenInstanceError, fields, is_dataclass, replace

        index, _, result = flow(
            {
                "api.ts": EXPRESS + "const router=express.Router(); "
                'function handler(){} router.get("/x",handler); '
                'app.use("/api",router);'
            }
        )
        prefix = index.router_prefix_observations[0]
        hash(prefix)
        hash(index.router_mount_observations[0])
        with self.assertRaises(FrozenInstanceError):
            prefix.prefix = "/changed"
        with self.assertRaises(ValueError):
            replace(index, router_prefix_observations=(replace(prefix, id="wrong"),))
        with self.assertRaises(ValueError):
            replace(index, file_results=(replace(index.file_results[0], router_observation_count=0),))
        pending = [index, result]
        while pending:
            obj = pending.pop()
            self.assertNotIsInstance(obj, bytes)
            self.assertNotIn(type(obj).__name__, ("ParsedSource", "SyntaxNode"))
            if is_dataclass(obj):
                pending.extend(getattr(obj, f.name) for f in fields(obj))
            elif isinstance(obj, tuple):
                pending.extend(obj)

    def test_composition_never_reopens_sources(self):
        from unittest.mock import patch

        from arctrellis.frameworks import resolve_framework_flow
        from tests.frameworks.test_endpoints import analyze

        index, imports, calls, endpoints = analyze(
            {
                "api.js": EXPRESS + "const router=express.Router(); "
                'function handler(){} router.get("/x",handler); '
                'app.use("/api",router);'
            }
        )
        with patch("builtins.open", side_effect=AssertionError("source reread")):
            result = resolve_framework_flow(index, imports, calls, endpoints)
        self.assertEqual(len(result.effective_endpoints), 1)

    def test_partial_and_failed_router_files_are_accounted(self):
        from unittest.mock import patch

        from arctrellis.frameworks import FrameworkExtractionError, extract_router_observations

        def fail_one(parsed, extracted):
            if parsed.path == "bad.js":
                raise FrameworkExtractionError("untrusted source text")
            return extract_router_observations(parsed, extracted)

        with patch("arctrellis.indexing.repository.extract_router_observations", side_effect=fail_one):
            index, _, result = flow(
                {
                    "api.py": FASTAPI_ROUTER
                    + 'router=APIRouter(prefix="/api")\n@router.get("/x")\ndef handler(): pass\ndef broken(:\n',
                    "bad.js": "function bad(){}",
                }
            )
        self.assertEqual(index.partial_file_count, 1)
        self.assertEqual(index.failed_file_count, 1)
        self.assertEqual(index.file_results[1].router_observation_count, 0)
        self.assertNotIn("untrusted source", index.file_results[1].error_message)
        self.assertEqual(len(result.effective_endpoints), 1)

    def test_dynamic_prefix_does_not_hide_registration_fact(self):
        _, _, result = flow(
            {
                "api.py": FASTAPI_ROUTER + 'router=APIRouter(prefix="/users")\n'
                '@router.get("/x")\n'
                "def handler(): pass\n"
                "app=FastAPI()\n"
                "app.include_router(router, prefix=dynamic)\n"
            }
        )
        self.assertFalse(result.effective_endpoints)
        self.assertEqual(len(result.local_endpoints), 1)
        self.assertEqual(result.mount_resolutions[0].status.value, "unsupported")

    def test_fastapi_invalid_trailing_prefix_does_not_fabricate_effective_path(self):
        for constructor_prefix, mount_prefix in (("/users/", "/api"), ("/users", "/api/")):
            with self.subTest(constructor=constructor_prefix, mount=mount_prefix):
                _, _, result = flow(
                    {
                        "api.py": FASTAPI_ROUTER + f'router=APIRouter(prefix="{constructor_prefix}")\n'
                        f'@router.get("/x")\n'
                        f"def handler(): pass\n"
                        f"app=FastAPI()\n"
                        f'app.include_router(router, prefix="{mount_prefix}")\n'
                    }
                )
                self.assertFalse(result.effective_endpoints)
                self.assertEqual(len(result.local_endpoints), 1)
                self.assertEqual(result.mount_resolutions[0].status.value, "unsupported")

    def test_multiple_leading_route_slashes_are_not_normalized_into_effective_facts(self):
        _, _, result = flow(
            {
                "api.py": FASTAPI_ROUTER + 'router=APIRouter(prefix="/users")\n'
                '@router.get("//x")\n'
                "def handler(): pass\n"
                "app=FastAPI()\n"
                'app.include_router(router, prefix="/api")\n'
            }
        )
        self.assertFalse(result.effective_endpoints)
        self.assertEqual(result.local_endpoints[0].name, "GET //x")
