import unittest

from arctrellis.ingestion import Language
from arctrellis.parsing import UnsupportedLanguageError, parse_source


class GrammarSelectionTests(unittest.TestCase):
    def test_all_extensions_and_uppercase_select_valid_grammars(self):
        families = ((Language.PYTHON, ("py", "pyi"), b"x = 1\n", "module"),
                    (Language.JAVASCRIPT, ("js", "jsx", "mjs", "cjs"), b"const x = 1;", "program"),
                    (Language.TYPESCRIPT, ("ts", "tsx", "mts", "cts"), b"const x: number = 1;", "program"))
        for language, extensions, source, root_kind in families:
            for extension in extensions:
                for suffix in (extension, extension.upper()):
                    path = f"APP.{suffix}"
                    with self.subTest(path=path):
                        result = parse_source(path, language, source)
                        self.assertEqual(result.path, path)
                        self.assertEqual(result.root.kind, root_kind)
                        self.assertFalse(result.has_errors)

    def test_language_extension_mismatch_and_unsupported_are_explicit(self):
        for path, language in (("a.js", Language.PYTHON), ("a.md", None), ("a.md", Language.PYTHON)):
            with self.subTest(path=path), self.assertRaises(UnsupportedLanguageError):
                parse_source(path, language, b"x")
