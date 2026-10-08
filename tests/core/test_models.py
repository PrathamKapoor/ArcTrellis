"""Domain contract tests through the public package API."""

from dataclasses import FrozenInstanceError, asdict, fields, replace
import json
import unittest

from arctrellis.core import (
    CodeEntity,
    Confidence,
    EntityKind,
    Evidence,
    Relationship,
    RelationshipKind,
    SourceLocation,
)


class VocabularyTests(unittest.TestCase):
    def test_entity_kinds_match_required_vocabulary(self):
        self.assertEqual(
            {item.value for item in EntityKind},
            {"REPOSITORY", "DIRECTORY", "FILE", "MODULE", "CLASS", "FUNCTION",
             "METHOD", "VARIABLE", "IMPORT", "API_ENDPOINT", "MIDDLEWARE",
             "TEST", "DATABASE_OPERATION"},
        )

    def test_relationship_kinds_match_required_vocabulary(self):
        self.assertEqual(
            {item.value for item in RelationshipKind},
            {"DEFINES", "CONTAINS", "IMPORTS", "CALLS", "INHERITS", "USES",
             "EXPOSES", "APPLIES_MIDDLEWARE", "TESTS", "READS_DATABASE", "WRITES_DATABASE"},
        )

    def test_confidence_contains_only_static_classifications(self):
        self.assertEqual(
            {item.value for item in Confidence},
            {"PROVEN", "LIKELY", "POSSIBLE", "UNRESOLVED"},
        )


class SourceLocationTests(unittest.TestCase):
    def test_valid_source_location_preserves_path_and_inclusive_lines(self):
        location = SourceLocation("src/payment/PaymentService.ts", 61, 61)
        self.assertEqual(location.file_path, "src/payment/PaymentService.ts")
        self.assertEqual((location.start_line, location.end_line), (61, 61))
        self.assertEqual(SourceLocation("file.py", 1, 10).end_line, 10)

    def test_source_location_rejects_start_line_below_one(self):
        for start in (0, -1):
            with self.subTest(start=start), self.assertRaisesRegex(ValueError, "start_line"):
                SourceLocation("file.py", start, 10)

    def test_source_location_rejects_end_line_before_start_line(self):
        with self.assertRaisesRegex(ValueError, "end_line"):
            SourceLocation("file.py", 10, 5)

    def test_source_location_requires_integer_lines_excluding_boolean(self):
        for value in (True, 1.0, "1", None):
            for field in ("start_line", "end_line"):
                with self.subTest(value=value, field=field), self.assertRaises(TypeError):
                    SourceLocation(**{"file_path": "file.py", "start_line": 1,
                                      "end_line": 1, field: value})

    def test_source_location_rejects_absolute_and_noncanonical_paths(self):
        for path in ("", " ", "/src/a.py", "C:/src/a.py", "C:a.py", "//host/a.py",
                     "src\\a.py", "../a.py", "src/../a.py", "./a.py", "src/./a.py",
                     "src//a.py", "src/a.py/", " a.py", "a.py ", "a\x00.py", "."):
            with self.subTest(path=path), self.assertRaises(ValueError):
                SourceLocation(path, 1, 1)

    def test_source_location_rejects_nonstring_paths(self):
        with self.assertRaises(TypeError):
            SourceLocation(123, 1, 1)

    def test_source_location_accepts_unicode_and_spaces_inside_paths(self):
        path = "source files/支付.py"
        self.assertEqual(SourceLocation(path, 1, 1).file_path, path)


class DomainRecordTests(unittest.TestCase):
    def test_optional_signature_preserves_existing_positions_and_validates_text(self):
        entity = CodeEntity("id", EntityKind.FUNCTION, "f", "f", None, None, "python", (("x", "y"),))
        self.assertIsNone(entity.signature)
        signature = "def f(\n    x: int,\n) -> int"
        self.assertEqual(replace(entity, signature=signature).signature, signature)
        for invalid in ("", " ", " def f()", 1):
            with self.subTest(invalid=invalid), self.assertRaises((ValueError, TypeError)):
                replace(entity, signature=invalid)

    def setUp(self):
        self.location = SourceLocation("src/payment/PaymentService.ts", 61, 61)
        self.entity = CodeEntity(
            "payment.create", EntityKind.METHOD, "create", "PaymentService.create",
            self.location, "payment", "typescript", (("visibility", "public"),),
        )
        self.evidence = Evidence("call-site-61", self.location, "direct_call_resolution")
        self.relationship = Relationship(
            "payment-fraud-call", self.entity.id, RelationshipKind.CALLS, "fraud.check",
            Confidence.PROVEN, 1.0, (self.evidence,),
        )

    def test_valid_entity_preserves_identity_kind_and_optional_data(self):
        self.assertEqual(self.entity.id, "payment.create")
        self.assertIs(self.entity.kind, EntityKind.METHOD)
        self.assertEqual(self.entity.qualified_name, "PaymentService.create")
        self.assertEqual(self.entity.location, self.location)
        self.assertEqual(self.entity.parent_id, "payment")
        self.assertEqual(self.entity.language, "typescript")
        repository = CodeEntity("repo", EntityKind.REPOSITORY, "ArcTrellis", "ArcTrellis")
        self.assertIsNone(repository.location)
        self.assertIsNone(repository.parent_id)
        self.assertIsNone(repository.language)

    def test_entity_rejects_empty_required_strings(self):
        for field in ("id", "name", "qualified_name"):
            for value in ("", " ", " padded "):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    replace(self.entity, **{field: value})

    def test_entity_rejects_invalid_optional_data_and_raw_kind(self):
        for field, value in (("kind", "METHOD"), ("location", {}), ("id", 3)):
            with self.subTest(field=field), self.assertRaises(TypeError):
                replace(self.entity, **{field: value})
        for field in ("parent_id", "language"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                replace(self.entity, **{field: ""})

    def test_valid_evidence_preserves_analysis_method_and_source(self):
        self.assertEqual(self.evidence.id, "call-site-61")
        self.assertEqual(self.evidence.location, self.location)
        self.assertEqual(self.evidence.analysis_method, "direct_call_resolution")

    def test_evidence_rejects_invalid_id_location_and_method(self):
        for field, value, error in (
            ("id", "", ValueError), ("location", None, TypeError),
            ("analysis_method", "", ValueError), ("analysis_method", "Direct call", ValueError),
            ("analysis_method", "1_method", ValueError), ("analysis_method", None, TypeError),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(error):
                replace(self.evidence, **{field: value})

    def test_valid_relationship_preserves_evidence_and_classification(self):
        self.assertEqual(self.relationship.evidence, (self.evidence,))
        self.assertIs(self.relationship.confidence, Confidence.PROVEN)
        self.assertEqual(self.relationship.confidence_score, 1.0)

    def test_relationship_direction_remains_source_to_target(self):
        self.assertEqual(self.relationship.source_entity_id, "payment.create")
        self.assertEqual(self.relationship.target_entity_id, "fraud.check")
        reverse = replace(self.relationship, source_entity_id="fraud.check",
                          target_entity_id="payment.create")
        self.assertNotEqual(reverse, self.relationship)

    def test_relationship_rejects_empty_source_id(self):
        with self.assertRaisesRegex(ValueError, "source_entity_id"):
            replace(self.relationship, source_entity_id="")

    def test_relationship_rejects_empty_target_id(self):
        with self.assertRaisesRegex(ValueError, "target_entity_id"):
            replace(self.relationship, target_entity_id="")

    def test_relationship_rejects_empty_relationship_id(self):
        with self.assertRaisesRegex(ValueError, "id"):
            replace(self.relationship, id="")

    def test_relationship_rejects_confidence_below_zero(self):
        with self.assertRaises(ValueError):
            replace(self.relationship, confidence_score=-0.1)

    def test_relationship_rejects_confidence_above_one(self):
        with self.assertRaises(ValueError):
            replace(self.relationship, confidence_score=1.1)

    def test_relationship_rejects_nonfinite_and_mistyped_confidence(self):
        for score in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(score=score), self.assertRaises(ValueError):
                replace(self.relationship, confidence_score=score)
        for score in (True, "0.5", []):
            with self.subTest(score=score), self.assertRaises(TypeError):
                replace(self.relationship, confidence_score=score)

    def test_relationship_accepts_score_boundaries_and_optional_score(self):
        for score in (0.0, 1.0, None):
            with self.subTest(score=score):
                self.assertEqual(replace(self.relationship, confidence_score=score).confidence_score, score)

    def test_relationship_preserves_uncertainty_without_assumed_thresholds(self):
        for classification in Confidence:
            with self.subTest(classification=classification):
                relationship = replace(self.relationship, confidence=classification,
                                       confidence_score=None, evidence=())
                self.assertIs(relationship.confidence, classification)
                self.assertEqual(relationship.evidence, ())

    def test_relationship_rejects_raw_enums_mutable_or_invalid_evidence(self):
        for field, value in (("kind", "CALLS"), ("confidence", "PROVEN"),
                             ("evidence", [self.evidence]), ("evidence", ("id",))):
            with self.subTest(field=field), self.assertRaises(TypeError):
                replace(self.relationship, **{field: value})

    def test_relationship_rejects_duplicate_evidence_ids(self):
        with self.assertRaisesRegex(ValueError, "duplicate evidence id"):
            replace(self.relationship, evidence=(self.evidence, self.evidence))

    def test_metadata_rejects_mutable_nested_or_duplicate_values(self):
        for record in (self.entity, self.evidence):
            for metadata in ({"key": "value"}, (("key", []),), (["key", "value"],),
                             (("key", "value", "extra"),)):
                with self.subTest(record=type(record), metadata=metadata), self.assertRaises(TypeError):
                    replace(record, metadata=metadata)
            for metadata in ((("", "value"),), (("key", "one"), ("key", "two"))):
                with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                    replace(record, metadata=metadata)

    def test_records_have_value_equality_and_consistent_hashes(self):
        for record in (self.location, self.entity, self.evidence, self.relationship):
            with self.subTest(record=type(record)):
                copy = replace(record)
                self.assertEqual(copy, record)
                self.assertEqual(hash(copy), hash(record))
                self.assertEqual(len({copy, record}), 1)

    def test_records_reject_field_mutation(self):
        for record in (self.location, self.entity, self.evidence, self.relationship):
            with self.subTest(record=type(record)), self.assertRaises(FrozenInstanceError):
                setattr(record, fields(record)[0].name, "changed")

    def test_nested_metadata_and_evidence_cannot_be_mutated(self):
        with self.assertRaises(TypeError):
            self.entity.metadata[0][1] = "private"
        with self.assertRaises(TypeError):
            self.relationship.evidence[0] = self.evidence
        with self.assertRaises(FrozenInstanceError):
            self.relationship.evidence[0].analysis_method = "changed"

    def test_metadata_order_participates_in_equality(self):
        first = replace(self.entity, metadata=(("a", "1"), ("b", "2")))
        second = replace(self.entity, metadata=(("b", "2"), ("a", "1")))
        self.assertNotEqual(first, second)

    def test_records_convert_to_json_primitives_without_custom_encoder(self):
        entity_data = json.loads(json.dumps(asdict(self.entity)))
        self.assertEqual(entity_data["kind"], "METHOD")
        self.assertEqual(entity_data["metadata"], [["visibility", "public"]])
        relationship_data = json.loads(json.dumps(asdict(self.relationship), allow_nan=False))
        self.assertEqual(relationship_data["kind"], "CALLS")
        self.assertEqual(relationship_data["confidence"], "PROVEN")
        self.assertEqual(relationship_data["evidence"][0]["location"]["start_line"], 61)


if __name__ == "__main__":
    unittest.main()
