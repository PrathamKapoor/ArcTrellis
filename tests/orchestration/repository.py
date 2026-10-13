"""Untrusted synthetic repositories for orchestration tests.

Nothing in this module is imported, executed, installed or compiled by
ArcTrellis. The strings below exist only as static source text for the existing
safe discovery and analysis pipeline.

The fixtures deliberately include the negative cases the orchestration contract
must handle: duplicate endpoint registrations, a same-name CLASS and IMPORT,
unresolved and ambiguous calls, a fake ORM object that is not a supported
provider, a staged SQLAlchemy mutation, a route with no known database path and a
partially parsed source file.
"""

from __future__ import annotations

from arctrellis.orchestration import AnalysisSnapshot, analyze_repository

PAYMENTS = {
    "app.py": """from fastapi import FastAPI
from payments import PaymentService, createPayment, listAllPayments
app = FastAPI()
service = PaymentService()
@app.post("/payments")
def createPaymentRoute():
    return createPayment()
@app.get("/payments")
def listPaymentsRoute():
    return listAllPayments()
@app.post("/refunds")
def createRefundRoute():
    return service.createRefund()
@app.delete("/payments/{paymentId}")
def deletePaymentRoute():
    return {"deleted": True}
@app.get("/reports")
def reportRoute():
    return {"rows": 0}
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

EXPRESS = {
    "js/app.js": """import express from "express";
import { PrismaClient } from "@prisma/client";
import { persistPayment } from "./service.js";
const app = express();
const db = new PrismaClient();
function auditPayment() { return db.paymentAudit.create({data:{}}); }
function readPayments() { return db.payment.findMany(); }
function missingHandler() { return unknownService(); }
function fakePaymentWrite() { return customClient().payment.create({}); }
app.post("/payments", auditPayment, persistPayment);
app.get("/payments", readPayments);
app.post("/ghost", missingHandler);
app.post("/fake", fakePaymentWrite);
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
app.post("/ts-payments", persistPaymentRoute);
app.post("/ts-payments", persistPaymentRoute);
""",
    "ts/service.ts": """import { PrismaClient } from "@prisma/client";
const db = new PrismaClient();
export function persistPayment(): unknown {
    return db.payment.create({data:{amount:100}});
}
""",
}

#: One module defining ``handler`` twice produces two canonical FUNCTION entities
#: with the same qualified name, which is the duplicate-identity case.
DUPLICATE_QUALIFIED_NAMES = {
    "js/dup.js": """export function handler() { return 1; }
export function handler() { return 2; }
""",
    "js/other.js": """export function handler() { return 3; }
""",
}

#: A syntactically incomplete module. Indexing must keep it as a partial file and
#: must not report the repository as completely analyzed.
PARTIAL_SOURCE = {
    "good.py": """def goodFunction():
    return 1
""",
    "broken.py": """def broken(:
    return
""",
}

#: No framework, no ORM and no database operation of any kind.
PLAIN_SOURCE = {
    "lib.py": """def helper(value):
    return value + 1
""",
}

MIXED = {**PAYMENTS, **EXPRESS, **TYPESCRIPT}


def write_sources(root, sources) -> None:
    for name, text in sources.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def analyze(root, sources) -> AnalysisSnapshot:
    """Write an untrusted fixture and analyze it through the public entry point."""
    write_sources(root, sources)
    return analyze_repository(root)
