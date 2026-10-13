"""Canonical entity selection: explicit outcomes, never an implicit guess."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from arctrellis.core import EntityKind
from arctrellis.graph import CodeGraph
from arctrellis.orchestration import (
    InvalidQueryRequestError,
    OrchestrationInvariantError,
    QueryIntent,
    QueryRequest,
    SelectionBasis,
    SelectionStatus,
    SelectorForm,
    analyze_repository,
    intent_spec,
    search_candidates,
    select_canonical_entity,
)

from .repository import (
    DUPLICATE_QUALIFIED_NAMES,
    EXPRESS,
    MIXED,
    PARTIAL_SOURCE,
    PAYMENTS,
    TYPESCRIPT,
    analyze,
    write_sources,
)

TRACE = QueryIntent.TRACE_ENDPOINT_TO_DATABASE


class SelectionTestCase(unittest.TestCase):
    """Analyze one shared untrusted fixture per test class."""

    sources: dict[str, str] = MIXED

    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        root = Path(cls._temporary.name)
        write_sources(root, cls.sources)
        cls.snapshot = analyze_repository(root)
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def select(self, **kwargs):
        intent = kwargs.pop("intent")
        request = QueryRequest(intent=intent, **kwargs)
        return select_canonical_entity(self.snapshot, request, intent_spec(intent).source_kinds)


class ExactIdentifierSelectionTests(SelectionTestCase):
    def test_exact_canonical_id_resolves(self) -> None:
        endpoint = next(
            document
            for document in self.snapshot.documents()
            if document.field_value("route_path") == "/payments" and document.repository_relative_path == "app.py"
        )
        result = self.select(intent=TRACE, entity_id=endpoint.entity_id)
        self.assertIs(result.status, SelectionStatus.RESOLVED)
        self.assertEqual(result.selected_entity_id, endpoint.entity_id)
        self.assertIs(result.selector_form, SelectorForm.ENTITY_ID)
        self.assertFalse(result.truncated)

    def test_unknown_canonical_id_is_not_found(self) -> None:
        result = self.select(intent=TRACE, entity_id="00000000-0000-0000-0000-000000000000")
        self.assertIs(result.status, SelectionStatus.NOT_FOUND)
        self.assertIsNone(result.selected_entity_id)
        self.assertEqual(result.candidates, ())
        self.assertIn("no canonical entity", result.reason)

    def test_wrong_entity_kind_is_invalid_not_not_found(self) -> None:
        function = next(
            document
            for document in self.snapshot.documents()
            if document.entity_kind is EntityKind.FUNCTION and document.repository_relative_path == "payments.py"
        )
        result = self.select(intent=TRACE, entity_id=function.entity_id)
        self.assertIs(result.status, SelectionStatus.INVALID)
        self.assertIn("does not satisfy", result.reason)

    def test_caller_constraint_is_honoured_for_an_exact_id(self) -> None:
        endpoint = next(
            document
            for document in self.snapshot.documents()
            if document.field_value("route_path") == "/payments" and document.repository_relative_path == "app.py"
        )
        result = self.select(
            intent=QueryIntent.FIND_CALLERS,
            entity_id=endpoint.entity_id,
        )
        self.assertIs(result.status, SelectionStatus.INVALID)


class QualifiedNameSelectionTests(SelectionTestCase):
    def test_unique_qualified_name_resolves(self) -> None:
        result = self.select(intent=QueryIntent.DIRECT_DATABASE_OPERATIONS, qualified_name="payments.py::createPayment")
        self.assertIs(result.status, SelectionStatus.RESOLVED)
        self.assertIsNotNone(result.selected_entity_id)

    def test_unknown_qualified_name_is_not_found(self) -> None:
        result = self.select(intent=QueryIntent.FIND_CALLERS, qualified_name="payments.py::absent")
        self.assertIs(result.status, SelectionStatus.NOT_FOUND)
        self.assertEqual(result.candidates, ())

    def test_duplicate_qualified_names_are_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            snapshot = analyze(Path(raw), DUPLICATE_QUALIFIED_NAMES)
        matches = snapshot.entities_with_qualified_name("js/dup.js::handler")
        self.assertEqual(len(matches), 2)
        request = QueryRequest(intent=QueryIntent.FIND_CALLERS, qualified_name="js/dup.js::handler")
        result = select_canonical_entity(snapshot, request, frozenset())
        self.assertIs(result.status, SelectionStatus.AMBIGUOUS)
        self.assertIsNone(result.selected_entity_id)
        self.assertEqual(len(result.candidates), 2)
        self.assertEqual(
            [candidate.entity_id for candidate in result.candidates],
            sorted(matches),
            "ambiguous candidates must be deterministically ordered",
        )
        for candidate in result.candidates:
            self.assertIs(candidate.basis, SelectionBasis.EXACT_QUALIFIED_NAME)
            self.assertIsNone(candidate.relevance_score)

    def test_entity_kind_constraint_disambiguates_duplicate_names(self) -> None:
        sources = {
            "js/typed.ts": """export class Handler { run(): unknown { return 1; } }
export function Handler(): unknown { return 2; }
""",
        }
        with tempfile.TemporaryDirectory() as raw:
            snapshot = analyze(Path(raw), sources)
        qualified = next(
            document.qualified_name
            for document in snapshot.documents()
            if document.name == "Handler" and document.entity_kind is EntityKind.CLASS
        )
        matches = snapshot.entities_with_qualified_name(qualified)
        self.assertGreaterEqual(len(matches), 1)
        unconstrained = select_canonical_entity(
            snapshot,
            QueryRequest(intent=QueryIntent.FIND_CALLERS, qualified_name=qualified),
            frozenset(),
        )
        self.assertIs(unconstrained.status, SelectionStatus.AMBIGUOUS)
        constrained = select_canonical_entity(
            snapshot,
            QueryRequest(intent=QueryIntent.FIND_CALLERS, qualified_name=qualified, entity_kind=EntityKind.CLASS),
            frozenset(),
        )
        self.assertIs(constrained.status, SelectionStatus.RESOLVED)
        document = snapshot.document(constrained.selected_entity_id or "")
        self.assertIs(document.entity_kind if document else None, EntityKind.CLASS)


class EndpointSelectorSelectionTests(SelectionTestCase):
    def test_unique_endpoint_registration_resolves(self) -> None:
        result = self.select(intent=TRACE, http_method="DELETE", route_path="/payments/{paymentId}")
        self.assertIs(result.status, SelectionStatus.RESOLVED)
        document = self.snapshot.document(result.selected_entity_id or "")
        self.assertIsNotNone(document)
        self.assertEqual(document.field_value("http_method") if document else None, "DELETE")

    def test_duplicate_endpoint_registrations_are_ambiguous(self) -> None:
        matches = self.snapshot.entities_with_route("POST", "/ts-payments")
        self.assertEqual(len(matches), 2)
        result = self.select(intent=TRACE, http_method="POST", route_path="/ts-payments")
        self.assertIs(result.status, SelectionStatus.AMBIGUOUS)
        self.assertIsNone(result.selected_entity_id)
        self.assertEqual(len(result.candidates), 2)
        for candidate in result.candidates:
            self.assertIs(candidate.basis, SelectionBasis.EXACT_ENDPOINT_METHOD_PATH)
            self.assertEqual(candidate.repository_relative_path, "ts/app.ts")

    def test_same_route_in_different_files_is_still_ambiguous(self) -> None:
        matches = self.snapshot.entities_with_route("POST", "/payments")
        self.assertGreater(len(matches), 1)
        result = self.select(intent=TRACE, http_method="POST", route_path="/payments")
        self.assertIs(result.status, SelectionStatus.AMBIGUOUS)
        self.assertEqual(len(result.candidates), len(matches))

    def test_unknown_route_is_not_found(self) -> None:
        result = self.select(intent=TRACE, http_method="GET", route_path="/absent")
        self.assertIs(result.status, SelectionStatus.NOT_FOUND)
        self.assertEqual(result.candidates, ())

    def test_local_versus_effective_scope_narrows_the_route(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            snapshot = analyze(
                Path(raw),
                {
                    "api.py": """from fastapi import APIRouter, FastAPI
router = APIRouter()
@router.get("/items")
def readItems():
    return []
app = FastAPI()
app.include_router(router, prefix="/v1")
"""
                },
            )
        effective = snapshot.entities_with_route("GET", "/v1/items")
        local = snapshot.entities_with_route("GET", "/items")
        self.assertEqual(len(effective), 1)
        self.assertEqual(len(local), 1)
        scoped = select_canonical_entity(
            snapshot,
            QueryRequest(
                intent=TRACE,
                http_method="GET",
                route_path="/items",
                endpoint_scope="local",
            ),
            intent_spec(TRACE).source_kinds,
        )
        self.assertIs(scoped.status, SelectionStatus.RESOLVED)
        self.assertEqual(scoped.selected_entity_id, local[0])
        declared_only = select_canonical_entity(
            snapshot,
            QueryRequest(
                intent=TRACE,
                http_method="GET",
                route_path="/v1/items",
                endpoint_scope="declared",
            ),
            intent_spec(TRACE).source_kinds,
        )
        self.assertIs(declared_only.status, SelectionStatus.NOT_FOUND)
        application = select_canonical_entity(
            snapshot,
            QueryRequest(
                intent=TRACE,
                http_method="GET",
                route_path="/v1/items",
                endpoint_scope="application",
            ),
            intent_spec(TRACE).source_kinds,
        )
        self.assertIs(application.status, SelectionStatus.RESOLVED)
        self.assertEqual(application.selected_entity_id, effective[0])


class LexicalCandidateSelectionTests(SelectionTestCase):
    def test_fuzzy_retrieval_returns_candidates_and_selects_nothing(self) -> None:
        request = QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="payment creation")
        found = search_candidates(self.snapshot, request)
        self.assertIs(found.selection.status, SelectionStatus.CANDIDATES)
        self.assertIsNone(found.selection.selected_entity_id)
        self.assertTrue(found.selection.candidates)
        for candidate in found.selection.candidates:
            self.assertIs(candidate.basis, SelectionBasis.LEXICAL_CANDIDATES)
            self.assertIsNotNone(candidate.relevance_score)

    def test_class_and_import_of_the_same_name_are_both_reported(self) -> None:
        request = QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="PaymentService", top_k=10)
        found = search_candidates(self.snapshot, request)
        kinds = {
            candidate.entity_kind for candidate in found.selection.candidates if candidate.name == "PaymentService"
        }
        self.assertIn(EntityKind.CLASS, kinds)
        self.assertIn(EntityKind.IMPORT, kinds)

    def test_top_ranked_candidate_is_not_promoted_to_a_selection(self) -> None:
        request = QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="PaymentService", top_k=1)
        found = search_candidates(self.snapshot, request)
        self.assertEqual(len(found.result.hits), 1)
        self.assertIs(found.selection.status, SelectionStatus.CANDIDATES)
        self.assertIsNone(found.selection.selected_entity_id)

    def test_filtered_search_applies_the_caller_constraints(self) -> None:
        request = QueryRequest(
            intent=QueryIntent.SEARCH_ENTITIES,
            search_text="payment",
            entity_kind=EntityKind.API_ENDPOINT,
        )
        found = search_candidates(self.snapshot, request)
        self.assertTrue(found.result.hits)
        for hit in found.result.hits:
            self.assertIs(hit.entity_kind, EntityKind.API_ENDPOINT)

    def test_search_with_no_match_is_not_found(self) -> None:
        request = QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="zzzznotpresentzzzz")
        found = search_candidates(self.snapshot, request)
        self.assertIs(found.selection.status, SelectionStatus.NOT_FOUND)
        self.assertEqual(found.selection.candidates, ())

    def test_truncated_search_reports_truncation_and_stays_unselected(self) -> None:
        request = QueryRequest(
            intent=QueryIntent.SEARCH_ENTITIES,
            search_text="payment",
            max_examined_postings=1,
        )
        found = search_candidates(self.snapshot, request)
        self.assertTrue(found.result.truncated)
        self.assertTrue(found.selection.truncated)
        self.assertIsNone(found.selection.selected_entity_id)

    def test_selection_requires_a_real_snapshot_and_request(self) -> None:
        with self.assertRaises(InvalidQueryRequestError):
            select_canonical_entity(self.snapshot, "not a request", frozenset())  # type: ignore[arg-type]
        with self.assertRaises(InvalidQueryRequestError):
            select_canonical_entity("not a snapshot", self.valid_request(), frozenset())  # type: ignore[arg-type]

    def valid_request(self) -> QueryRequest:
        return QueryRequest(intent=TRACE, http_method="GET", route_path="/payments")


class SelectionSideEffectTests(SelectionTestCase):
    def test_selection_does_not_mutate_the_snapshot(self) -> None:
        before_entities = len(self.snapshot.graph.entities())
        before_relationships = self.snapshot.graph.relationship_count
        before_snapshot_id = self.snapshot.snapshot_id
        self.select(intent=QueryIntent.SEARCH_ENTITIES, search_text="payment")
        self.select(intent=TRACE, http_method="POST", route_path="/payments")
        self.select(intent=QueryIntent.LIST_ENDPOINTS)
        self.assertEqual(len(self.snapshot.graph.entities()), before_entities)
        self.assertEqual(self.snapshot.graph.relationship_count, before_relationships)
        self.assertEqual(self.snapshot.snapshot_id, before_snapshot_id)

    def test_candidate_ordering_is_deterministic(self) -> None:
        first = self.select(intent=TRACE, http_method="POST", route_path="/payments")
        second = self.select(intent=TRACE, http_method="POST", route_path="/payments")
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_candidates_expose_no_source_text(self) -> None:
        result = self.select(intent=TRACE, http_method="POST", route_path="/payments")
        for candidate in result.candidates:
            payload = candidate.to_dict()
            self.assertEqual(
                sorted(payload),
                [
                    "basis",
                    "entity_id",
                    "entity_kind",
                    "language",
                    "matched_fields",
                    "name",
                    "qualified_name",
                    "relevance_score",
                    "repository_relative_path",
                    "source_location",
                ],
            )
            self.assertNotIn("def ", str(payload))
            self.assertNotIn("function ", str(payload))


class PartialAnalysisSelectionTests(unittest.TestCase):
    def test_partial_analysis_still_allows_selection_and_reports_completeness(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            snapshot = analyze(Path(raw), PARTIAL_SOURCE)
        self.assertGreater(snapshot.counts.partial_file_count, 0)
        self.assertIsNot(snapshot.analysis_completeness.value, "complete")
        document = next(
            item
            for item in snapshot.documents()
            if item.entity_kind is EntityKind.FUNCTION and item.name == "goodFunction"
        )
        result = select_canonical_entity(
            snapshot,
            QueryRequest(intent=QueryIntent.FIND_CALLERS, entity_id=document.entity_id),
            frozenset(),
        )
        self.assertIs(result.status, SelectionStatus.RESOLVED)


class SelectionModelTests(unittest.TestCase):
    def test_selection_result_rejects_inconsistent_states(self) -> None:
        from arctrellis.orchestration import SelectionResult

        with self.assertRaises(InvalidQueryRequestError):
            SelectionResult(
                status=SelectionStatus.AMBIGUOUS,
                selector_form=SelectorForm.ENTITY_ID,
                selector_text="x",
                selected_entity_id="abc",
                candidates=(),
                truncated=False,
                reason="x",
            )
        with self.assertRaises(InvalidQueryRequestError):
            SelectionResult(
                status=SelectionStatus.CANDIDATES,
                selector_form=SelectorForm.SEARCH_TEXT,
                selector_text="x",
                selected_entity_id=None,
                candidates=(),
                truncated=False,
                reason="x",
            )

    def test_analysis_snapshot_requires_a_graph(self) -> None:
        from arctrellis.orchestration import AnalysisCounts, AnalysisSnapshot

        with self.assertRaises(OrchestrationInvariantError):
            AnalysisSnapshot(
                counts=AnalysisCounts(
                    supported_file_count=0,
                    complete_file_count=0,
                    partial_file_count=0,
                    failed_file_count=0,
                    entity_count=0,
                    relationship_count=0,
                    endpoint_count=0,
                    test_count=0,
                    database_operation_count=0,
                    retrieval_document_count=0,
                    retrieval_term_count=0,
                ),
                analysis_completeness=self.snapshot_completeness(),
                graph=CodeGraph(),  # type: ignore[arg-type]
                retrieval=None,  # type: ignore[arg-type]
            )

    @staticmethod
    def snapshot_completeness():
        from arctrellis.query import AnalysisCompleteness

        return AnalysisCompleteness.UNKNOWN


class MixedSourceSelectionTests(unittest.TestCase):
    """Selection must be language independent and must not re-read source."""

    def test_candidates_span_python_javascript_and_typescript(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            snapshot = analyze(Path(raw), MIXED)
        endpoint_ids = {
            snapshot.document(identifier).entity_id  # type: ignore[union-attr]
            for identifier in snapshot.entities_with_route("POST", "/ts-payments")
        }
        self.assertTrue(endpoint_ids)
        request = QueryRequest(intent=TRACE, http_method="POST", route_path="/ts-payments")
        result = select_canonical_entity(snapshot, request, frozenset())
        self.assertIs(result.status, SelectionStatus.AMBIGUOUS)
        languages = {candidate.language for candidate in result.candidates}
        self.assertEqual(languages, {"typescript"})

    def test_language_constraint_narrows_a_qualified_name(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            snapshot = analyze(Path(raw), MIXED)
        request = QueryRequest(
            intent=QueryIntent.FIND_DIRECT_TESTS,
            qualified_name="payments.py::createPayment",
            language="python",
        )
        result = select_canonical_entity(snapshot, request, frozenset())
        self.assertIs(result.status, SelectionStatus.RESOLVED)
        mismatched = select_canonical_entity(
            snapshot,
            QueryRequest(
                intent=QueryIntent.FIND_DIRECT_TESTS,
                qualified_name="payments.py::createPayment",
                language="javascript",
            ),
            frozenset(),
        )
        self.assertIs(mismatched.status, SelectionStatus.NOT_FOUND)


class FixtureIntegrityTests(unittest.TestCase):
    def test_fixture_repositories_contain_the_expected_negative_cases(self) -> None:
        self.assertIn("/payments", PAYMENTS["app.py"])
        self.assertIn("persistPayment", EXPRESS["js/app.js"])
        self.assertIn("customClient", EXPRESS["js/app.js"])
        self.assertIn("db.commit()", PAYMENTS["payments.py"])
        self.assertIn("def broken(:", PARTIAL_SOURCE["broken.py"])
        self.assertEqual(len(TYPESCRIPT), 2)


if __name__ == "__main__":
    unittest.main()
