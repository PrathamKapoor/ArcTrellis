"""Static test identities and derivation records; never runtime coverage."""

from dataclasses import dataclass

from arctrellis.calls.ids import _identity
from arctrellis.calls.models import CallResolution, CallSite, _site_order
from arctrellis.core import CodeEntity, EntityKind, RelationshipKind, SourceLocation
from arctrellis.core.models import Metadata, _require_text, _validate_metadata
from arctrellis.extraction.source import _location, _span_metadata
from arctrellis.graph import CodeGraph
from arctrellis.ingestion import Language
from arctrellis.parsing import SyntaxSpan


@dataclass(frozen=True, slots=True)
class TestObservation:
    id: str
    path: str
    language: Language
    name: str
    parent_id: str
    declaration_entity_id: str | None
    location: SourceLocation
    span: SyntaxSpan
    callback_calls: tuple[CallSite, ...] = ()
    metadata: Metadata = ()

    def __post_init__(self) -> None:
        _validate_metadata(self.metadata)
        if any(not k.startswith("decorator_") for k, _ in self.metadata):
            raise ValueError("test observation metadata currently preserves decorators only")
        for value in (self.id, self.name, self.parent_id):
            _require_text(value, "test identity component")
        if not isinstance(self.language, Language) or not isinstance(self.span, SyntaxSpan):
            raise TypeError("test requires canonical language and coordinates")
        if self.location != _location(self.path, self.span):
            raise ValueError("test location must agree with its span")
        if self.declaration_entity_id is not None:
            _require_text(self.declaration_entity_id, "declaration_entity_id")
        if self.id != _test_id(self):
            raise ValueError("test identity does not match its components")
        if not isinstance(self.callback_calls, tuple) or any(not isinstance(c, CallSite) for c in self.callback_calls):
            raise TypeError("callback calls must be an immutable canonical tuple")
        if self.callback_calls != tuple(sorted(self.callback_calls, key=_site_order)) or len(
            {c.id for c in self.callback_calls}
        ) != len(self.callback_calls):
            raise ValueError("callback calls must be ordered and unique")
        for call in self.callback_calls:
            if (call.owner_entity_id, call.path, call.language) != (self.id, self.path, self.language) or not (
                self.span.start_byte <= call.span.start_byte <= call.span.end_byte <= self.span.end_byte
                and (self.span.start_line, self.span.start_column) <= (call.span.start_line, call.span.start_column)
                and (call.span.end_line, call.span.end_column) <= (self.span.end_line, self.span.end_column)
            ):
                raise ValueError("callback invocation must belong to this test")
        if self.declaration_entity_id is not None and self.callback_calls:
            raise ValueError("declaration tests reuse canonical call observations")


def _test_id(observation: TestObservation) -> str:
    return _identity(
        "arctrellis-test-v1",
        observation.language.value,
        observation.path,
        "declaration" if observation.declaration_entity_id else "callback",
        observation.declaration_entity_id,
        observation.parent_id,
        observation.span.start_byte,
        observation.span.end_byte,
        observation.name,
    )


def _test_entity(observation: TestObservation) -> CodeEntity:
    metadata = (
        _span_metadata(observation.span)
        + observation.metadata
        + (
            (
                "framework",
                "pytest_naming_convention" if observation.language is Language.PYTHON else "unknown_js_test_api",
            ),
        )
    )
    if observation.declaration_entity_id:
        metadata += (("declaration_entity_id", observation.declaration_entity_id),)
    return CodeEntity(
        observation.id,
        EntityKind.TEST,
        observation.name,
        f"{observation.path}::test:{observation.name}@{observation.span.start_byte}",
        location=observation.location,
        language=observation.language.value,
        parent_id=observation.parent_id,
        metadata=metadata,
    )


def _test_order(observation: TestObservation) -> tuple[str, int, int, str]:
    return observation.path, observation.span.start_byte, observation.span.end_byte, observation.id


@dataclass(frozen=True, slots=True)
class TestDerivation:
    test_entity_id: str
    call_relationship_id: str
    tests_relationship_id: str

    def __post_init__(self) -> None:
        for value in (self.test_entity_id, self.call_relationship_id, self.tests_relationship_id):
            _require_text(value, "derivation ID")


@dataclass(frozen=True, slots=True)
class TestAnalysisResult:
    graph: CodeGraph
    observations: tuple[TestObservation, ...]
    test_entities: tuple[CodeEntity, ...]
    callback_resolutions: tuple[CallResolution, ...]
    derivations: tuple[TestDerivation, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.graph, CodeGraph):
            raise TypeError("graph must be CodeGraph")
        groups = (
            (self.observations, TestObservation),
            (self.test_entities, CodeEntity),
            (self.callback_resolutions, CallResolution),
            (self.derivations, TestDerivation),
        )
        for records, kind in groups:
            if not isinstance(records, tuple) or any(not isinstance(r, kind) for r in records):
                raise TypeError("result records must be immutable canonical tuples")
        if self.observations != tuple(sorted(self.observations, key=_test_order)) or len(
            {o.id for o in self.observations}
        ) != len(self.observations):
            raise ValueError("result test observations must be unique and ordered")
        if self.test_entities != tuple(_test_entity(o) for o in self.observations):
            raise ValueError("test entities must match observations")
        if any(self.graph.get_entity(t.id) != t for t in self.test_entities):
            raise ValueError("graph must retain test identities")
        expected_sites = tuple(c.id for o in self.observations for c in o.callback_calls)
        if tuple(r.call_site_id for r in self.callback_resolutions) != expected_sites:
            raise ValueError("callback resolutions must match retained call order")
        tests = {t.id: o for t, o in zip(self.test_entities, self.observations, strict=True)}
        if len({d.tests_relationship_id for d in self.derivations}) != len(self.derivations):
            raise ValueError("test derivations must be unique")
        for derivation in self.derivations:
            observation = tests.get(derivation.test_entity_id)
            call = self.graph.get_relationship(derivation.call_relationship_id)
            edge = self.graph.get_relationship(derivation.tests_relationship_id)
            if (
                observation is None
                or call.kind is not RelationshipKind.CALLS
                or edge.kind is not RelationshipKind.TESTS
                or edge.source_entity_id != observation.id
                or call.source_entity_id != (observation.declaration_entity_id or observation.id)
                or edge.target_entity_id != call.target_entity_id
            ):
                raise ValueError("test derivation must retain its direct CALLS proof")

    @property
    def test_count(self) -> int:
        return len(self.test_entities)

    @property
    def resolved_test_relationship_count(self) -> int:
        return len(self.derivations)

    @property
    def linked_test_count(self) -> int:
        return len({d.test_entity_id for d in self.derivations})

    @property
    def unlinked_test_count(self) -> int:
        return self.test_count - self.linked_test_count
