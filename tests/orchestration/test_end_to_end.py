"""End-to-end: analyze, snapshot, request, plan, selection, execution, bundle."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from arctrellis.core import EntityKind
from arctrellis.orchestration import (
    BundleStatus,
    PlanStep,
    QueryIntent,
    QueryRequest,
    SelectionStatus,
    analyze_repository,
    build_plan,
    intent_spec,
    run_query,
    select_canonical_entity,
)

from .repository import DUPLICATE_QUALIFIED_NAMES, MIXED, analyze, write_sources

_SAMPLE_REQUESTS = {
    QueryIntent.SEARCH_ENTITIES: QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="payment"),
    QueryIntent.LIST_ENDPOINTS: QueryRequest(intent=QueryIntent.LIST_ENDPOINTS),
    QueryIntent.LIST_DATABASE_CALLERS: QueryRequest(intent=QueryIntent.LIST_DATABASE_CALLERS),
    QueryIntent.TRACE_ENDPOINT_TO_DATABASE: QueryRequest(
        intent=QueryIntent.TRACE_ENDPOINT_TO_DATABASE, http_method="POST", route_path="/payments"
    ),
    QueryIntent.TRACE_CALLABLE_TO_DATABASE: QueryRequest(intent=QueryIntent.TRACE_CALLABLE_TO_DATABASE, entity_id="id"),
    QueryIntent.DIRECT_DATABASE_OPERATIONS: QueryRequest(intent=QueryIntent.DIRECT_DATABASE_OPERATIONS, entity_id="id"),
    QueryIntent.FIND_DIRECT_TESTS: QueryRequest(intent=QueryIntent.FIND_DIRECT_TESTS, entity_id="id"),
    QueryIntent.FIND_CALLERS: QueryRequest(intent=QueryIntent.FIND_CALLERS, entity_id="id"),
    QueryIntent.FIND_AFFECTED_ENDPOINTS: QueryRequest(intent=QueryIntent.FIND_AFFECTED_ENDPOINTS, entity_id="id"),
}


class EndToEndWorkflowTests(unittest.TestCase):
    """One complete flow, asserted against independently derived expectations."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls._temporary.name)
        write_sources(cls.root, MIXED)
        cls.snapshot = analyze_repository(cls.root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_search_then_select_then_trace_then_serialize(self) -> None:
        snapshot = self.snapshot

        # 1. search "list payments" -> ranked candidates, nothing selected
        search_request = QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="list payments")
        search_plan = build_plan(search_request)
        self.assertIs(search_plan.planned_output, "ranked_entity_candidates")
        search_bundle = run_query(snapshot, search_request)
        self.assertIs(search_bundle.status, BundleStatus.SEARCH_RESULTS)
        self.assertIsNone(search_bundle.selected_entity)
        self.assertTrue(search_bundle.search_hits)

        # 2. the caller chooses one endpoint candidate explicitly by its own name
        endpoint_candidates = [
            candidate
            for candidate in search_bundle.candidate_entities
            if candidate.entity_kind is EntityKind.API_ENDPOINT
        ]
        self.assertTrue(endpoint_candidates, "the fixture must expose endpoint candidates for 'list payments'")
        chosen = next(
            candidate
            for candidate in endpoint_candidates
            if candidate.name == "POST /payments" and candidate.repository_relative_path == "app.py"
        )

        # 3. plan and execute a structural query against that exact canonical ID
        trace_request = QueryRequest(
            intent=QueryIntent.TRACE_ENDPOINT_TO_DATABASE,
            entity_id=chosen.entity_id,
        )
        trace_plan = build_plan(trace_request)
        self.assertEqual(trace_plan.structural_query, "trace_endpoint_to_database")
        selection = select_canonical_entity(snapshot, trace_request, trace_plan.source_kinds)
        self.assertIs(selection.status, SelectionStatus.RESOLVED)
        self.assertEqual(selection.selected_entity_id, chosen.entity_id)

        bundle = run_query(snapshot, trace_request)
        self.assertIs(bundle.status, BundleStatus.EVIDENCE_PATHS)
        payload = bundle.to_dict()
        json.dumps(payload)

        # 4. the bundle agrees with the stored graph, independently re-read
        stored = {relationship.id: relationship for relationship in snapshot.graph.relationships()}
        for path in bundle.paths:
            self.assertEqual(path.entities[0].entity_id, chosen.entity_id)
            for index, relationship in enumerate(path.relationships):
                original = stored[relationship.relationship_id]
                self.assertEqual(original.kind.value, relationship.relationship_kind)
                self.assertEqual(
                    path.entities[index].entity_id,
                    original.source_entity_id,
                    "path entity order must follow stored edge direction",
                )
                self.assertEqual(path.entities[index + 1].entity_id, original.target_entity_id)
                self.assertTrue(original.evidence)
                for detail, original_evidence in zip(relationship.evidence, original.evidence, strict=True):
                    self.assertEqual(detail.evidence_id, original_evidence.id)
                    self.assertEqual(detail.file_path, original_evidence.location.file_path)
                    self.assertEqual(detail.start_line, original_evidence.location.start_line)
        self.assertEqual(payload["index_snapshot_id"], snapshot.snapshot_id)
        self.assertEqual(payload["analysis_completeness"], snapshot.analysis_completeness.value)

    def test_ambiguity_flow_stops_before_execution(self) -> None:
        bundle = run_query(
            self.snapshot,
            QueryRequest(
                intent=QueryIntent.TRACE_ENDPOINT_TO_DATABASE,
                http_method="POST",
                route_path="/payments",
            ),
        )
        self.assertIs(bundle.status, BundleStatus.AMBIGUOUS_SOURCE)
        self.assertEqual(bundle.paths, ())
        identifiers = [candidate.entity_id for candidate in bundle.candidate_entities]
        self.assertGreaterEqual(len(identifiers), 2)
        self.assertEqual(identifiers, sorted(identifiers))
        self.assertIn(
            "ambiguous_source_selection_requires_an_exact_entity_id",
            bundle.limitations,
        )
        json.dumps(bundle.to_dict())

    def test_class_import_collision_is_reported_not_guessed(self) -> None:
        found = run_query(
            self.snapshot,
            QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="PaymentService"),
        )
        named = [item for item in found.candidate_entities if item.name == "PaymentService"]
        kinds = {item.entity_kind for item in named}
        self.assertIn(EntityKind.CLASS, kinds)
        self.assertIn(EntityKind.IMPORT, kinds)
        self.assertIsNone(found.selected_entity)
        self.assertIn("lexical_relevance_is_not_entity_identity", found.limitations)

    def test_duplicate_qualified_name_flow_requires_an_exact_id(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            snapshot = analyze(Path(raw), DUPLICATE_QUALIFIED_NAMES)
        request = QueryRequest(intent=QueryIntent.FIND_CALLERS, qualified_name="js/dup.js::handler")
        plan = build_plan(request)
        selection = select_canonical_entity(snapshot, request, plan.source_kinds)
        self.assertIs(selection.status, SelectionStatus.AMBIGUOUS)
        bundle = run_query(snapshot, request)
        self.assertIs(bundle.status, BundleStatus.AMBIGUOUS_SOURCE)
        first = bundle.candidate_entities[0].entity_id
        resolved = run_query(
            snapshot,
            QueryRequest(intent=QueryIntent.FIND_CALLERS, entity_id=first),
        )
        self.assertIs(resolved.selection.status, SelectionStatus.RESOLVED)
        self.assertEqual(resolved.selected_entity.entity_id, first)  # type: ignore[union-attr]

    def test_every_intent_executes_against_the_same_snapshot(self) -> None:
        endpoint = next(
            identifier
            for identifier in self.snapshot.entities_with_route("POST", "/payments")
            if self.snapshot.document(identifier).repository_relative_path == "app.py"  # type: ignore[union-attr]
        )
        callable_id = next(
            document.entity_id
            for document in self.snapshot.documents()
            if document.qualified_name == "payments.py::createPayment"
        )
        requests = (
            QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="payment"),
            QueryRequest(intent=QueryIntent.LIST_ENDPOINTS),
            QueryRequest(intent=QueryIntent.LIST_DATABASE_CALLERS),
            QueryRequest(intent=QueryIntent.TRACE_ENDPOINT_TO_DATABASE, entity_id=endpoint),
            QueryRequest(intent=QueryIntent.TRACE_CALLABLE_TO_DATABASE, entity_id=callable_id),
            QueryRequest(intent=QueryIntent.DIRECT_DATABASE_OPERATIONS, entity_id=callable_id),
            QueryRequest(intent=QueryIntent.FIND_DIRECT_TESTS, entity_id=callable_id),
            QueryRequest(intent=QueryIntent.FIND_CALLERS, entity_id=callable_id),
            QueryRequest(intent=QueryIntent.FIND_AFFECTED_ENDPOINTS, entity_id=callable_id),
        )
        seen_intents = set()
        for request in requests:
            with self.subTest(intent=request.intent.value):
                bundle = run_query(self.snapshot, request)
                json.dumps(bundle.to_dict())
                seen_intents.add(bundle.request["intent"])
                self.assertEqual(bundle.index_snapshot_id, self.snapshot.snapshot_id)
                self.assertEqual(bundle.plan["intent"], request.intent.value)
        self.assertEqual(seen_intents, {intent.value for intent in QueryIntent})

    def test_source_kind_contract_matches_the_execution_backend(self) -> None:
        callable_intents = (
            QueryIntent.FIND_CALLERS,
            QueryIntent.FIND_DIRECT_TESTS,
            QueryIntent.TRACE_CALLABLE_TO_DATABASE,
            QueryIntent.FIND_AFFECTED_ENDPOINTS,
        )
        for intent in QueryIntent:
            spec = intent_spec(intent)
            with self.subTest(intent=intent.value):
                if intent is QueryIntent.TRACE_ENDPOINT_TO_DATABASE:
                    self.assertEqual(spec.source_kinds, frozenset((EntityKind.API_ENDPOINT,)))
                    self.assertEqual(spec.structural_query, "trace_endpoint_to_database")
                elif intent in callable_intents:
                    self.assertEqual(
                        spec.source_kinds,
                        frozenset((EntityKind.FUNCTION, EntityKind.METHOD)),
                    )
                    self.assertIsNotNone(spec.structural_query)
                    self.assertIn(PlanStep.SELECT_CANONICAL_ENTITY, plan_steps(intent))
                elif intent is QueryIntent.SEARCH_ENTITIES:
                    self.assertIsNone(spec.structural_query)
                    self.assertEqual(plan_steps(intent), (PlanStep.SEARCH_CANDIDATES, PlanStep.ASSEMBLE_EVIDENCE))
                elif intent is QueryIntent.DIRECT_DATABASE_OPERATIONS:
                    self.assertEqual(
                        spec.source_kinds,
                        frozenset((EntityKind.FUNCTION, EntityKind.METHOD, EntityKind.MODULE)),
                    )
                    self.assertIn(PlanStep.SELECT_CANONICAL_ENTITY, plan_steps(intent))
                else:
                    self.assertEqual(spec.source_kinds, frozenset())
                    self.assertIsNotNone(spec.structural_query)
                    self.assertNotIn(PlanStep.SELECT_CANONICAL_ENTITY, plan_steps(intent))


def plan_steps(intent: QueryIntent) -> tuple[PlanStep, ...]:
    """Return the planned steps for a representative valid request of an intent."""
    sample = _SAMPLE_REQUESTS[intent]
    return build_plan(sample).steps


class StagedAnalysisTests(unittest.TestCase):
    def test_mixed_language_repository_analysis_is_complete(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            snapshot = analyze(Path(raw), MIXED)
        languages = {document.language for document in snapshot.documents() if document.language is not None}
        self.assertEqual(languages, {"python", "javascript", "typescript"})
        self.assertGreater(snapshot.counts.endpoint_count, 0)
        self.assertGreater(snapshot.counts.test_count, 0)
        self.assertGreater(snapshot.counts.database_operation_count, 0)

    def test_no_target_code_is_executed_during_analysis(self) -> None:
        marker = Path(tempfile.gettempdir()) / "arctrellis_orchestration_must_not_exist.txt"
        self.assertFalse(marker.exists(), "a previous run leaked a side effect")
        sources = {
            "sideeffect.py": f"""import pathlib
pathlib.Path({str(marker)!r}).write_text("executed", encoding="utf-8")
""",
        }
        with tempfile.TemporaryDirectory() as raw:
            snapshot = analyze(Path(raw), sources)
        self.assertGreater(snapshot.counts.entity_count, 0)
        self.assertFalse(marker.exists(), "analysis must never execute target module code")


if __name__ == "__main__":
    unittest.main()
