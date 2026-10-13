"""Synthetic mixed-language repositories as untrusted static data for retrieval.

The strings below are never imported, executed, installed or compiled. The only
thing ArcTrellis does with them is the existing safe static analysis pipeline,
followed by retrieval over the resulting graph.
"""

from arctrellis.calls import resolve_calls
from arctrellis.database import materialize_database_graph
from arctrellis.frameworks import resolve_framework_flow, resolve_http_endpoints
from arctrellis.indexing import index_repository
from arctrellis.query import AnalysisSummary
from arctrellis.resolution import resolve_imports
from arctrellis.test_semantics import analyze_tests

PYTHON = {
    "app.py": """from fastapi import FastAPI
from payments import PaymentService, createPayment, deletePayment, listAllPayments
app = FastAPI()
service = PaymentService()
@app.post("/payments")
def createPayment():
    return service.createPayment()
@app.get("/payments")
def listPayments():
    return listAllPayments()
@app.delete("/payments/{paymentId}")
def deletePayment():
    return service.deletePayment()
@app.post("/refunds")
def createRefund():
    return service.createRefund()
""",
    "payments.py": """from sqlalchemy.orm import Session
from sqlalchemy import insert, select
def createPayment():
    db = Session(engine)
    return db.execute(insert(Payment))
def listPayments():
    db = Session(engine)
    return db.execute(select(Payment))
def listAllPayments():
    return listPayments()
def stagePayment():
    db = Session(engine)
    db.add(Payment)
    db.commit()
class PaymentService:
    def createPayment(self):
        return createPayment()
    def listPayments(self):
        return listPayments()
    def deletePayment(self):
        return stagePayment()
    def createRefund(self):
        return createPayment()
""",
    "test_payments.py": """from payments import createPayment, listPayments
def test_create_payment():
    createPayment()
def test_list_payments():
    listPayments()
""",
}

JAVASCRIPT = {
    "js/app.js": """import express from "express";
import { PrismaClient } from "@prisma/client";
import { persistPayment } from "./service.js";
const app = express();
const db = new PrismaClient();
function auditPayment() { return db.paymentAudit.create({data:{}}); }
function persistPaymentLocal() { return persistPayment(); }
function readPayments() { return db.payment.findMany(); }
function missingHandler() { return unknownService(); }
app.post("/payments", auditPayment, persistPaymentLocal);
app.get("/payments", readPayments);
app.post("/ghost", missingHandler);
const fake = customClient();
function fakePaymentWrite() { return fake.payment.create({}); }
""",
    "js/service.js": """import { PrismaClient } from "@prisma/client";
const db = new PrismaClient();
export function persistPayment() {
    return db.payment.create({data:{amount:100}});
}
""",
    "js/service.test.js": """import { persistPayment } from "./service.js";
test("persists a payment", () => { persistPayment(); });
""",
}

TYPESCRIPT = {
    "ts/app.ts": """import express from "express";
import { persistPayment } from "./service.ts";
const app = express();
function persistPaymentRoute(): unknown { return persistPayment(); }
function refundPayment(): unknown { return persistPayment(); }
app.post("/payments", persistPaymentRoute);
app.post("/payments", persistPaymentRoute);
app.post("/refunds", refundPayment);
""",
    "ts/service.ts": """import { PrismaClient } from "@prisma/client";
const db = new PrismaClient();
export function persistPayment(): unknown {
    return db.payment.create({data:{amount:100}});
}
""",
    "ts/service.test.ts": """import { persistPayment } from "./service.ts";
test("persists a payment", () => { persistPayment(); });
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


def analysis_context(index):
    return AnalysisSummary(index.complete_file_count, index.partial_file_count, index.failed_file_count).completeness
