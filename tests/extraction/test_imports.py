import unittest

from arctrellis.core import EntityKind
from arctrellis.extraction import extract_python_entities
from arctrellis.ingestion import Language
from arctrellis.parsing import parse_source


class ImportTests(unittest.TestCase):
    def test_future_imports_use_their_anonymous_module_token_without_resolution(self):
        result, imports = self.imports('from __future__ import annotations\nfrom __future__ import division as d\n')
        self.assertFalse(result.partial)
        self.assertEqual([e.name for e in imports], ["annotations", "d"])
        self.assertTrue(all(dict(e.metadata)["module"] == "__future__" for e in imports))
        self.assertEqual(dict(imports[1].metadata)["imported_name"], "division")
        self.assertEqual(dict(imports[1].metadata)["alias"], "d")

    def imports(self, source):
        result = extract_python_entities(parse_source("src/a.py", Language.PYTHON, source.encode()))
        return result, result.entities_of_kind(EntityKind.IMPORT)

    def test_direct_bindings_aliases_and_full_dotted_modules(self):
        result, imports = self.imports("import os, sys as system\nimport package.submodule\nimport package.submodule as module\n")
        self.assertEqual([i.name for i in imports], ["os", "system", "package", "module"])
        for entity, module, alias in zip(imports, ["os", "sys", "package.submodule", "package.submodule"], ["", "system", "", "module"]):
            metadata = dict(entity.metadata)
            self.assertEqual({key: metadata[key] for key in ("import_form", "module", "imported_name", "alias", "binding", "relative_level", "is_wildcard")},
                             dict(import_form="import", module=module, imported_name="", alias=alias,
                                  binding=entity.name, relative_level="0", is_wildcard="false"))
            self.assertEqual(entity.parent_id, result.module.id)

    def test_from_bindings_parentheses_and_relative_levels(self):
        _, imports = self.imports("from pathlib import Path\nfrom package.module import Thing as Alias\nfrom package import (A, B as Bee,)\nfrom .local import helper\nfrom ..parent import thing\nfrom . import sibling\n")
        self.assertEqual([i.name for i in imports], ["Path", "Alias", "A", "Bee", "helper", "thing", "sibling"])
        for entity, module, name, level in zip(imports, ["pathlib", "package.module", "package", "package", ".local", "..parent", "."],
                                             ["Path", "Thing", "A", "B", "helper", "thing", "sibling"], [0, 0, 0, 0, 1, 2, 1]):
            metadata = dict(entity.metadata)
            self.assertEqual(metadata["import_form"], "from")
            self.assertEqual(metadata["module"], module)
            self.assertEqual(metadata["imported_name"], name)
            self.assertEqual(metadata["relative_level"], str(level))
        self.assertEqual(dict(imports[1].metadata)["alias"], "Alias")

    def test_wildcard_is_one_unexpanded_binding_and_repeated_imports_are_distinct(self):
        _, imports = self.imports("from package import *\nimport os\nimport os\n")
        self.assertEqual(len(imports), 3)
        wildcard = dict(imports[0].metadata)
        self.assertEqual((imports[0].name, wildcard["binding"], wildcard["imported_name"], wildcard["is_wildcard"]), ("*", "*", "*", "true"))
        self.assertNotEqual(imports[1].id, imports[2].id)
        self.assertNotEqual(imports[1].qualified_name, imports[2].qualified_name)
