"""Observation validation, snapshot ownership and security boundary contracts."""

import subprocess
import sys
import unittest
from dataclasses import fields, is_dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from arctrellis.core import EntityKind, RelationshipKind
from arctrellis.extraction import extract_entities
from arctrellis.frameworks import (
    EndpointResolutionStatus,
    FrameworkExtractionError,
    FrameworkResolutionInvariantError,
    HttpEndpointResolution,
    extract_framework_observations,
    resolve_http_endpoints,
)
from arctrellis.frameworks.ids import _observation_id
from arctrellis.indexing import FileIndexStatus, index_repository
from arctrellis.ingestion import Language
from arctrellis.parsing import ParsedSource, SyntaxNode, SyntaxSpan, parse_source

from .fixtures import http_sources
from .test_endpoints import analyze


class ObservationContracts(unittest.TestCase):
    def setUp(self):
        self.index, self.imports, self.calls, self.result = analyze(http_sources())
        self.route = self.index.route_observations[-1]

    def test_invalid_observation_inputs_and_revision_identity(self):
        for changes in (
            {"http_methods": ("post",)},
            {"http_methods": ("POST", "POST")},
            {"handler_reference": ("",)},
            {"owner_module_id": ""},
            {"route_path": "relative"},
            {"pre_handler_argument_count": -1},
            {"path": "../outside.py"},
            {"registration_kind": "direct_call"},
            {"handler_binding_supported": 1},
        ):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(self.route, **changes)
        changed = replace(self.route, route_path="/different")
        self.assertNotEqual(_observation_id(changed), self.route.id)
        self.assertEqual(_observation_id(self.route), self.route.id)

    def test_decorator_cannot_be_redirected_to_unrelated_declaration(self):
        index, _, _, _ = analyze(
            {
                "a.py": 'from fastapi import FastAPI\napp=FastAPI()\n@app.get("/x")\ndef h(): pass\n'
                "class C:\n def h(self): pass\n"
            }
        )
        route = index.route_observations[0]
        other = next(e for e in index.graph.entities() if e.kind is EntityKind.METHOD)
        metadata = dict(other.metadata)
        span = SyntaxSpan(
            *(
                int(metadata[k])
                for k in ("start_byte", "end_byte", "start_line", "start_column", "end_line", "end_column")
            )
        )
        with self.assertRaises(ValueError):
            replace(route, handler_declaration_span=span)
        with self.assertRaises(ValueError):
            replace(
                route,
                binding=replace(
                    route.binding,
                    span=SyntaxSpan(route.binding.span.start_byte, route.binding.span.end_byte, 999, 0, 999, 10),
                ),
            )

    def test_inconsistent_index_counts_owners_and_snapshot_proof_fail(self):
        with self.assertRaises(ValueError):
            replace(self.index, route_observations=())
        with self.assertRaises(ValueError):
            replace(self.index, route_observations=(replace(self.route, owner_module_id="missing"),))
        with self.assertRaises(FrameworkResolutionInvariantError):
            resolve_http_endpoints(self.index, self.imports, replace(self.calls, resolutions=()))
        edge = next(r for r in self.calls.graph.relationships() if r.kind is RelationshipKind.CALLS)
        from arctrellis.graph import CodeGraph

        graph = CodeGraph()
        for entity in self.calls.graph.entities():
            graph.add_entity(entity)
        for relationship in self.calls.graph.relationships():
            graph.add_relationship(
                replace(relationship, confidence_score=0.99) if relationship.id == edge.id else relationship
            )
        with self.assertRaises(FrameworkResolutionInvariantError):
            resolve_http_endpoints(self.index, self.imports, replace(self.calls, graph=graph))

    def test_resolution_records_reject_unsupported_selected_targets(self):
        with self.assertRaises(ValueError):
            HttpEndpointResolution("site", EndpointResolutionStatus.RESOLVED, "handler", (), "selected", "method")
        with self.assertRaises(ValueError):
            HttpEndpointResolution("site", EndpointResolutionStatus.AMBIGUOUS, None, ("one",), "many")
        with self.assertRaises(ValueError):
            HttpEndpointResolution("site", EndpointResolutionStatus.UNRESOLVED, "handler", (), "unknown")

    def test_no_source_tree_exception_or_bytes_survive_and_counts_match(self):
        pending = [
            self.index.route_observations,
            self.index.call_sites,
            self.index.file_results,
            self.result.observations,
            self.result.resolutions,
            self.result.graph.entities(),
            self.result.graph.relationships(),
        ]
        while pending:
            value = pending.pop()
            self.assertNotIsInstance(value, (ParsedSource, SyntaxNode, bytes, BaseException))
            if is_dataclass(value):
                pending.extend(getattr(value, f.name) for f in fields(value))
            elif isinstance(value, tuple):
                pending.extend(value)
        self.assertEqual(
            sum(f.route_observation_count for f in self.index.file_results), self.index.route_observation_count
        )
        self.assertEqual(
            [o.path for o in self.index.route_observations], sorted(o.path for o in self.index.route_observations)
        )

    def test_failed_framework_boundary_discards_calls_and_routes_but_other_files_survive(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.py").write_text("def a(): pass\na()\n", encoding="utf-8")
            (root / "b.py").write_text("def b(): pass\nb()\n", encoding="utf-8")
            actual = extract_framework_observations

            def injected(parsed, semantic):
                if parsed.path == "a.py":
                    raise FrameworkExtractionError("sensitive source must not escape")
                return actual(parsed, semantic)

            with patch("arctrellis.indexing.repository.extract_framework_observations", side_effect=injected):
                index = index_repository(root)
            self.assertEqual([f.status for f in index.file_results], [FileIndexStatus.FAILED, FileIndexStatus.COMPLETE])
            self.assertEqual(index.file_results[0].route_observation_count, 0)
            self.assertEqual(index.file_results[0].call_site_count, 0)
            self.assertNotIn("sensitive", index.file_results[0].error_message)
            self.assertEqual([c.path for c in index.call_sites], ["b.py"])

    def test_public_import_orders_in_fresh_interpreter(self):
        for first in ("frameworks", "indexing", "resolution", "calls"):
            code = f"import arctrellis.{first}; from arctrellis.frameworks import resolve_http_endpoints"
            completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_mixed_pipeline_deterministic_with_real_proof_and_express_trace(self):
        index, imports, calls, result = analyze(dict(reversed(list(http_sources().items()))))
        self.assertEqual(self.index.route_observations, index.route_observations)
        self.assertEqual(self.result.endpoints, result.endpoints)
        self.assertEqual(self.result.resolutions, result.resolutions)
        self.assertEqual(self.result.graph.relationships(), result.graph.relationships())
        endpoint = next(e for e in result.endpoints if e.name == "GET /users")
        target = next(e for e in result.graph.entities() if e.name == "sanitize")
        path = result.graph.shortest_path(endpoint.id, target.id)
        self.assertEqual([e.kind for e in path.relationships], [RelationshipKind.EXPOSES, RelationshipKind.CALLS])
        for edge in path.relationships:
            self.assertEqual(result.graph.get_relationship(edge.id).evidence, edge.evidence)
        self.assertFalse(any(r.kind is RelationshipKind.APPLIES_MIDDLEWARE for r in result.graph.relationships()))
        module_ids = {e.id for e in result.graph.entities() if e.kind is EntityKind.MODULE}
        handler_ids = {r.target_entity_id for r in result.graph.relationships() if r.kind is RelationshipKind.EXPOSES}
        self.assertFalse(
            any(
                r.kind is RelationshipKind.CALLS
                and r.source_entity_id in module_ids
                and r.target_entity_id in handler_ids
                for r in result.graph.relationships()
            )
        )

    def test_partial_express_and_python_methods_and_shadowed_class_receiver(self):
        _, _, _, result = analyze(
            {
                "a.js": 'import express from "express"; const app=express(); function h(){} '
                'app.get("/safe", h); function broken(\n'
            }
        )
        self.assertEqual([e.name for e in result.endpoints], ["GET /safe"])
        for shadow in ("", " app=other\n"):
            _, _, _, result = analyze(
                {
                    "a.py": "from fastapi import FastAPI\napp=FastAPI()\nclass C:\n"
                    + shadow
                    + ' @app.get("/x")\n def h(self): pass\n'
                }
            )
            self.assertEqual(result.endpoint_count, 0 if shadow else 1)
            if not shadow:
                edge = next(r for r in result.graph.relationships() if r.kind is RelationshipKind.EXPOSES)
                self.assertEqual(result.graph.get_entity(edge.target_entity_id).kind, EntityKind.METHOD)

    def test_source_revision_mismatch_and_escaped_route_spellings_are_explicit(self):
        parsed = parse_source("a.py", Language.PYTHON, b"def h(): pass\n")
        other = parse_source("b.py", Language.PYTHON, b"def h(): pass\n")
        with self.assertRaises(FrameworkExtractionError):
            extract_framework_observations(parsed, extract_entities(other))
        _, _, _, result = analyze(
            {
                "a.js": 'import express from "express"; const app=express(); function h(){} '
                'app.get("/escaped\\x2fx", h); app.get(`/dynamic/${name}`, h);'
            }
        )
        self.assertEqual(result.endpoint_count, 0)
        self.assertEqual(result.unsupported_count, 2)
