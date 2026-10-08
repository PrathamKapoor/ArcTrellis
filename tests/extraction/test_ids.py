import unittest
from uuid import UUID

from arctrellis.core import EntityKind
from arctrellis.extraction import make_entity_id
from arctrellis.ingestion import Language


class IdentityTests(unittest.TestCase):
    def test_identical_components_reproduce_uuid5_and_changed_components_differ(self):
        fields = dict(language=Language.PYTHON, path="src/a.py", kind=EntityKind.FUNCTION,
                      qualified_name="src/a.py::f", start_byte=10, end_byte=30)
        original = make_entity_id(**fields)
        self.assertEqual(UUID(original).version, 5)
        self.assertEqual(make_entity_id(**fields), original)
        for change in ({"language": Language.JAVASCRIPT}, {"path": "b.py"},
                       {"kind": EntityKind.METHOD}, {"qualified_name": "src/a.py::g"},
                       {"start_byte": 11}, {"end_byte": 31}):
            with self.subTest(change=change):
                self.assertNotEqual(make_entity_id(**(fields | change)), original)

    def test_invalid_identity_components_are_rejected(self):
        fields = dict(language=Language.PYTHON, path="a.py", kind=EntityKind.FUNCTION,
                      qualified_name="a.py::f", start_byte=0, end_byte=1)
        for change in ({"path": "../a.py"}, {"qualified_name": ""}, {"start_byte": -1},
                       {"end_byte": -1}, {"start_byte": True}, {"kind": "FUNCTION"}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                make_entity_id(**(fields | change))
