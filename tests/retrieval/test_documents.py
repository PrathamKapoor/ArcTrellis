"""Canonical SearchDocument projection contracts; bounded, allowlisted, immutable."""

import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass
from json import dumps, loads

from arctrellis.core import CodeEntity, EntityKind, SourceLocation
from arctrellis.graph import CodeGraph
from arctrellis.retrieval import (
    SEARCHABLE_METADATA_KEYS,
    SearchDocument,
    SearchField,
    build_document,
    build_search_index,
)
from arctrellis.retrieval.errors import RetrievalInvariantError
from tests.retrieval.fixtures import empty_graph, entity, payment_graph


def document_of(index, identifier):
    found = index.document(identifier)
    assert found is not None, identifier
    return found


class DocumentProjectionTests(unittest.TestCase):
    def test_entity_identity_and_location_are_preserved(self):
        document = build_document(
            entity(
                "function:createPayment",
                EntityKind.FUNCTION,
                "createPayment",
                "payments.py::createPayment",
                path="payments.py",
                start=6,
                end=8,
                language="python",
            )
        )
        self.assertEqual(document.entity_id, "function:createPayment")
        self.assertEqual(document.entity_kind, EntityKind.FUNCTION)
        self.assertEqual(document.name, "createPayment")
        self.assertEqual(document.qualified_name, "payments.py::createPayment")
        self.assertEqual(document.repository_relative_path, "payments.py")
        self.assertEqual(document.source_location, SourceLocation("payments.py", 6, 8))
        self.assertEqual(document.language, "python")

    def test_missing_location_is_reported_explicitly_without_invented_lines(self):
        document = build_document(entity("module:x", EntityKind.MODULE, "payments", "payments", language="python"))
        self.assertIsNone(document.source_location)
        self.assertIsNone(document.repository_relative_path)
        self.assertIsNone(document.field("repository_relative_path"))
        self.assertIsNone(document.field_value("repository_relative_path"))
        self.assertEqual(document.field_tokens("repository_relative_path"), ())
        self.assertIsNone(document.to_dict()["source_location"])

    def test_endpoint_projection_keeps_canonical_route_metadata(self):
        document = document_of(build_search_index(payment_graph()), "endpoint:post-payments")
        self.assertEqual(document.field_value("http_method"), "POST")
        self.assertEqual(document.field_value("route_path"), "/payments")
        self.assertEqual(document.field_value("framework"), "fastapi")
        self.assertEqual(document.field_value("path_completeness"), "local")
        self.assertEqual(document.field_tokens("route_path"), ("payments",))
        self.assertEqual(document.field_tokens("http_method"), ("post",))
        self.assertEqual(document.field_tokens("repository_relative_path"), ("app", "py"))

    def test_dynamic_route_parameters_are_preserved_in_canonical_metadata(self):
        document = document_of(build_search_index(payment_graph()), "endpoint:get-users-id")
        self.assertEqual(document.field_value("route_path"), "/users/{id}")
        self.assertEqual(document.field_tokens("route_path"), ("users", "id"))

    def test_test_projection(self):
        document = document_of(build_search_index(payment_graph()), "test:create-payment")
        self.assertEqual(document.entity_kind, EntityKind.TEST)
        self.assertEqual(document.field_tokens("name"), ("test", "create", "payment"))
        self.assertEqual(document.field_value("framework"), "pytest_naming_convention")
        self.assertEqual(document.field_tokens("entity_kind"), ("test",))

    def test_database_operation_projection(self):
        document = document_of(build_search_index(payment_graph()), "db:insert")
        self.assertEqual(document.entity_kind, EntityKind.DATABASE_OPERATION)
        self.assertEqual(document.field_value("provider"), "sqlalchemy")
        self.assertEqual(document.field_value("operation_kind"), "write")
        self.assertEqual(document.field_value("operation_name"), "execute")
        self.assertEqual(document.field_value("target_name"), "Payment")
        self.assertEqual(document.field_value("effect_stage"), "statement_execution")
        self.assertEqual(document.field_tokens("target_name"), ("payment",))

    def test_import_projection(self):
        document = document_of(build_search_index(payment_graph()), "import:persist")
        self.assertEqual(document.entity_kind, EntityKind.IMPORT)
        self.assertEqual(document.field_value("import_form"), "from")
        self.assertEqual(document.field_value("module"), "payments")
        self.assertEqual(document.field_value("imported_name"), "persist_payment")
        self.assertEqual(document.field_value("binding"), "persist_payment")
        self.assertEqual(document.field_tokens("imported_name"), ("persist", "payment"))

    def test_mixed_language_projection(self):
        graph = CodeGraph()
        for identifier, kind, name, language in (
            ("py", EntityKind.FUNCTION, "create_payment", "python"),
            ("js", EntityKind.FUNCTION, "createPayment", "javascript"),
            ("ts", EntityKind.CLASS, "PaymentService", "typescript"),
        ):
            graph.add_entity(
                entity(identifier, kind, name, f"{identifier}.x::{name}", path=f"{identifier}.x", language=language)
            )
        index = build_search_index(graph)
        self.assertEqual([document.language for document in index.documents], ["javascript", "python", "typescript"])
        self.assertEqual(document_of(index, "ts").field_tokens("language"), ("typescript",))

    def test_arbitrary_metadata_is_excluded_by_allowlist(self):
        record = entity(
            "entity:leaky",
            EntityKind.FUNCTION,
            "handle",
            "leaky.py::handle",
            path="leaky.py",
            metadata=(
                ("framework", "fastapi"),
                ("statement_kind", "insert"),
                ("statement_start_byte", "9182"),
                ("decorator_name", "require_admin"),
                ("observation_id", "obs-1"),
                ("router_prefix_observation_id", "obs-2"),
                ("module", "payments"),
            ),
        )
        document = build_document(record)
        names = {item.name for item in document.fields}
        self.assertEqual(
            names, {"entity_kind", "framework", "module", "name", "qualified_name", "repository_relative_path"}
        )
        for excluded in (
            "statement_kind",
            "statement_start_byte",
            "decorator_name",
            "observation_id",
            "router_prefix_observation_id",
        ):
            self.assertNotIn(excluded, names)
        self.assertEqual(
            set(SEARCHABLE_METADATA_KEYS) - names,
            {
                "alias",
                "binding",
                "composition_scope",
                "effect_stage",
                "http_method",
                "import_form",
                "imported_name",
                "is_type_only",
                "operation_kind",
                "operation_name",
                "path_completeness",
                "provider",
                "registration_kind",
                "route_path",
                "target_basis",
                "target_name",
            },
        )
        for item in document.fields:
            self.assertNotIn("9182", item.tokens)
            self.assertNotIn("require_admin", item.tokens)

    def test_signature_literals_are_not_indexed(self):
        document = build_document(
            entity(
                "entity:signatures",
                EntityKind.FUNCTION,
                "verify",
                "leaky.py::verify",
                path="leaky.py",
                signature='def verify(token: str = "TOP_SECRET_LITERAL") -> Literal["other_secret"]: ...',
            )
        )
        tokens = document.tokens
        self.assertNotIn("top_secret_literal", tokens)
        self.assertNotIn("other_secret", tokens)
        self.assertNotIn("literal", tokens)
        self.assertIn("verify", tokens)

    def test_empty_metadata_values_are_not_projected(self):
        document = build_document(
            entity(
                "entity:x",
                EntityKind.DATABASE_OPERATION,
                "unknown:execute@1",
                "a.py::database:x",
                metadata=(("target_name", ""),),
            )
        )
        self.assertIsNone(document.field("target_name"))

    def test_repeated_tokens_are_preserved_with_frequencies(self):
        document = document_of(build_search_index(payment_graph()), "class:PaymentService")
        self.assertEqual(document.tokens.count("payment"), 2)
        self.assertEqual(document.tokens.count("service"), 2)
        self.assertEqual(document.token_count, len(document.tokens))
        self.assertIn("payment", document.distinct_tokens)
        self.assertEqual(document.field_tokens("name"), ("payment", "service"))

    def test_document_is_immutable_and_json_primitive(self):
        document = build_document(entity("entity:x", EntityKind.MODULE, "x", "x", path="x.py"))
        with self.assertRaises(FrozenInstanceError):
            document.name = "other"
        with self.assertRaises(TypeError):
            document._by_name["name"] = SearchField("name", "other", ("other",))
        payload = document.to_dict()
        self.assertEqual(loads(dumps(payload)), payload)

    def test_field_contracts_are_validated(self):
        document = build_document(entity("entity:x", EntityKind.MODULE, "x", "x", path="x.py"))
        name_field = document.field("name")
        self.assertIsNotNone(name_field)
        with self.assertRaises(RetrievalInvariantError):
            SearchField("name", "PaymentService", ("wrong",))
        with self.assertRaises(ValueError):
            SearchField("", "value", ("value",))
        with self.assertRaises(TypeError):
            SearchField("name", "value", ["value"])

    def test_document_field_order_is_deterministic(self):
        first = build_document(
            entity("a", EntityKind.MODULE, "a", "a", path="a.py", metadata=(("module", "m"), ("alias", "b")))
        )
        second = build_document(
            entity("a", EntityKind.MODULE, "a", "a", path="a.py", metadata=(("alias", "b"), ("module", "m")))
        )
        self.assertEqual(first, second)
        self.assertEqual(tuple(item.name for item in first.fields), tuple(sorted(item.name for item in first.fields)))

    def test_documents_reject_inconsistent_paths_and_unknown_types(self):
        with self.assertRaises(TypeError):
            SearchDocument("e", "FUNCTION", "n", "q", None, None, None, ())
        with self.assertRaises(TypeError):
            build_document("not an entity")
        with self.assertRaises(ValueError):
            SearchDocument(
                "e",
                EntityKind.MODULE,
                "n",
                "q",
                "python",
                None,
                "a.py",
                None,
                (),
            )

    def test_search_document_model_exposes_only_declared_fields(self):
        document = build_document(entity("entity:x", EntityKind.MODULE, "x", "x", path="x.py"))
        self.assertTrue(is_dataclass(document))
        declared = tuple(item.name for item in fields(document))
        self.assertEqual(
            declared,
            (
                "entity_id",
                "entity_kind",
                "name",
                "qualified_name",
                "language",
                "parent_id",
                "repository_relative_path",
                "source_location",
                "fields",
                "_by_name",
            ),
        )

    def test_empty_graph_produces_no_documents(self):
        index = build_search_index(empty_graph())
        self.assertEqual(index.documents, ())
        self.assertTrue(index.empty)
        self.assertEqual(index.document_count, 0)
        self.assertEqual(index.average_document_length, 0.0)

    def test_one_entity_produces_exactly_one_document(self):
        graph = CodeGraph()
        graph.add_entity(CodeEntity("only", EntityKind.MODULE, "payments", "payments", language="python"))
        index = build_search_index(graph)
        self.assertEqual([document.entity_id for document in index.documents], ["only"])

    def test_one_entity_is_not_duplicated_by_its_relationships(self):
        graph = payment_graph()
        index = build_search_index(graph)
        identifiers = [document.entity_id for document in index.documents]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertEqual(index.document_count, graph.entity_count)


if __name__ == "__main__":
    unittest.main()
