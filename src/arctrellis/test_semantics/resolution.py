"""Derive direct TESTS only after shared call resolution establishes CALLS."""

from __future__ import annotations

from typing import TYPE_CHECKING

from arctrellis.calls.models import CallResolutionStatus
from arctrellis.calls.resolution import _edge, _resolve, _Symbols
from arctrellis.core import Confidence, EntityKind, Evidence, Relationship, RelationshipKind
from arctrellis.frameworks.errors import FrameworkResolutionInvariantError
from arctrellis.frameworks.resolution import _validate_snapshots
from arctrellis.graph import CodeGraph

from .errors import TestAnalysisInvariantError
from .models import TestAnalysisResult, TestDerivation, _test_entity

if TYPE_CHECKING:
    from arctrellis.calls import CallResolutionResult
    from arctrellis.indexing import RepositoryIndexResult
    from arctrellis.resolution import ImportResolutionResult

from arctrellis.calls.ids import _identity


def analyze_tests(
    index: RepositoryIndexResult,
    imports: ImportResolutionResult,
    calls: CallResolutionResult,
    *,
    base_graph: CodeGraph | None = None,
) -> TestAnalysisResult:
    """Preserve a matching graph, add test identities and direct static proof.

    Optional base_graph may include framework enrichment; its original call
    facts must match the validated call snapshot. No source is reread.
    """
    try:
        _validate_snapshots(index, imports, calls)
    except FrameworkResolutionInvariantError as error:
        raise TestAnalysisInvariantError("test analysis requires matching analysis snapshots") from error
    base = calls.graph if base_graph is None else base_graph
    if not isinstance(base, CodeGraph):
        raise TypeError("base_graph must be CodeGraph")
    if any(base.get_entity(e.id) != e for e in calls.graph.entities()) or any(
        base.get_relationship(e.id) != e for e in calls.graph.relationships()
    ):
        raise ValueError("test input must preserve the call snapshot")
    if tuple(e for e in base.relationships() if e.kind is RelationshipKind.CALLS) != tuple(
        e for e in calls.graph.relationships() if e.kind is RelationshipKind.CALLS
    ) or any(e.kind is RelationshipKind.TESTS for e in base.relationships()):
        raise ValueError("test input cannot introduce extra call/test facts")
    graph = CodeGraph()
    for entity in base.entities():
        graph.add_entity(entity)
    for edge in base.relationships():
        graph.add_relationship(edge)
    observations = index.test_observations
    tests = tuple(_test_entity(o) for o in observations)
    for entity in tests:
        graph.add_entity(entity)
    for observation, entity in zip(observations, tests, strict=True):
        proof = Evidence(
            _identity("arctrellis-test-declaration-proof-v1", entity.id),
            observation.location,
            "static_test_declaration",
            entity.metadata,
        )
        graph.add_relationship(
            Relationship(
                _identity("arctrellis-test-defines-v1", entity.id),
                observation.parent_id,
                RelationshipKind.DEFINES,
                entity.id,
                Confidence.PROVEN,
                1.0,
                (proof,),
            )
        )
    symbols = _Symbols(
        {e.id: e for e in graph.entities()}, {}, {}, {}, {r.import_entity_id: r for r in imports.resolutions}
    )
    for entity in index.graph.entities():
        if entity.kind is EntityKind.FUNCTION:
            symbols.functions.setdefault((entity.parent_id, entity.name), []).append(entity)
        elif entity.kind is EntityKind.METHOD:
            symbols.methods.setdefault((entity.parent_id, entity.name), []).append(entity)
        elif entity.kind is EntityKind.IMPORT:
            binding = dict(entity.metadata).get("binding", "")
            if binding:
                symbols.imports.setdefault((entity.parent_id, binding), []).append(entity)
    outcomes = []
    for observation in observations:
        for site in observation.callback_calls:
            outcome = _resolve(site, symbols)
            outcomes.append(outcome)
            if outcome.status is CallResolutionStatus.RESOLVED:
                graph.add_relationship(_edge(site, outcome))
    declaration_tests = {o.declaration_entity_id for o in observations if o.declaration_entity_id is not None}
    derivations = []
    for observation in observations:
        owner = observation.declaration_entity_id or observation.id
        for call in graph.outgoing(owner, kind=RelationshipKind.CALLS):
            target = graph.get_entity(call.target_entity_id)
            if target.kind not in (EntityKind.FUNCTION, EntityKind.METHOD) or target.id in declaration_tests:
                continue
            method = (
                "python_direct_test_call" if observation.language.value == "python" else "ecmascript_direct_test_call"
            )
            evidence = tuple(
                Evidence(
                    _identity("arctrellis-tests-proof-v1", observation.id, e.id),
                    e.location,
                    method,
                    e.metadata + (("call_relationship_id", call.id),),
                )
                for e in call.evidence
            )
            edge = Relationship(
                _identity("arctrellis-tests-edge-v1", observation.id, call.id),
                observation.id,
                RelationshipKind.TESTS,
                target.id,
                Confidence.LIKELY,
                0.85,
                evidence,
            )
            graph.add_relationship(edge)
            derivations.append(TestDerivation(observation.id, call.id, edge.id))
    return TestAnalysisResult(graph, observations, tests, tuple(outcomes), tuple(derivations))
