"""Synthetic repositories as untrusted data; never import or execute these strings."""

from arctrellis.calls import resolve_calls
from arctrellis.database import materialize_database_graph
from arctrellis.frameworks import resolve_framework_flow, resolve_http_endpoints
from arctrellis.indexing import index_repository
from arctrellis.resolution import resolve_imports
from arctrellis.test_semantics import analyze_tests

PYTHON = {
    "app.py": """from fastapi import FastAPI
from payments import persist_payment, read_payment, stage_payment
app = FastAPI()
@app.post("/payments")
def create_payment():
    persist_payment()
@app.get("/payments")
def get_payment():
    read_payment()
@app.post("/staged")
def staged():
    stage_payment()
@app.get("/unknown")
def unresolved():
    unknown_service()
def duplicate():
    persist_payment()
def duplicate():
    read_payment()
@app.get("/ambiguous")
def ambiguous():
    duplicate()
def persistOrder():
    unknown_service()
fake = factory()
@fake.post("/fake")
def fake_handler():
    persist_payment()
""",
    "payments.py": """from sqlalchemy.orm import Session
from sqlalchemy import insert
def persist_payment():
    db = Session(engine)
    db.execute(insert(Payment))
def read_payment():
    db = Session(engine)
    return db.get(Payment, 1)
def stage_payment():
    db = Session(engine)
    db.add(payment)
    db.commit()
""",
    "test_payments.py": """from payments import persist_payment
def test_persist_payment():
    persist_payment()
def test_ambiguous():
    unknown_service()
""",
}

JAVASCRIPT = {
    "js/app.js": """import express from "express";
import { PrismaClient } from "@prisma/client";
import { persistOrder } from "./service.js";
const app = express();
const db = new PrismaClient();
function guard() { return db.audit.create({data:{}}); }
function createOrder() { return persistOrder(); }
function readOrder() { return db.order.findMany(); }
function empty() { return unknown(); }
app.post("/orders", guard, createOrder);
app.get("/orders", readOrder);
app.get("/empty", guard, empty);
app.get("/dynamic", choose());
const router = express.Router();
router.post("/local", createOrder);
app.use("/api", router);
const fake = customClient();
function fakeWrite() { return fake.order.create({}); }
""",
    "js/service.js": """import { PrismaClient } from "@prisma/client";
const db = new PrismaClient();
export function persistOrder() {
    return db.order.create({data:{amount:100}});
}
""",
    "js/service.test.js": """import { persistOrder } from "./service.js";
test("persists", () => { persistOrder(); });
test("dynamic", () => { handlers[name](); });
""",
}

TYPESCRIPT = {
    "ts/app.ts": """import express from "express";
import { persistOrder } from "./service.ts";
const app = express();
function createOrder(): unknown { return persistOrder(); }
app.post("/orders", createOrder);
app.post("/orders", createOrder);
""",
    "ts/service.ts": """import { PrismaClient } from "@prisma/client";
const db = new PrismaClient();
export function persistOrder(): unknown {
    return db.order.create({data:{amount:100}});
}
""",
    "ts/service.test.ts": """import { persistOrder } from "./service.ts";
test("persists", () => { persistOrder(); });
""",
}

MIXED = PYTHON | JAVASCRIPT | TYPESCRIPT


def write_repository(root, sources):
    for name, text in sources.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def pipeline(root):
    index = index_repository(root)
    imports = resolve_imports(index)
    calls = resolve_calls(index, imports)
    endpoints = resolve_http_endpoints(index, imports, calls)
    flow = resolve_framework_flow(index, imports, calls, endpoints)
    tests = analyze_tests(index, imports, calls, base_graph=flow.graph)
    database = materialize_database_graph(index, base_graph=tests.graph)
    return index, calls, tests, database
