from dataclasses import FrozenInstanceError
import unittest

from arctrellis.ingestion import Language
from arctrellis.parsing import DiagnosticKind, ParseDiagnostic, ParsedSource, SyntaxNode, SyntaxSpan


class SyntaxModelTests(unittest.TestCase):
    def span(self, **changes):
        fields = dict(start_byte=0, end_byte=1, start_line=1, start_column=0, end_line=1, end_column=1)
        fields.update(changes)
        return SyntaxSpan(**fields)

    def test_valid_span_has_half_open_byte_and_point_coordinates(self):
        self.assertEqual(self.span().end_byte, 1)
        self.assertEqual(self.span(end_byte=0, end_column=0).start_line, 1)

    def test_invalid_byte_line_and_column_ranges_are_rejected(self):
        for change in ({"start_byte": -1}, {"start_byte": 2}, {"start_line": 0},
                       {"start_line": 2}, {"start_column": -1}, {"end_column": -1},
                       {"start_column": 2}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.span(**change)
        with self.assertRaises(TypeError):
            self.span(start_byte=True)

    def test_node_requires_kind_tuple_children_and_valid_optional_field(self):
        span = self.span()
        for kind in ("", " "):
            with self.assertRaises(ValueError):
                SyntaxNode(kind, span)
        with self.assertRaises(TypeError):
            SyntaxNode("identifier", span, children=[])
        with self.assertRaises(ValueError):
            SyntaxNode("identifier", span, field_name="")
        self.assertIsNone(SyntaxNode("identifier", span).field_name)

    def test_walk_and_field_lookup_preserve_order_and_choose_first_match(self):
        child = SyntaxNode("identifier", self.span(), field_name="name")
        other = SyntaxNode("identifier", self.span(), field_name="name")
        root = SyntaxNode("module", self.span(), children=(child, other))
        self.assertIs(root.child_by_field("name"), child)
        self.assertIsNone(root.child_by_field("missing"))
        self.assertEqual(tuple(root.walk()), (root, child, other))

    def test_children_must_fit_parent_span_and_preserve_source_order(self):
        with self.assertRaises(ValueError):
            SyntaxNode("module", self.span(), children=(SyntaxNode("identifier", self.span(end_byte=2, end_column=2)),))

    def test_diagnostics_and_parsed_source_are_validated_immutable_values(self):
        root = SyntaxNode("module", self.span())
        diagnostic = ParseDiagnostic(DiagnosticKind.ERROR, "ERROR", self.span())
        result = ParsedSource("a.py", Language.PYTHON, b"x", root, (diagnostic,))
        self.assertTrue(result.has_errors)
        self.assertEqual(result.diagnostic_count, 1)
        self.assertEqual(result.size_bytes, 1)
        self.assertEqual(result.bytes_for(root), b"x")
        self.assertEqual(result, ParsedSource("a.py", Language.PYTHON, b"x", root, (diagnostic,)))
        with self.assertRaises(FrozenInstanceError):
            result.source = b"z"
        with self.assertRaises(TypeError):
            ParseDiagnostic("ERROR", "ERROR", self.span())
        for path in ("/a.py", "../a.py", "a\\b.py"):
            with self.assertRaises(ValueError):
                ParsedSource(path, Language.PYTHON, b"x", root)
        with self.assertRaises(TypeError):
            ParsedSource("a.py", None, b"x", root)
        with self.assertRaises(TypeError):
            ParsedSource("a.py", Language.PYTHON, "x", root)
        with self.assertRaises(TypeError):
            ParsedSource("a.py", Language.PYTHON, b"x", root, [])
        with self.assertRaises(ValueError):
            ParsedSource("a.py", Language.PYTHON, b"", root)
