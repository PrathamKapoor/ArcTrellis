"""Precise pre-handler roles normalized into the canonical middleware edge."""

from dataclasses import dataclass
from enum import StrEnum

from arctrellis.core import CodeEntity, SourceLocation
from arctrellis.extraction.source import _location
from arctrellis.graph import CodeGraph
from arctrellis.ingestion import DiscoveredFile, Language
from arctrellis.parsing import SyntaxSpan

from .ids import _identity
from .models import (
    Framework,
    FrameworkAnalysisResult,
    FrameworkBinding,
    HttpEndpointResolution,
    HttpRouteObservation,
    _text,
)


class PreHandlerKind(StrEnum):
    ROUTE_MIDDLEWARE = "route_middleware"
    DEPENDENCY = "dependency"
    REQUEST_HOOK = "request_hook"


@dataclass(frozen=True, slots=True)
class PreHandlerObservation:
    id: str
    path: str
    language: Language
    framework: Framework
    semantic_kind: PreHandlerKind
    owner_module_id: str
    binding: FrameworkBinding
    route_observation_id: str | None
    callable_reference: tuple[str, ...]
    order_index: int
    location: SourceLocation
    span: SyntaxSpan
    declaration_span: SyntaxSpan | None = None
    provenance_import_id: str | None = None
    binding_supported: bool = True

    def __post_init__(self) -> None:
        for value in (self.id, self.owner_module_id):
            _text(value)
        if not isinstance(self.language, Language) or not isinstance(self.framework, Framework):
            raise TypeError("pre-handler language/framework must be canonical")
        DiscoveredFile(self.path, 0, self.language)
        kinds = {
            Framework.EXPRESS: PreHandlerKind.ROUTE_MIDDLEWARE,
            Framework.FASTAPI: PreHandlerKind.DEPENDENCY,
            Framework.FLASK: PreHandlerKind.REQUEST_HOOK,
        }
        if not isinstance(self.semantic_kind, PreHandlerKind) or kinds[self.framework] is not self.semantic_kind:
            raise ValueError("pre-handler category must preserve framework meaning")
        if (self.language is Language.PYTHON) == (self.framework is Framework.EXPRESS):
            raise ValueError("pre-handler language/framework disagree")
        if not isinstance(self.span, SyntaxSpan) or not isinstance(self.binding, FrameworkBinding):
            raise TypeError("pre-handler requires owned coordinates/binding")
        if self.location != _location(self.path, self.span):
            raise ValueError("pre-handler location must match coordinates")
        if type(self.order_index) is not int or self.order_index < 0:
            raise ValueError("declared order must be a nonnegative integer")
        if type(self.binding_supported) is not bool:
            raise TypeError("binding support must be boolean")
        if not isinstance(self.callable_reference, tuple) or any(
            not isinstance(p, str) or not p.replace("$", "_").isidentifier() for p in self.callable_reference
        ):
            raise ValueError("references must be immutable simple identifier parts")
        if self.route_observation_id is not None:
            _text(self.route_observation_id)
        if self.semantic_kind is PreHandlerKind.REQUEST_HOOK:
            if self.route_observation_id is not None or not isinstance(self.declaration_span, SyntaxSpan):
                raise ValueError("request hooks require declaration coordinates and app binding")
            if not _contains(self.declaration_span, self.span):
                raise ValueError("hook declaration must contain its decorator")
        elif self.route_observation_id is None or self.declaration_span is not None:
            raise ValueError("route-local pre-handlers require a route identity")
        if self.semantic_kind is PreHandlerKind.DEPENDENCY and self.provenance_import_id is None:
            raise ValueError("dependency requires Depends import provenance")
        if self.provenance_import_id is not None:
            _text(self.provenance_import_id)
        if self.semantic_kind is not PreHandlerKind.DEPENDENCY and self.provenance_import_id is not None:
            raise ValueError("only dependencies carry Depends provenance")
        if self.binding.span.end_byte > self.span.start_byte or (
            self.binding.span.end_line,
            self.binding.span.end_column,
        ) > (self.span.start_line, self.span.start_column):
            raise ValueError("framework binding must precede pre-handler registration")


def _contains(outer: SyntaxSpan, inner: SyntaxSpan) -> bool:
    return (
        outer.start_byte <= inner.start_byte <= inner.end_byte <= outer.end_byte
        and (outer.start_line, outer.start_column) <= (inner.start_line, inner.start_column)
        and (inner.end_line, inner.end_column) <= (outer.end_line, outer.end_column)
    )


def _pre_order(p: PreHandlerObservation) -> tuple[str, int, int, str]:
    return p.path, p.span.start_byte, p.span.end_byte, p.id


def _pre_id(p: PreHandlerObservation) -> str:
    return _identity(
        "arctrellis-pre-handler-v1",
        p.framework.value,
        p.semantic_kind.value,
        p.path,
        p.language.value,
        p.owner_module_id,
        p.binding.name,
        p.binding.import_entity_id,
        p.binding.span.start_byte,
        p.binding.span.end_byte,
        p.route_observation_id,
        p.callable_reference,
        p.order_index,
        p.span.start_byte,
        p.span.end_byte,
        None if p.declaration_span is None else (p.declaration_span.start_byte, p.declaration_span.end_byte),
        p.provenance_import_id,
        p.binding_supported,
    )


@dataclass(frozen=True, slots=True)
class FrameworkFlowResult:
    """Independent graph plus immutable endpoint/pre-handler decisions."""

    analysis: FrameworkAnalysisResult
    pre_handler_observations: tuple[PreHandlerObservation, ...]
    pre_handler_resolutions: tuple[HttpEndpointResolution, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.analysis, FrameworkAnalysisResult):
            raise TypeError("flow requires canonical framework analysis")
        if not isinstance(self.pre_handler_observations, tuple) or any(
            not isinstance(p, PreHandlerObservation) for p in self.pre_handler_observations
        ):
            raise TypeError("pre-handler observations must be immutable")
        if self.pre_handler_observations != tuple(sorted(self.pre_handler_observations, key=_pre_order)) or len(
            {p.id for p in self.pre_handler_observations}
        ) != len(self.pre_handler_observations):
            raise ValueError("pre-handlers require unique ordered identities")
        if (
            not isinstance(self.pre_handler_resolutions, tuple)
            or any(not isinstance(r, HttpEndpointResolution) for r in self.pre_handler_resolutions)
            or tuple(r.observation_id for r in self.pre_handler_resolutions)
            != tuple(p.id for p in self.pre_handler_observations)
        ):
            raise ValueError("one ordered decision required per pre-handler")

    @property
    def graph(self) -> CodeGraph:
        return self.analysis.graph

    @property
    def endpoints(self) -> tuple[CodeEntity, ...]:
        return self.analysis.endpoints

    @property
    def route_observations(self) -> tuple[HttpRouteObservation, ...]:
        return self.analysis.observations

    @property
    def endpoint_resolutions(self) -> tuple[HttpEndpointResolution, ...]:
        return self.analysis.resolutions

    @property
    def resolved_pre_handler_count(self) -> int:
        return sum(r.status.value == "resolved" for r in self.pre_handler_resolutions)

    @property
    def unresolved_pre_handler_count(self) -> int:
        return sum(r.status.value == "unresolved" for r in self.pre_handler_resolutions)

    @property
    def ambiguous_pre_handler_count(self) -> int:
        return sum(r.status.value == "ambiguous" for r in self.pre_handler_resolutions)

    @property
    def unsupported_pre_handler_count(self) -> int:
        return sum(r.status.value == "unsupported" for r in self.pre_handler_resolutions)
