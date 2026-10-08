"""Reproducible static multi-framework flow smoke; target source is never run."""

from arctrellis.core import RelationshipKind
from arctrellis.frameworks import resolve_framework_flow

from .test_endpoints import analyze


def sources() -> dict[str, str]:
    return {
        "fastapi_app.py": "from fastapi import APIRouter, Depends, FastAPI\n"
        "def authenticate(): pass\n"
        "def validate(): pass\n"
        'router = APIRouter(prefix="/payments")\n'
        '@router.post("/", dependencies=[Depends(authenticate)])\n'
        "def create_payment():\n    validate()\n"
        "app = FastAPI()\n"
        'app.include_router(router, prefix="/api")\n',
        "flask_app.py": "from flask import Flask\n"
        "app = Flask(__name__)\n"
        "@app.before_request\ndef authenticate(): pass\n"
        '@app.route("/health")\ndef health(): return "ok"\n',
        "express_app.ts": 'import express from "express";\n'
        "const app = express();\nconst router = express.Router();\n"
        "function auth(req, res, next) {}\nfunction service() {}\n"
        "function handler(req, res) { service(); }\n"
        'router.get("/users", auth, handler);\napp.use("/api", router);\n',
    }


def _flow(source: dict[str, str]):
    index, imports, calls, endpoints = analyze(source)
    return index, resolve_framework_flow(index, imports, calls, endpoints)


def false_positives() -> None:
    cases = {
        "fake FastAPI-like object": (
            'class Fake: pass\napp=Fake()\n@app.get("/x")\ndef handler(): pass\n',
            "py",
        ),
        "custom Depends": (
            "from fastapi import FastAPI\nfrom custom import Depends\napp=FastAPI()\n"
            'def auth(): pass\n@app.get("/x", dependencies=[Depends(auth)])\ndef handler(): pass\n',
            "py",
        ),
        "fake Flask app": (
            "class Fake: pass\napp=Fake()\n@app.before_request\ndef auth(): pass\n"
            '@app.route("/x")\ndef handler(): pass\n',
            "py",
        ),
        "custom Express factory": (
            'const app=customFactory(); function auth(){} function handler(){} app.get("/x",auth,handler);',
            "js",
        ),
        "normal function use is not router": (
            'import express from "express"; const app=express(); function auth(){} app.use("/x",auth);',
            "js",
        ),
        "dynamic prefix": (
            'import express from "express"; const app=express(); const router=express.Router();'
            'function handler(){} router.get("/x",handler); app.use(prefix,router);',
            "js",
        ),
        "dynamic middleware factory": (
            'import express from "express"; const app=express(); function handler(){}'
            'app.get("/x", makeMiddleware(), handler);',
            "js",
        ),
    }
    for label, (source, suffix) in cases.items():
        _, result = _flow({"negative." + suffix: source})
        assert not result.effective_endpoints
        assert not any(r.kind is RelationshipKind.APPLIES_MIDDLEWARE for r in result.graph.relationships())
        if label in ("fake FastAPI-like object", "fake Flask app", "custom Express factory"):
            assert not result.endpoints
        if label == "custom Depends":
            assert not result.pre_handler_observations
        print(label + ": rejected")


def main() -> None:
    index, result = _flow(sources())
    repeated_index, repeated = _flow(sources())
    print("Route observations:", len(result.route_observations))
    print("Local endpoints:", len(result.local_endpoints))
    print("Effective endpoints:", len(result.effective_endpoints))
    print("Pre-handler observations:", len(result.pre_handler_observations))
    print("Resolved pre-handlers:", result.resolved_pre_handler_count)
    print("Unresolved pre-handlers:", result.unresolved_pre_handler_count)
    print("Ambiguous pre-handlers:", result.ambiguous_pre_handler_count)
    for kind in (RelationshipKind.APPLIES_MIDDLEWARE, RelationshipKind.EXPOSES):
        print(kind.value + " edges:", sum(r.kind is kind for r in result.graph.relationships()))
    deterministic = (
        index.pre_handler_observations == repeated_index.pre_handler_observations
        and index.router_prefix_observations == repeated_index.router_prefix_observations
        and index.router_mount_observations == repeated_index.router_mount_observations
        and result.pre_handler_resolutions == repeated.pre_handler_resolutions
        and result.mount_resolutions == repeated.mount_resolutions
        and result.graph.entities() == repeated.graph.entities()
        and result.graph.relationships() == repeated.graph.relationships()
    )
    assert deterministic
    print("Deterministic:", deterministic)
    endpoint = next(e for e in result.effective_endpoints if e.name == "POST /api/payments/")
    target = next(e for e in result.graph.entities() if e.name == "validate")
    path = result.graph.shortest_path(endpoint.id, target.id)
    assert path is not None
    edges = result.graph.outgoing(endpoint.id, kind=RelationshipKind.APPLIES_MIDDLEWARE) + path.relationships
    for edge in edges:
        source = result.graph.get_entity(edge.source_entity_id)
        callee = result.graph.get_entity(edge.target_entity_id)
        print(source.name, edge.kind.value, callee.name)
        for proof in edge.evidence:
            print(
                f"  {proof.location.file_path}:{proof.location.start_line}-{proof.location.end_line} "
                f"method={proof.analysis_method} confidence={edge.confidence.value} score={edge.confidence_score}"
            )
    false_positives()


if __name__ == "__main__":
    main()
