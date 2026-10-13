"""Structural execution and evidence bundles: reuse, preservation, honesty."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from arctrellis.core import EntityKind, RelationshipKind
from arctrellis.graph import CodeGraph
from arctrellis.orchestration import (
    SCHEMA_VERSION,
    BundleStatus,
    InvalidQueryRequestError,
    OrchestrationInvariantError,
    QueryIntent,
    QueryRequest,
    SelectionStatus,
    analyze_repository,
    build_plan,
    execute_plan,
    run_query,
    select_canonical_entity,
)

from .repository import MIXED, PARTIAL_SOURCE, analyze, write_sources

TRACE_ENDPOINT = QueryIntent.TRACE_ENDPOINT_TO_DATABASE
TRACE_CALLABLE = QueryIntent.TRACE_CALLABLE_TO_DATABASE


class BundleTestCase(unittest.TestCase):
    sources = MIXED

    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls._temporary.name)
        write_sources(cls.root, cls.sources)
        cls.snapshot = analyze_repository(cls.root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def endpoint_id(self, method: str, path: str, file: str) -> str:
        matches = [
            identifier
            for identifier in self.snapshot.entities_with_route(method, path)
            if (self.snapshot.document(identifier) or None) is not None
            and self.snapshot.document(identifier).repository_relative_path == file  # type: ignore[union-attr]
        ]
        self.assertEqual(len(matches), 1, f"expected one {method} {path} in {file}, found {len(matches)}")
        return matches[0]

    def run_request(self, **kwargs):
        intent = kwargs.pop("intent")
        return run_query(self.snapshot, QueryRequest(intent=intent, **kwargs))


class EndpointTraceTests(BundleTestCase):
    def test_python_endpoint_traces_to_a_database_write(self) -> None:
        endpoint = self.endpoint_id("POST", "/payments", "app.py")
        bundle = self.run_request(intent=TRACE_ENDPOINT, entity_id=endpoint)
        self.assertIs(bundle.status, BundleStatus.EVIDENCE_PATHS)
        self.assertIs(bundle.selection.status, SelectionStatus.RESOLVED)
        self.assertIsNotNone(bundle.selected_entity)
        kinds = [relationship.relationship_kind for path in bundle.paths for relationship in path.relationships]
        self.assertIn("EXPOSES", kinds)
        self.assertIn("CALLS", kinds)
        self.assertIn("WRITES_DATABASE", kinds)
        self.assertNotIn("READS_DATABASE", kinds)

    def test_javascript_prisma_endpoint_traces_to_a_write(self) -> None:
        endpoint = self.endpoint_id("POST", "/payments", "js/app.js")
        bundle = self.run_request(intent=TRACE_ENDPOINT, entity_id=endpoint)
        self.assertIs(bundle.status, BundleStatus.EVIDENCE_PATHS)
        write_edges = [
            relationship
            for path in bundle.paths
            for relationship in path.relationships
            if relationship.relationship_kind == "WRITES_DATABASE"
        ]
        self.assertTrue(write_edges)
        self.assertEqual(write_edges[0].confidence_score, 0.85)

    def test_read_endpoint_reports_a_read_edge_only(self) -> None:
        endpoint = self.endpoint_id("GET", "/payments", "js/app.js")
        bundle = self.run_request(intent=TRACE_ENDPOINT, entity_id=endpoint)
        kinds = [relationship.relationship_kind for path in bundle.paths for relationship in path.relationships]
        self.assertIn("READS_DATABASE", kinds)
        self.assertNotIn("WRITES_DATABASE", kinds)

    def test_route_with_no_database_path_reports_no_known_path(self) -> None:
        endpoint = self.endpoint_id("GET", "/reports", "app.py")
        bundle = self.run_request(intent=TRACE_ENDPOINT, entity_id=endpoint)
        self.assertIs(bundle.status, BundleStatus.NO_KNOWN_PATH)
        self.assertEqual(bundle.paths, ())
        self.assertIn("no_known_path_is_not_proof_of_absence", bundle.limitations)
        self.assertIs(bundle.selection.status, SelectionStatus.RESOLVED)

    def test_unresolved_call_endpoint_has_no_known_path(self) -> None:
        endpoint = self.endpoint_id("POST", "/ghost", "js/app.js")
        bundle = self.run_request(intent=TRACE_ENDPOINT, entity_id=endpoint)
        self.assertIs(bundle.status, BundleStatus.NO_KNOWN_PATH)

    def test_fake_orm_object_produces_no_database_relationship(self) -> None:
        endpoint = self.endpoint_id("POST", "/fake", "js/app.js")
        bundle = self.run_request(intent=TRACE_ENDPOINT, entity_id=endpoint)
        self.assertIs(bundle.status, BundleStatus.NO_KNOWN_PATH)
        graph_kinds = {
            relationship.kind
            for relationship in self.snapshot.graph.relationships()
            if relationship.source_entity_id == endpoint or relationship.target_entity_id == endpoint
        }
        self.assertNotIn(RelationshipKind.WRITES_DATABASE, graph_kinds)

    def test_ambiguous_endpoint_selector_never_executes(self) -> None:
        before = self.snapshot.graph.relationship_count
        bundle = self.run_request(intent=TRACE_ENDPOINT, http_method="POST", route_path="/payments")
        self.assertIs(bundle.status, BundleStatus.AMBIGUOUS_SOURCE)
        self.assertIs(bundle.selection.status, SelectionStatus.AMBIGUOUS)
        self.assertEqual(bundle.paths, ())
        self.assertIsNone(bundle.selected_entity)
        self.assertGreaterEqual(len(bundle.candidate_entities), 2)
        self.assertEqual(self.snapshot.graph.relationship_count, before)

    def test_unknown_entity_id_reports_not_found_source(self) -> None:
        bundle = self.run_request(intent=TRACE_ENDPOINT, entity_id="00000000-0000-0000-0000-000000000000")
        self.assertIs(bundle.status, BundleStatus.NOT_FOUND_SOURCE)
        self.assertEqual(bundle.paths, ())
        self.assertIn("selected_source_entity_does_not_exist_in_the_snapshot", bundle.limitations)


class GraphFactPreservationTests(BundleTestCase):
    def test_bundle_relationships_are_the_stored_records(self) -> None:
        endpoint = self.endpoint_id("POST", "/payments", "app.py")
        bundle = self.run_request(intent=TRACE_ENDPOINT, entity_id=endpoint)
        stored = {relationship.id: relationship for relationship in self.snapshot.graph.relationships()}
        checked = 0
        for path in bundle.paths:
            for relationship in path.relationships:
                original = stored[relationship.relationship_id]
                self.assertEqual(relationship.relationship_kind, original.kind.value)
                self.assertEqual(relationship.source_entity_id, original.source_entity_id)
                self.assertEqual(relationship.target_entity_id, original.target_entity_id)
                self.assertEqual(relationship.confidence, original.confidence.value)
                self.assertEqual(relationship.confidence_score, original.confidence_score)
                self.assertEqual(
                    [item.evidence_id for item in relationship.evidence],
                    [item.id for item in original.evidence],
                )
                for detail in relationship.evidence:
                    self.assertEqual(detail.file_path, detail.file_path)
                    self.assertFalse(detail.file_path.startswith("/"))
                    self.assertFalse(detail.file_path.startswith("\\"))
                    self.assertNotIn(":", detail.file_path)
                checked += 1
        self.assertGreater(checked, 0)

    def test_paths_follow_stored_forward_continuity(self) -> None:
        endpoint = self.endpoint_id("POST", "/payments", "app.py")
        bundle = self.run_request(intent=TRACE_ENDPOINT, entity_id=endpoint)
        for path in bundle.paths:
            for index, relationship in enumerate(path.relationships):
                self.assertEqual(relationship.source_entity_id, path.entities[index].entity_id)
                self.assertEqual(relationship.target_entity_id, path.entities[index + 1].entity_id)
                self.assertEqual(path.entities[0].entity_id, endpoint)

    def test_weakest_edge_confidence_is_preserved_not_multiplied(self) -> None:
        endpoint = self.endpoint_id("POST", "/payments", "app.py")
        bundle = self.run_request(intent=TRACE_ENDPOINT, entity_id=endpoint)
        for path in bundle.paths:
            scores = [relationship.confidence_score for relationship in path.relationships]
            self.assertEqual(path.weakest_edge_score, min(score for score in scores if score is not None))
            self.assertLessEqual(max(score for score in scores if score is not None), 1.0)

    def test_execution_does_not_add_relationships(self) -> None:
        endpoint = self.endpoint_id("POST", "/payments", "app.py")
        before_entities = len(self.snapshot.graph.entities())
        before_relationships = self.snapshot.graph.relationship_count
        for _ in range(3):
            self.run_request(intent=TRACE_ENDPOINT, entity_id=endpoint)
            self.run_request(intent=QueryIntent.FIND_CALLERS, entity_id=endpoint)
        self.assertEqual(len(self.snapshot.graph.entities()), before_entities)
        self.assertEqual(self.snapshot.graph.relationship_count, before_relationships)

    def test_imports_are_never_reported_as_calls(self) -> None:
        endpoint = self.endpoint_id("POST", "/payments", "app.py")
        bundle = self.run_request(intent=TRACE_ENDPOINT, entity_id=endpoint)
        for path in bundle.paths:
            for relationship in path.relationships:
                if relationship.relationship_kind == "CALLS":
                    original = next(
                        item for item in self.snapshot.graph.relationships() if item.id == relationship.relationship_id
                    )
                    self.assertIs(original.kind, RelationshipKind.CALLS)


class StructuralIntentTests(BundleTestCase):
    def test_callable_to_database_trace(self) -> None:
        function = next(
            document
            for document in self.snapshot.documents()
            if document.qualified_name == "payments.py::createPayment"
        )
        bundle = self.run_request(intent=TRACE_CALLABLE, qualified_name="payments.py::createPayment")
        self.assertIs(bundle.status, BundleStatus.EVIDENCE_PATHS)
        self.assertEqual(bundle.selected_entity.entity_id, function.entity_id)  # type: ignore[union-attr]
        kinds = {relationship.relationship_kind for path in bundle.paths for relationship in path.relationships}
        self.assertEqual(kinds, {"WRITES_DATABASE"})

    def test_direct_database_operations_are_listed(self) -> None:
        bundle = self.run_request(
            intent=QueryIntent.DIRECT_DATABASE_OPERATIONS,
            qualified_name="payments.py::listPayments",
        )
        self.assertIs(bundle.status, BundleStatus.EVIDENCE_PATHS)
        self.assertEqual(bundle.paths[0].relationships[0].relationship_kind, "READS_DATABASE")

    def test_operation_filter_narrows_the_trace(self) -> None:
        bundle = self.run_request(
            intent=TRACE_CALLABLE,
            qualified_name="payments.py::createPayment",
            operation_kinds=frozenset(("read",)),
        )
        self.assertIs(bundle.status, BundleStatus.NO_KNOWN_PATH)

    def test_direct_tests_are_found(self) -> None:
        bundle = self.run_request(
            intent=QueryIntent.FIND_DIRECT_TESTS,
            qualified_name="payments.py::createPayment",
        )
        self.assertIs(bundle.status, BundleStatus.EVIDENCE_PATHS)
        for path in bundle.paths:
            self.assertEqual({relationship.relationship_kind for relationship in path.relationships}, {"TESTS"})

    def test_symbol_without_a_direct_test_reports_no_known_path(self) -> None:
        bundle = self.run_request(
            intent=QueryIntent.FIND_DIRECT_TESTS,
            qualified_name="payments.py::listAllPayments",
        )
        self.assertIs(bundle.status, BundleStatus.NO_KNOWN_PATH)

    def test_find_callers_reports_the_caller_edge(self) -> None:
        bundle = self.run_request(
            intent=QueryIntent.FIND_CALLERS,
            qualified_name="payments.py::createPayment",
        )
        self.assertIs(bundle.status, BundleStatus.EVIDENCE_PATHS)
        for path in bundle.paths:
            self.assertEqual(path.direction, "reverse")
            self.assertEqual({relationship.relationship_kind for relationship in path.relationships}, {"CALLS"})

    def test_affected_endpoints_are_reported_for_a_service_method(self) -> None:
        bundle = self.run_request(
            intent=QueryIntent.FIND_AFFECTED_ENDPOINTS,
            qualified_name="payments.py::createPayment",
        )
        self.assertIs(bundle.status, BundleStatus.EVIDENCE_PATHS)
        kinds = {relationship.relationship_kind for path in bundle.paths for relationship in path.relationships}
        self.assertIn("EXPOSES", kinds)

    def test_endpoint_inventory_lists_registrations(self) -> None:
        bundle = self.run_request(intent=QueryIntent.LIST_ENDPOINTS, http_method="POST")
        self.assertIs(bundle.status, BundleStatus.INVENTORY)
        self.assertEqual(bundle.paths, ())
        self.assertTrue(bundle.candidate_entities)
        for candidate in bundle.candidate_entities:
            self.assertIs(candidate.entity_kind, EntityKind.API_ENDPOINT)

    def test_endpoint_inventory_filter_by_route(self) -> None:
        bundle = self.run_request(
            intent=QueryIntent.LIST_ENDPOINTS,
            http_method="GET",
            route_path="/reports",
        )
        self.assertIs(bundle.status, BundleStatus.INVENTORY)
        self.assertEqual(len(bundle.candidate_entities), 1)

    def test_empty_endpoint_inventory_reports_no_known_path(self) -> None:
        bundle = self.run_request(intent=QueryIntent.LIST_ENDPOINTS, http_method="GET", route_path="/absent")
        self.assertIs(bundle.status, BundleStatus.NO_KNOWN_PATH)

    def test_database_owner_inventory_reports_evidence_paths(self) -> None:
        bundle = self.run_request(intent=QueryIntent.LIST_DATABASE_CALLERS)
        self.assertIs(bundle.status, BundleStatus.EVIDENCE_PATHS)
        kinds = {relationship.relationship_kind for path in bundle.paths for relationship in path.relationships}
        self.assertTrue(kinds <= {"CALLS", "DEFINES", "READS_DATABASE", "WRITES_DATABASE"})
        self.assertIn("WRITES_DATABASE", kinds)


class SearchBehaviourTests(BundleTestCase):
    def test_search_returns_ranked_candidates_without_a_selected_entity(self) -> None:
        bundle = self.run_request(intent=QueryIntent.SEARCH_ENTITIES, search_text="payment creation")
        self.assertIs(bundle.status, BundleStatus.SEARCH_RESULTS)
        self.assertIsNone(bundle.selected_entity)
        self.assertEqual(bundle.paths, ())
        self.assertEqual(bundle.selection.status, SelectionStatus.CANDIDATES)
        self.assertTrue(bundle.search_hits)
        self.assertEqual(len(bundle.search_hits), len(bundle.candidate_entities))

    def test_search_bundle_has_no_fabricated_evidence_path(self) -> None:
        bundle = self.run_request(intent=QueryIntent.SEARCH_ENTITIES, search_text="persistPayment")
        self.assertEqual(bundle.paths, ())
        self.assertNotIn("relations", bundle.to_dict())

    def test_search_limitations_state_the_relevance_boundary(self) -> None:
        bundle = self.run_request(intent=QueryIntent.SEARCH_ENTITIES, search_text="payment")
        self.assertIn("lexical_relevance_is_not_entity_identity", bundle.limitations)
        self.assertIn("token_overlap_is_not_semantic_understanding", bundle.limitations)

    def test_search_truncation_is_propagated(self) -> None:
        bundle = self.run_request(
            intent=QueryIntent.SEARCH_ENTITIES,
            search_text="payment",
            max_examined_postings=1,
        )
        self.assertTrue(bundle.retrieval_truncation)
        self.assertTrue(bundle.truncated)
        self.assertIn("retrieval_budget_truncated_candidate_examination", bundle.limitations)


class BundleSerialisationTests(BundleTestCase):
    def test_bundle_is_json_serializable_and_versioned(self) -> None:
        bundle = self.run_request(intent=TRACE_ENDPOINT, entity_id=self.endpoint_id("POST", "/payments", "app.py"))
        payload = bundle.to_dict()
        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        json.dumps(payload)
        json.dumps(payload, sort_keys=True)

    def test_bundle_is_deterministic_across_runs(self) -> None:
        endpoint = self.endpoint_id("POST", "/payments", "app.py")
        first = self.run_request(intent=TRACE_ENDPOINT, entity_id=endpoint).to_dict()
        second = self.run_request(intent=TRACE_ENDPOINT, entity_id=endpoint).to_dict()
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_bundle_contains_no_absolute_paths_or_secrets(self) -> None:
        bundle = self.run_request(intent=TRACE_ENDPOINT, entity_id=self.endpoint_id("POST", "/payments", "app.py"))
        serialized = json.dumps(bundle.to_dict())
        self.assertNotIn(str(Path.home()), serialized)
        self.assertNotIn(":\\", serialized)
        self.assertNotIn("Traceback", serialized)
        for token in ("password", "secret", "api_key", "connection_string", "postgresql://"):
            self.assertNotIn(token, serialized.lower())

    def test_bundle_omits_declaration_signatures(self) -> None:
        bundle = self.run_request(intent=TRACE_ENDPOINT, entity_id=self.endpoint_id("POST", "/payments", "app.py"))
        serialized = json.dumps(bundle.to_dict())
        self.assertNotIn("signature", serialized)
        for entity in bundle.path_entities():
            self.assertNotIn("signature", entity.to_dict())
            self.assertNotIn("metadata", entity.to_dict())

    def test_bundle_reports_analysis_completeness_and_snapshot_identity(self) -> None:
        bundle = self.run_request(intent=TRACE_ENDPOINT, entity_id=self.endpoint_id("POST", "/payments", "app.py"))
        self.assertEqual(bundle.analysis_completeness.value, "complete")
        self.assertEqual(bundle.index_snapshot_id, self.snapshot.snapshot_id)

    def test_partial_analysis_is_reported_not_hidden(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            snapshot = analyze(Path(raw), PARTIAL_SOURCE)
        document = next(
            item
            for item in snapshot.documents()
            if item.entity_kind is EntityKind.FUNCTION and item.name == "goodFunction"
        )
        bundle = run_query(snapshot, QueryRequest(intent=QueryIntent.FIND_CALLERS, entity_id=document.entity_id))
        self.assertNotEqual(bundle.analysis_completeness.value, "complete")
        self.assertIn("source_analysis_was_partial_or_failed", bundle.limitations)

    def test_path_identifiers_are_unique_within_a_bundle(self) -> None:
        bundle = self.run_request(intent=QueryIntent.LIST_DATABASE_CALLERS)
        identifiers = [path.path_id for path in bundle.paths]
        self.assertEqual(len(identifiers), len(set(identifiers)))

    def test_bundle_rejects_an_inconsistent_projection(self) -> None:
        from arctrellis.orchestration import EvidenceBundle

        bundle = self.run_request(intent=TRACE_ENDPOINT, entity_id=self.endpoint_id("POST", "/payments", "app.py"))
        with self.assertRaises(InvalidQueryRequestError):
            EvidenceBundle(
                schema_version=99,
                status=bundle.status,
                request=bundle.request,
                plan=bundle.plan,
                selection=bundle.selection,
                selected_entity=bundle.selected_entity,
                candidate_entities=bundle.candidate_entities,
                search_hits=bundle.search_hits,
                paths=bundle.paths,
                analysis_completeness=bundle.analysis_completeness,
                retrieval_truncation=bundle.retrieval_truncation,
                graph_truncation=bundle.graph_truncation,
                limitations=bundle.limitations,
                index_snapshot_id=bundle.index_snapshot_id,
            )


class ExecutionContractTests(BundleTestCase):
    def test_execute_plan_requires_a_resolved_source(self) -> None:
        plan = build_plan(QueryRequest(intent=TRACE_ENDPOINT, entity_id="x"))
        with self.assertRaises(OrchestrationInvariantError):
            execute_plan(self.snapshot, plan, None)

    def test_execute_plan_rejects_a_non_snapshot(self) -> None:
        plan = build_plan(QueryRequest(intent=TRACE_ENDPOINT, entity_id="x"))
        with self.assertRaises(OrchestrationInvariantError):
            execute_plan(CodeGraph(), plan, "x")  # type: ignore[arg-type]

    def test_outcome_preserves_upstream_truncation(self) -> None:
        endpoint = self.endpoint_id("POST", "/payments", "app.py")
        plan = build_plan(QueryRequest(intent=TRACE_ENDPOINT, entity_id=endpoint, max_paths=1, max_expansions=2))
        selection = select_canonical_entity(self.snapshot, plan.request, plan.source_kinds)
        outcome = execute_plan(self.snapshot, plan, selection.selected_entity_id)
        self.assertTrue(outcome.graph_truncation)
        bundle = run_query(self.snapshot, plan.request)
        self.assertEqual(bundle.graph_truncation, outcome.graph_truncation)
        self.assertIn("structural_query_budget_truncated_enumeration", bundle.limitations)
