"""Lightweight immutable route syntax, provenance and handler decisions."""

from dataclasses import dataclass
from enum import StrEnum

from arctrellis.core import CodeEntity, EntityKind, SourceLocation
from arctrellis.extraction.source import _location
from arctrellis.graph import CodeGraph
from arctrellis.ingestion import DiscoveredFile, Language
from arctrellis.parsing import SyntaxSpan

HTTP_METHODS = frozenset(("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"))


class Framework(StrEnum):
    FASTAPI = "fastapi"
    FLASK = "flask"
    EXPRESS = "express"


class EndpointResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


def _text(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("identity/reference fields must be strings")
    if not value or value != value.strip():
        raise ValueError("identity/reference fields must be nonempty and unpadded")


@dataclass(frozen=True, slots=True)
class FrameworkBinding:
    """One simple constructor binding and the canonical framework import witness."""

    name: str
    import_entity_id: str
    constructor: str
    span: SyntaxSpan
    path_completeness: str

    def __post_init__(self) -> None:
        for value in (self.name, self.import_entity_id, self.constructor):
            _text(value)
        if not self.name.replace("$", "_").isidentifier():
            raise ValueError("framework binding must be a simple identifier")
        if not isinstance(self.span, SyntaxSpan):
            raise TypeError("binding requires owned syntax coordinates")
        if self.path_completeness not in ("local", "declared"):
            raise ValueError("unknown path completeness")


@dataclass(frozen=True, slots=True)
class HttpRouteObservation:
    id: str
    path: str
    language: Language
    framework: Framework
    owner_module_id: str
    binding: FrameworkBinding
    http_methods: tuple[str, ...]
    route_path: str | None
    handler_reference: tuple[str, ...]
    handler_declaration_span: SyntaxSpan | None
    location: SourceLocation
    span: SyntaxSpan
    registration_kind: str
    pre_handler_argument_count: int = 0
    handler_binding_supported: bool = True

    def __post_init__(self) -> None:
        for value in (self.id, self.owner_module_id, self.registration_kind):
            _text(value)
        if not isinstance(self.language, Language) or not isinstance(self.framework, Framework):
            raise TypeError("route language/framework must be canonical enums")
        DiscoveredFile(self.path, 0, self.language)
        if (self.language is Language.PYTHON) == (self.framework is Framework.EXPRESS):
            raise ValueError("framework and language disagree")
        if not isinstance(self.binding, FrameworkBinding) or not isinstance(self.span, SyntaxSpan):
            raise TypeError("route requires owned binding/span values")
        if not isinstance(self.location, SourceLocation) or self.location != _location(self.path, self.span):
            raise ValueError("route location must match exact coordinates")
        if not isinstance(self.http_methods, tuple) or any(m not in HTTP_METHODS for m in self.http_methods):
            raise ValueError("methods must be an immutable supported method tuple")
        if self.http_methods != tuple(sorted(set(self.http_methods))):
            raise ValueError("methods must be sorted and unique")
        if self.route_path is not None and (
            not isinstance(self.route_path, str) or not self.route_path.startswith("/")
        ):
            raise ValueError("supported routes require a literal absolute application path")
        if not isinstance(self.handler_reference, tuple) or any(
            not isinstance(p, str) or not p.replace("$", "_").isidentifier() for p in self.handler_reference
        ):
            raise ValueError("handler reference must contain simple identifier spellings")
        if self.handler_declaration_span is not None and not isinstance(self.handler_declaration_span, SyntaxSpan):
            raise TypeError("handler declaration must use owned coordinates")
        if type(self.pre_handler_argument_count) is not int or self.pre_handler_argument_count < 0:
            raise ValueError("pre-handler argument count must be a nonnegative integer")
        if type(self.handler_binding_supported) is not bool:
            raise TypeError("handler binding support must be boolean")
        if self.registration_kind != ("direct_call" if self.framework is Framework.EXPRESS else "decorator"):
            raise ValueError("registration kind must match framework syntax")
        if self.framework is not Framework.EXPRESS:
            declaration = self.handler_declaration_span
            if declaration is None or (
                declaration.start_byte > self.span.start_byte
                or declaration.end_byte < self.span.end_byte
                or (declaration.start_line, declaration.start_column) > (self.span.start_line, self.span.start_column)
                or (declaration.end_line, declaration.end_column) < (self.span.end_line, self.span.end_column)
            ):
                raise ValueError("decorated handler declaration must contain the route decorator")
        if self.binding.span.end_byte > self.span.start_byte:
            raise ValueError("framework binding must precede registration")
        if (self.binding.span.end_line, self.binding.span.end_column) > (self.span.start_line, self.span.start_column):
            raise ValueError("framework binding points must precede registration")


def _route_order(route: HttpRouteObservation) -> tuple[str, int, int, str]:
    return route.path, route.span.start_byte, route.span.end_byte, route.id


@dataclass(frozen=True, slots=True)
class HttpEndpointResolution:
    observation_id: str
    status: EndpointResolutionStatus
    handler_entity_id: str | None
    candidate_entity_ids: tuple[str, ...]
    reason: str
    resolution_method: str | None = None

    def __post_init__(self) -> None:
        _text(self.observation_id)
        _text(self.reason)
        if not isinstance(self.status, EndpointResolutionStatus):
            raise TypeError("handler status must be canonical")
        if not isinstance(self.candidate_entity_ids, tuple):
            raise TypeError("candidates must be immutable")
        for value in self.candidate_entity_ids:
            _text(value)
        if self.candidate_entity_ids != tuple(sorted(set(self.candidate_entity_ids))):
            raise ValueError("candidates must be unique and sorted")
        if self.status is EndpointResolutionStatus.RESOLVED:
            if self.candidate_entity_ids != (self.handler_entity_id,) or self.resolution_method is None:
                raise ValueError("resolved handler requires one matching candidate and method")
            _text(self.resolution_method)
        elif self.handler_entity_id is not None or self.resolution_method is not None:
            raise ValueError("uncertain handler cannot have a selected target or method")
        elif self.status is EndpointResolutionStatus.AMBIGUOUS:
            if len(self.candidate_entity_ids) < 2:
                raise ValueError("ambiguous handler requires multiple witnesses")
        elif self.candidate_entity_ids:
            raise ValueError("unresolved/unsupported handler cannot have candidates")


@dataclass(frozen=True, slots=True)
class FrameworkAnalysisResult:
    graph: CodeGraph
    observations: tuple[HttpRouteObservation, ...]
    endpoints: tuple[CodeEntity, ...]
    resolutions: tuple[HttpEndpointResolution, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.graph, CodeGraph):
            raise TypeError("framework result requires CodeGraph")
        for records, expected in (
            (self.observations, HttpRouteObservation),
            (self.endpoints, CodeEntity),
            (self.resolutions, HttpEndpointResolution),
        ):
            if not isinstance(records, tuple) or any(not isinstance(r, expected) for r in records):
                raise TypeError("framework records must be immutable canonical tuples")
        if self.observations != tuple(sorted(self.observations, key=_route_order)) or len(
            {r.id for r in self.observations}
        ) != len(self.observations):
            raise ValueError("observations must have unique IDs in source order")
        if tuple(r.observation_id for r in self.resolutions) != tuple(r.id for r in self.observations):
            raise ValueError("one ordered resolution is required per observation")
        if len({e.id for e in self.endpoints}) != len(self.endpoints) or any(
            e.kind is not EntityKind.API_ENDPOINT or not self.graph.has_entity(e.id) or self.graph.get_entity(e.id) != e
            for e in self.endpoints
        ):
            raise ValueError("endpoints must be distinct and present in graph")

    @property
    def observation_count(self) -> int:
        return len(self.observations)

    @property
    def endpoint_count(self) -> int:
        return len(self.endpoints)

    @property
    def resolved_handler_count(self) -> int:
        return sum(r.status is EndpointResolutionStatus.RESOLVED for r in self.resolutions)

    @property
    def unresolved_handler_count(self) -> int:
        return sum(r.status is EndpointResolutionStatus.UNRESOLVED for r in self.resolutions)

    @property
    def ambiguous_handler_count(self) -> int:
        return sum(r.status is EndpointResolutionStatus.AMBIGUOUS for r in self.resolutions)

    @property
    def unsupported_count(self) -> int:
        return sum(r.status is EndpointResolutionStatus.UNSUPPORTED for r in self.resolutions)


def _contains(outer: SyntaxSpan, inner: SyntaxSpan) -> bool:
    return (
        outer.start_byte <= inner.start_byte <= inner.end_byte <= outer.end_byte
        and (outer.start_line, outer.start_column) <= (inner.start_line, inner.start_column)
        and (inner.end_line, inner.end_column) <= (outer.end_line, outer.end_column)
    )
