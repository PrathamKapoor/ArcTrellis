import unittest
from dataclasses import FrozenInstanceError, replace

from arctrellis.calls import CalleeKind, CallSite, make_call_site_id
from arctrellis.core import SourceLocation
from arctrellis.ingestion import Language
from arctrellis.parsing import SyntaxSpan


class ModelTests(unittest.TestCase):
    def test_identity_helper_rejects_noncanonical_inputs(self):
        site = self.site()
        for language, path, owner, kind, parts, span in (
            ("python", site.path, "owner", site.callee_kind, site.callee_parts, site.span),
            (site.language, "../a.py", "owner", site.callee_kind, site.callee_parts, site.span),
            (site.language, site.path, "", site.callee_kind, site.callee_parts, site.span),
            (site.language, site.path, "owner", site.callee_kind, (), site.span),
        ):
            with self.assertRaises((TypeError, ValueError)):
                make_call_site_id(language, path, owner, kind, parts, span)

    def site(self):
        return CallSite(
            "site",
            "a.py",
            Language.PYTHON,
            "owner",
            CalleeKind.NAME,
            ("run",),
            SourceLocation("a.py", 1, 1),
            SyntaxSpan(0, 5, 1, 0, 1, 5),
        )

    def test_immutable_hashable_and_validated(self):
        site = self.site()
        self.assertEqual(len({site, site}), 1)
        with self.assertRaises(FrozenInstanceError):
            site.owner_entity_id = "new"
        for change in (
            {"callee_parts": ()},
            {"owner_entity_id": ""},
            {"callee_parts": ["run"]},
            {"callee_kind": CalleeKind.MEMBER},
            {"language": "python"},
            {"location": SourceLocation("b.py", 1, 1)},
            {"callee_parts": ("a()",)},
        ):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                replace(site, **change)
        with self.assertRaises(ValueError):
            SyntaxSpan(-1, 5, 1, 0, 1, 5)

    def test_identity_changes_with_canonical_components(self):
        site = self.site()
        a = make_call_site_id(
            site.language, site.path, site.owner_entity_id, site.callee_kind, site.callee_parts, site.span
        )
        self.assertEqual(
            a,
            make_call_site_id(
                site.language, site.path, site.owner_entity_id, site.callee_kind, site.callee_parts, site.span
            ),
        )
        for change in (
            {"owner_entity_id": "other"},
            {"callee_parts": ("other",)},
            {"span": SyntaxSpan(1, 6, 1, 1, 1, 6)},
            {"path": "b.py", "location": SourceLocation("b.py", 1, 1)},
        ):
            other = replace(site, **change)
            self.assertNotEqual(
                a,
                make_call_site_id(
                    other.language, other.path, other.owner_entity_id, other.callee_kind, other.callee_parts, other.span
                ),
            )
