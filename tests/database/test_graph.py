import unittest
from dataclasses import fields, is_dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from arctrellis.calls import resolve_calls
from arctrellis.core import Confidence, EntityKind
from arctrellis.core import RelationshipKind as RK
from arctrellis.database import materialize_database_graph
from arctrellis.frameworks import resolve_framework_flow, resolve_http_endpoints
from arctrellis.indexing import index_repository
from arctrellis.parsing import ParsedSource, SourceReadError, SyntaxNode
from arctrellis.resolution import resolve_imports
from arctrellis.test_semantics import analyze_tests

PYTHON = """from fastapi import FastAPI
from sqlalchemy.orm import Session
from sqlalchemy import insert, select, delete
app = FastAPI()
def persist_payment():
    db = Session(engine)
    db.execute(insert(Payment))
    db.add(payment)
    db.commit()
    db.execute(command)
    db.execute(delete(Payment))
@app.post("/payments")
def create_payment():
    persist_payment()
@app.get("/payments")
def read_payment():
    db = Session(engine)
    return db.get(Payment, 1)
def test_create_payment():
    create_payment()
"""
TYPESCRIPT = """import express from "express";
import { PrismaClient } from "@prisma/client";
const app = express();
const db = new PrismaClient();
async function persistPayment() {
    return db.payment.create({data:{amount:100}});
}
async function createPayment() { return persistPayment(); }
async function readPayment() { return db.payment.findMany(); }
app.post("/payments", createPayment);
app.get("/payments", readPayment);
db.$transaction([]);
"""


def pipeline(root):
    index = index_repository(root)
    imports = resolve_imports(index)
    calls = resolve_calls(index, imports)
    endpoints = resolve_http_endpoints(index, imports, calls)
    flow = resolve_framework_flow(index, imports, calls, endpoints)
    tests = analyze_tests(index, imports, calls, base_graph=flow.graph)
    return index, tests, materialize_database_graph(index, base_graph=tests.graph)


class DatabaseGraphTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "app.py").write_text(PYTHON, encoding="utf-8")
        (self.root / "app.ts").write_text(TYPESCRIPT, encoding="utf-8")

    def test_integration_trace_evidence_and_determinism(self):
        index, prior, result = pipeline(self.root)
        self.assertTrue(index.is_complete)
        self.assertEqual(index.database_operation_count, 9)
        self.assertEqual(sum(f.database_operation_count for f in index.file_results), 9)
        self.assertEqual(len(result.operation_entities), 9)
        self.assertEqual(dict(result.provider_counts), {"prisma": 3, "sqlalchemy": 6})
        self.assertEqual(result.relationship_count, 5)
        self.assertEqual(result.unlinked_observation_count, 4)
        self.assertEqual(result.staged_observation_count, 1)
        self.assertEqual(result.unmaterialized_observation_count, 0)
        for entity in prior.graph.entities():
            self.assertEqual(result.graph.get_entity(entity.id), entity)
        for edge in prior.graph.relationships():
            self.assertEqual(result.graph.get_relationship(edge.id), edge)
        for entity in result.operation_entities:
            self.assertFalse(prior.graph.has_entity(entity.id))
            self.assertFalse(index.graph.has_entity(entity.id))
            self.assertFalse(any(e.kind is RK.DEFINES for e in result.graph.incoming(entity.id)))
            self.assertEqual(result.graph.get_entity(entity.parent_id).location.file_path, entity.location.file_path)
        for path in ("app.py", "app.ts"):
            for method, expected in (
                ("POST", (RK.EXPOSES, RK.CALLS, RK.WRITES_DATABASE)),
                ("GET", (RK.EXPOSES, RK.READS_DATABASE)),
            ):
                endpoint = next(
                    e
                    for e in result.graph.entities()
                    if e.kind is EntityKind.API_ENDPOINT and e.name.startswith(method) and e.location.file_path == path
                )
                operation = next(
                    e
                    for e in result.operation_entities
                    if e.location.file_path == path
                    and dict(e.metadata)["operation_kind"] == ("write" if method == "POST" else "read")
                    and dict(e.metadata)["effect_stage"] != "staged_mutation"
                )
                trace = result.graph.shortest_path(endpoint.id, operation.id, relationship_kinds=frozenset(expected))
                self.assertIsNotNone(trace)
                self.assertEqual(tuple(e.kind for e in trace.relationships), expected)
                for edge in trace.relationships:
                    self.assertEqual(edge, result.graph.get_relationship(edge.id))
                    self.assertTrue(edge.evidence)
                db_edge = trace.relationships[-1]
                self.assertEqual((db_edge.confidence, db_edge.confidence_score), (Confidence.LIKELY, 0.85))
                self.assertEqual(db_edge.evidence[0].location, operation.location)
                self.assertIn(
                    db_edge.evidence[0].analysis_method,
                    (
                        "sqlalchemy_execute_insert",
                        "sqlalchemy_session_get",
                        "prisma_model_create",
                        "prisma_model_findmany",
                    ),
                )
        again = pipeline(self.root)[2]
        self.assertEqual(result.graph.entities(), again.graph.entities())
        self.assertEqual(result.graph.relationships(), again.graph.relationships())
        self.assertEqual(result.observations, again.observations)

    def test_staged_transaction_unknown_have_nodes_without_database_edges(self):
        _, _, result = pipeline(self.root)
        for entity in result.operation_entities:
            if dict(entity.metadata)["effect_stage"] in ("staged_mutation", "transaction_control", "unknown"):
                self.assertEqual(result.graph.incoming(entity.id), ())
                endpoint = next(e for e in result.graph.entities() if e.kind is EntityKind.API_ENDPOINT)
                self.assertIsNone(
                    result.graph.shortest_path(
                        endpoint.id,
                        entity.id,
                        relationship_kinds=frozenset((RK.EXPOSES, RK.CALLS, RK.READS_DATABASE, RK.WRITES_DATABASE)),
                    )
                )

    def test_no_reread_or_retained_source(self):
        index, prior, _ = pipeline(self.root)
        with (
            patch("builtins.open", side_effect=AssertionError("source reread")),
            patch("arctrellis.parsing.source.os.open", side_effect=AssertionError("source reread")),
        ):
            result = materialize_database_graph(index, base_graph=prior.graph)
        pending = list(result.observations) + list(result.operation_entities)
        while pending:
            value = pending.pop()
            self.assertNotIsInstance(value, (bytes, bytearray, ParsedSource, SyntaxNode))
            if isinstance(value, tuple):
                pending.extend(value)
            elif is_dataclass(value):
                pending.extend(getattr(value, f.name) for f in fields(value))

    def test_snapshot_and_observation_corruption_rejected(self):
        index, prior, result = pipeline(self.root)
        with self.assertRaises(ValueError):
            materialize_database_graph(index, base_graph=result.graph)
        operation = index.database_observations[0]
        for metadata in (
            (),
            tuple((k, "missing" if k == "constructor_import_id" else v) for k, v in operation.metadata),
        ):
            changed = replace(operation, metadata=metadata)
            with self.assertRaises(ValueError):
                replace(index, database_observations=(changed,) + index.database_observations[1:])
        with self.assertRaises(ValueError):
            replace(index, database_observations=())
        with self.assertRaises(ValueError):
            replace(index, database_observations=tuple(reversed(index.database_observations)))

    def test_failed_partial_collisions_and_invariant_failure(self):
        (self.root / "app.py").write_text(PYTHON + "\ndef broken(:", encoding="utf-8")
        index = index_repository(self.root)
        self.assertEqual(index.partial_file_count, 1)
        self.assertEqual(index.database_operation_count, 9)
        with patch(
            "arctrellis.indexing.repository.extract_database_operations", side_effect=SourceReadError("not exposed")
        ):
            failed = index_repository(self.root)
        self.assertEqual(failed.database_operation_count, 0)
        self.assertEqual(failed.failed_file_count, 2)
        with (
            patch("arctrellis.indexing.repository.extract_database_operations", side_effect=ValueError("invariant")),
            self.assertRaises(ValueError),
        ):
            index_repository(self.root)
        (self.root / "sqlalchemy.py").write_text("def broken(:", encoding="utf-8")
        blocked = index_repository(self.root)
        self.assertEqual({o.provider for o in blocked.database_observations}, {"prisma"})

    def test_generic_execute_fake_and_unsupported_paths_are_absent(self):
        (self.root / "app.py").write_text(
            "def execute(): pass\ndef process(session):\n    session.execute(command)\nexecute()\n", encoding="utf-8"
        )
        (self.root / "app.ts").write_text(
            "const db = customFactory(); db.user.create({}); execute();", encoding="utf-8"
        )
        index, _, result = pipeline(self.root)
        self.assertEqual(index.database_observations, ())
        self.assertEqual(result.operation_entities, ())
        self.assertEqual(result.relationship_count, 0)

    def test_delete_and_transaction_effect_restrictions(self):
        (self.root / "app.py").write_text(
            "from sqlalchemy.orm import Session\nfrom sqlalchemy import update, insert, delete, select\n"
            "db = Session(engine)\ndb.add(x)\ndb.add_all(xs)\ndb.delete(x)\ndb.flush()\ndb.commit()\ndb.rollback()\n"
            "db.execute(command)\ndb.execute(select(Item))\ndb.execute(insert(Item))\n"
            "db.execute(update(Item))\ndb.execute(delete(Item))\n",
            encoding="utf-8",
        )
        (self.root / "app.ts").write_text(
            'import {PrismaClient} from "@prisma/client"; const db = new PrismaClient(); '
            "db.user.delete({}); db.$transaction([]);",
            encoding="utf-8",
        )
        index = index_repository(self.root)
        result = materialize_database_graph(index)
        self.assertEqual(len(result.operation_entities), 13)
        self.assertEqual(result.staged_observation_count, 3)
        self.assertEqual(result.unlinked_observation_count, 8)
        self.assertEqual([e.kind for e in result.relationships].count(RK.WRITES_DATABASE), 4)
        for edge in result.relationships:
            self.assertEqual((edge.confidence, edge.confidence_score), (Confidence.LIKELY, 0.85))
            entity = result.graph.get_entity(edge.target_entity_id)
            self.assertEqual(edge.source_entity_id, entity.parent_id)
            self.assertEqual(edge.evidence[0].metadata, entity.metadata)

    def test_category_and_statement_proof_cannot_be_substituted(self):
        from arctrellis.database import DatabaseOperationKind

        index = index_repository(self.root)
        original = index.database_observations[0]
        for changes in (
            {"operation_kind": DatabaseOperationKind.READ},
            {"metadata": tuple((k, "staged_mutation" if k == "effect_stage" else v) for k, v in original.metadata)},
            {"metadata": tuple((k, "missing" if k == "statement_import_id" else v) for k, v in original.metadata)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(index, database_observations=(replace(original, **changes),) + index.database_observations[1:])

    def test_unknown_execute_cannot_borrow_other_statement_proof(self):
        from arctrellis.database import DatabaseOperationKind

        index = index_repository(self.root)
        unknown = next(o for o in index.database_observations if o.operation_kind is DatabaseOperationKind.UNKNOWN)
        insert = next(o for o in index.database_observations if dict(o.metadata).get("statement_kind") == "insert")
        metadata = dict(unknown.metadata)
        metadata.update(dict(insert.metadata))
        changed = replace(unknown, operation_kind=DatabaseOperationKind.WRITE, metadata=tuple(metadata.items()))
        with self.assertRaises(ValueError):
            replace(
                index,
                database_observations=tuple(changed if o.id == unknown.id else o for o in index.database_observations),
            )

    def test_analysis_never_executes_source(self):
        import builtins

        marker = self.root / "executed.txt"
        source = (
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\nraise RuntimeError('target')\n"
        )
        (self.root / "app.py").write_text(source + PYTHON, encoding="utf-8")
        (self.root / "app.ts").write_text("throw new Error('target');\n" + TYPESCRIPT, encoding="utf-8")
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name.split(".")[0] in ("sqlalchemy", "prisma"):
                self.fail("target ORM import")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=guarded_import):
            index, _, result = pipeline(self.root)
        self.assertTrue(index.is_complete)
        self.assertEqual(len(result.observations), 9)
        self.assertFalse(marker.exists())

    def test_public_api_import_orders(self):
        import subprocess
        import sys

        for first in ("database", "indexing", "calls", "frameworks", "test_semantics"):
            with self.subTest(first=first):
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        f"import arctrellis.{first}; from arctrellis.database import "
                        "extract_database_operations, materialize_database_graph, DatabaseGraphResult",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
