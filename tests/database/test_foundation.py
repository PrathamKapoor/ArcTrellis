import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from uuid import UUID

from arctrellis.core import CodeEntity, EntityKind, SourceLocation
from arctrellis.database import (
    DatabaseAnalysisResult,
    DatabaseOperationKind,
    make_database_operation_observation,
)
from arctrellis.ingestion import Language
from arctrellis.parsing import ParsedSource, SyntaxNode, SyntaxSpan


def owner(kind=EntityKind.FUNCTION):
    return CodeEntity(
        "owner",
        kind,
        "save",
        "a.py::save",
        SourceLocation("a.py", 1, 9),
        language="python",
        metadata=(
            ("start_byte", "0"),
            ("end_byte", "100"),
            ("start_line", "1"),
            ("start_column", "0"),
            ("end_line", "10"),
            ("end_column", "0"),
        ),
    )


def observation(**changes):
    arguments = dict(
        owner=owner(),
        language=Language.PYTHON,
        operation_kind=DatabaseOperationKind.WRITE,
        provider="unknown",
        operation_name="synthetic_write",
        span=SyntaxSpan(10, 20, 2, 0, 2, 10),
    )
    arguments.update(changes)
    return make_database_operation_observation(**arguments)


class DatabaseFoundationTests(unittest.TestCase):
    def test_valid_unknown_target_and_canonical_owner(self):
        value = observation()
        self.assertEqual(value.owner_entity_id, "owner")
        self.assertIsNone(value.target_name)
        self.assertEqual(value.location, SourceLocation("a.py", 2, 2))
        self.assertEqual(value.provider, "unknown")
        self.assertEqual(UUID(value.id).version, 5)

    def test_supported_owner_kinds(self):
        for kind in (EntityKind.MODULE, EntityKind.FUNCTION, EntityKind.METHOD):
            self.assertEqual(observation(owner=owner(kind)).owner_entity_id, "owner")
        for kind in (EntityKind.CLASS, EntityKind.TEST, EntityKind.FILE):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                observation(owner=owner(kind))

    def test_owner_required_and_matching_language_and_bounds(self):
        for changes in (
            {"owner": None},
            {"language": Language.JAVASCRIPT},
            {"span": SyntaxSpan(101, 110, 11, 0, 11, 9)},
        ):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                observation(**changes)

    def test_kind_validation(self):
        with self.assertRaises(TypeError):
            observation(operation_kind="WRITE")
        self.assertEqual(
            {k.value for k in DatabaseOperationKind}, {"read", "write", "delete", "transaction", "unknown"}
        )

    def test_deterministic_identity_and_distinguishing_components(self):
        original = observation()
        self.assertEqual(original, observation())
        for changes in (
            {"span": SyntaxSpan(11, 20, 2, 1, 2, 10)},
            {"operation_kind": DatabaseOperationKind.READ},
            {"operation_name": "other"},
            {"provider": "future_adapter"},
            {"target_name": "payment"},
        ):
            with self.subTest(changes=changes):
                self.assertNotEqual(original.id, observation(**changes).id)

    def test_metadata_immutability_and_target_validation(self):
        value = observation(target_name="payment", metadata=(("verb", "create"),))
        self.assertEqual(dict(value.metadata), {"verb": "create"})
        with self.assertRaises(FrozenInstanceError):
            value.provider = "other"
        for changes in (
            {"metadata": {}},
            {"metadata": (("x", "1"), ("x", "2"))},
            {"provider": ""},
            {"target_name": " "},
        ):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                observation(**changes)

    def test_result_ordering_and_counts(self):
        write = observation()
        read = observation(operation_kind=DatabaseOperationKind.READ, provider="future_adapter")
        result = DatabaseAnalysisResult.from_observations((write, read))
        self.assertEqual(result, DatabaseAnalysisResult.from_observations((read, write)))
        self.assertEqual(result.observation_count, 2)
        self.assertEqual(dict(result.operation_counts), {DatabaseOperationKind.READ: 1, DatabaseOperationKind.WRITE: 1})
        self.assertEqual(dict(result.provider_counts), {"future_adapter": 1, "unknown": 1})
        self.assertEqual(DatabaseAnalysisResult(()).operation_counts, ())
        with self.assertRaises(ValueError):
            DatabaseAnalysisResult.from_observations((write, write))

    def test_no_source_or_parser_objects_retained(self):
        pending = [DatabaseAnalysisResult.from_observations((observation(),))]
        while pending:
            value = pending.pop()
            self.assertNotIsInstance(value, (bytes, bytearray, ParsedSource, SyntaxNode, CodeEntity))
            if isinstance(value, tuple):
                pending.extend(value)
            elif is_dataclass(value):
                pending.extend(getattr(value, f.name) for f in fields(value))

    def test_forged_identity_rejected(self):
        with self.assertRaises(TypeError):
            replace(observation(), id="forged")

    def test_generic_execute_is_not_database_analysis(self):
        from tests.test_semantics.test_analysis import analyze

        for path, source in (
            ("a.py", "def execute(): pass\nexecute()\n"),
            ("a.js", "function execute() {} execute();"),
            ("a.ts", "function execute() {} execute();"),
        ):
            with self.subTest(path=path):
                _, _, result = analyze({path: source})
                self.assertFalse(any(e.kind is EntityKind.DATABASE_OPERATION for e in result.graph.entities()))
                self.assertFalse(any("DATABASE" in e.kind.value for e in result.graph.relationships()))
