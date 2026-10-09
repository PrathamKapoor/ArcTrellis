import unittest

from arctrellis.database import DatabaseOperationKind as Kind
from arctrellis.database import extract_prisma_operations
from arctrellis.extraction import extract_entities
from arctrellis.ingestion import Language
from arctrellis.parsing import parse_source

HEADER = 'import { PrismaClient } from "@prisma/client";\nconst db = new PrismaClient();\n'


def extract(source, language=Language.TYPESCRIPT):
    path = "app.ts" if language is Language.TYPESCRIPT else "app.js"
    parsed = parse_source(path, language, source.encode())
    result = extract_entities(parsed)
    return parsed, result, extract_prisma_operations(parsed, result)


class PrismaTests(unittest.TestCase):
    def test_all_methods_in_both_languages(self):
        categories = {
            Kind.READ: (
                "findUnique",
                "findUniqueOrThrow",
                "findFirst",
                "findFirstOrThrow",
                "findMany",
                "count",
                "aggregate",
                "groupBy",
            ),
            Kind.WRITE: ("create", "createMany", "update", "updateMany", "upsert"),
            Kind.DELETE: ("delete", "deleteMany"),
        }
        for language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            for kind, methods in categories.items():
                for method in methods:
                    with self.subTest(language=language, method=method):
                        source = HEADER + "async function run() { return await db.payment." + method + "({}); }"
                        parsed, entities, operations = extract(source, language)
                        self.assertEqual(len(operations), 1)
                        operation = operations[0]
                        self.assertEqual(
                            (operation.operation_kind, operation.operation_name, operation.target_name),
                            (kind, method, "payment"),
                        )
                        self.assertEqual(operation.provider, "prisma")
                        self.assertEqual(dict(operation.metadata)["target_basis"], "prisma_model_accessor")
                        self.assertEqual(dict(operation.metadata)["effect_stage"], "client_request")
                        self.assertEqual(
                            next(e.name for e in entities.entities if e.id == operation.owner_entity_id), "run"
                        )
                        self.assertEqual(
                            parsed.bytes_for(next(n for n in parsed.root.walk() if n.span == operation.span)).decode(),
                            "db.payment." + method + "({})",
                        )
                        self.assertEqual(operation.location.start_line, 3)
                        self.assertEqual(operations, extract(source, language)[2])

    def test_alias_transaction_method_owner_and_models(self):
        source = (
            'import { PrismaClient as Client } from "@prisma/client";\n'
            "const db = new Client();\nclass Service { save() { db.User.create({}); "
            "db.payment.findMany(); db.$transaction([]); } }"
        )
        _, entities, operations = extract(source)
        self.assertEqual([o.target_name for o in operations], ["User", "payment", None])
        self.assertEqual(operations[-1].operation_kind, Kind.TRANSACTION)
        self.assertEqual(dict(operations[-1].metadata)["effect_stage"], "transaction_control")
        owner = next(e for e in entities.entities if e.id == operations[0].owner_entity_id)
        self.assertEqual((owner.kind.value, owner.name), ("METHOD", "save"))
        self.assertEqual(len({o.id for o in operations}), 3)

    def test_negatives(self):
        cases = (
            "class PrismaClient {}\nconst db = new PrismaClient(); db.user.create({});",
            "const db = customFactory(); db.user.create({});",
            "const db = {user:{create(){}}}; db.user.create();",
            HEADER + "function run(db: unknown) { db.user.findMany(); }",
            HEADER + "function run() { const db = fake; db.user.create({}); }",
            HEADER + "function run() { db.user.create({}); const db = fake; }",
            HEADER + "db = fake; db.user.create({});",
            HEADER + "db.user.create = fake; db.user.create({});",
            HEADER + 'db[model].create({}); db["user"].create({}); db.user["create"]({});',
            HEADER + 'db.$queryRaw("select"); db.$executeRaw("update"); db.user.unknown(); execute();',
            'import { PrismaClient } from "custom"; const db = new PrismaClient(); db.user.create({});',
            'import type { PrismaClient } from "@prisma/client"; const db = new PrismaClient(); db.user.create({});',
            HEADER + "function run(PrismaClient) { const local = new PrismaClient(); local.user.create({}); }",
            HEADER + "const run = function db() { db.user.create({}); };",
            HEADER + "db?.user.create({}); db.user.create?.({});",
            HEADER + "try {} catch (db) { db.user.create({}); }",
            HEADER + "function run() { try {} catch (db) { db.user.create({}); } }",
            HEADER + "function replace() { db.user.create = fake; } replace(); db.user.create({});",
            HEADER.replace("const db", "let db") + "function replace() { db = fake; } replace(); db.user.create({});",
            HEADER + "function run() { enum db { user } db.user.findMany(); }",
            HEADER + 'db["user"] = fake; db.user.create({});',
            HEADER + 'db.user["create"] = fake; db.user.create({});',
            HEADER + "delete db.user; db.user.create({});",
            HEADER + "delete\tdb.user; db.user.create({});",
            HEADER + "delete/* comment */db.user; db.user.create({});",
            HEADER + "delete(db.user); db.user.create({});",
        )
        for source in cases:
            with self.subTest(source=source):
                self.assertEqual(extract(source)[2], ())

    def test_partial(self):
        _, result, operations = extract(HEADER + "db.user.create({});\nfunction broken( {")
        self.assertTrue(result.partial)
        self.assertEqual(len(operations), 1)
