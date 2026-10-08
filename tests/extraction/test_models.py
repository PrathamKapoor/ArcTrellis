import unittest
from dataclasses import FrozenInstanceError, replace

from arctrellis.core import EntityKind
from arctrellis.extraction import extract_python_entities
from arctrellis.ingestion import Language
from arctrellis.parsing import parse_source


class ResultTests(unittest.TestCase):
    def setUp(self):
        self.result = extract_python_entities(parse_source("a.py", Language.PYTHON, b"def f():\n    pass\n"))

    def test_result_is_immutable_hashable_and_has_small_helpers(self):
        self.assertEqual(self.result.module.kind, EntityKind.MODULE)
        self.assertEqual(len(self.result.entities_of_kind(EntityKind.FUNCTION)), 1)
        self.assertEqual(self.result.entities_of_kind(EntityKind.CLASS), ())
        self.assertEqual(hash(self.result), hash(replace(self.result)))
        with self.assertRaises(FrozenInstanceError):
            self.result.partial = True
        with self.assertRaises(TypeError):
            replace(self.result, entities=list(self.result.entities))

    def test_module_unique_root_and_duplicate_id_contracts(self):
        module, function = self.result.entities
        for entities in ((function,), (module, module), (replace(module, parent_id=function.id), function)):
            with self.subTest(entities=entities), self.assertRaises(ValueError):
                replace(self.result, entities=entities)

    def test_path_language_location_and_parent_contracts(self):
        module, function = self.result.entities
        for change in (
            {"path": "b.py"},
            {"path": "../a.py"},
            {"language": "python"},
            {"partial": 1},
            {"entities": (module, replace(function, parent_id="missing"))},
            {"entities": (module, replace(function, parent_id=None))},
            {"entities": (module, replace(function, location=None))},
            {"entities": (module, replace(function, language="javascript"))},
        ):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                replace(self.result, **change)

    def test_source_order_and_parent_cycles_are_rejected(self):
        result = extract_python_entities(
            parse_source("a.py", Language.PYTHON, b"def a():\n    pass\ndef b():\n    pass\n")
        )
        module, first, second = result.entities
        with self.assertRaises(ValueError):
            replace(result, entities=(module, second, first))
        with self.assertRaises(ValueError):
            replace(result, entities=(module, replace(first, parent_id=first.id), second))
