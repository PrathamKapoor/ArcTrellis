import unittest

from arctrellis.database import DatabaseOperationKind as Kind
from arctrellis.database import extract_sqlalchemy_operations
from arctrellis.extraction import extract_entities
from arctrellis.ingestion import Language
from arctrellis.parsing import parse_source

HEADER = "from sqlalchemy.orm import Session\nfrom sqlalchemy import select, insert, update, delete\n"


def extract(source, **options):
    parsed = parse_source("app.py", Language.PYTHON, source.encode())
    entities = extract_entities(parsed)
    return parsed, entities, extract_sqlalchemy_operations(parsed, entities, **options)


class SQLAlchemyTests(unittest.TestCase):
    def test_every_supported_operation(self):
        cases = {
            "get(Payment, 1)": (Kind.READ, "read_capable", "Payment"),
            "execute(select(Payment))": (Kind.READ, "statement_execution", "Payment"),
            "execute(insert(Payment))": (Kind.WRITE, "statement_execution", "Payment"),
            "execute(update(Payment))": (Kind.WRITE, "statement_execution", "Payment"),
            "execute(delete(Payment))": (Kind.DELETE, "statement_execution", "Payment"),
            "add(payment)": (Kind.WRITE, "staged_mutation", None),
            "add_all(payments)": (Kind.WRITE, "staged_mutation", None),
            "delete(payment)": (Kind.DELETE, "staged_mutation", None),
            "flush()": (Kind.TRANSACTION, "transaction_control", None),
            "commit()": (Kind.TRANSACTION, "transaction_control", None),
            "rollback()": (Kind.TRANSACTION, "transaction_control", None),
            "execute(unknown)": (Kind.UNKNOWN, "unknown", None),
        }
        for call, expected in cases.items():
            with self.subTest(call=call):
                parsed, _, operations = extract(HEADER + "db = Session(engine)\ndb." + call + "\n")
                self.assertEqual(len(operations), 1)
                operation = operations[0]
                self.assertEqual(
                    (operation.operation_kind, dict(operation.metadata)["effect_stage"], operation.target_name),
                    expected,
                )
                self.assertEqual(
                    parsed.source[operation.span.start_byte : operation.span.end_byte].decode(), "db." + call
                )
                self.assertEqual(operation.location.start_line, 4)
                self.assertEqual(operation.provider, "sqlalchemy")

    def test_aliases_scopes_positions_and_ids(self):
        source = (
            "from sqlalchemy.orm import Session as OrmSession\n"
            "def outer():\n    db = OrmSession(engine)\n    def inner():\n        db.get(Payment, 1)\n"
            "    db.get(Payment, 2)\nclass Service:\n    def save(self):\n"
            "        db = OrmSession(engine)\n        db.add(payment)\n"
        )
        _, entities, operations = extract(source)
        names = {e.id: e.name for e in entities.entities}
        self.assertEqual([names[o.owner_entity_id] for o in operations], ["inner", "outer", "save"])
        self.assertEqual(len({o.id for o in operations}), 3)
        self.assertEqual(operations, extract(source)[2])

    def test_rejected_provenance_and_rebinding(self):
        cases = (
            "class Session: pass\ndb = Session(engine)\ndb.add(x)\n",
            "from custom import Session\ndb = Session(engine)\ndb.add(x)\n",
            "from sqlalchemy.orm import Session\nSession = fake\ndb = Session(engine)\ndb.add(x)\n",
            HEADER + "db = Session(engine)\ndb = fake\ndb.get(Payment, 1)\n",
            HEADER + "def f(db):\n    db.commit()\n",
            HEADER + "db = Session(engine)\ndef f(db):\n    db.get(Payment, 1)\n",
            HEADER + "db = Session(engine)\ndef f():\n    db.get(Payment, 1)\n    db = fake\n",
            HEADER + "if yes:\n    db = Session(engine)\ndb.add(x)\n",
            HEADER + "def f(Session):\n    db = Session(engine)\n    db.add(x)\n",
            HEADER + "db = Session(engine)\ndb.add = fake\ndb.add(x)\n",
        )
        for source in cases:
            with self.subTest(source=source):
                self.assertEqual(extract(source)[2], ())

    def test_unknown_statement_constructor(self):
        for prefix in ("from custom import select\n", "def select(x): pass\n", "select = custom\n"):
            _, _, operations = extract(
                "from sqlalchemy.orm import Session\n" + prefix + "db = Session(engine)\ndb.execute(select(Payment))\n"
            )
            self.assertEqual(operations[0].operation_kind, Kind.UNKNOWN)
        _, _, operations = extract(HEADER + "db = Session(engine)\ndb.execute(transform(insert(Payment)))\n")
        self.assertEqual(operations[0].operation_kind, Kind.UNKNOWN)

    def test_aliased_statement_constructor(self):
        _, _, operations = extract(
            "from sqlalchemy.orm import Session as S\nfrom sqlalchemy import select as pick\n"
            "db = S(engine)\ndb.execute(pick(Item))\n"
        )
        self.assertEqual((operations[0].operation_kind, operations[0].target_name), (Kind.READ, "Item"))

    def test_partial_and_provider_collision(self):
        source = HEADER + "db = Session(engine)\ndb.get(Payment, 1)\ndef broken(:\n"
        _, result, operations = extract(source)
        self.assertTrue(result.partial)
        self.assertEqual(len(operations), 1)
        self.assertEqual(extract(source, blocked_providers=frozenset({"sqlalchemy"}))[2], ())

    def test_comprehension_scopes_are_deferred(self):
        for expression in (
            "[db.get(Payment, 1) for db in others]",
            "[db.execute(select(Payment)) for select in others]",
        ):
            with self.subTest(expression=expression):
                self.assertEqual(extract(HEADER + "db = Session(engine)\n" + expression)[2], ())

    def test_nested_final_same_name_keeps_correct_owner(self):
        source = HEADER + "def f():\n    db = Session(engine)\n    def f():\n        db.get(Payment, 1)\n"
        _, result, operations = extract(source)
        inner = [e for e in result.entities if e.name == "f"][-1]
        self.assertEqual(len(operations), 1)
        self.assertEqual(operations[0].owner_entity_id, inner.id)
