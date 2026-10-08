"""Immutable router configuration/mount observations, without runtime objects."""

from dataclasses import dataclass

from arctrellis.core import SourceLocation
from arctrellis.extraction.source import _location
from arctrellis.ingestion import DiscoveredFile, Language
from arctrellis.parsing import SyntaxSpan

from .ids import _identity
from .models import EndpointResolutionStatus, Framework, FrameworkBinding, HttpEndpointResolution, _contains, _text


def _validate_router_source(
    path: str,
    language: Language,
    framework: Framework,
    owner: str,
    binding: FrameworkBinding,
    span: SyntaxSpan,
    location: SourceLocation,
) -> None:
    _text(owner)
    if not isinstance(language, Language) or not isinstance(framework, Framework):
        raise TypeError("router framework/language must be canonical")
    DiscoveredFile(path, 0, language)
    if framework is Framework.FLASK or (language is Language.PYTHON) == (framework is Framework.EXPRESS):
        raise ValueError("router composition supports FastAPI and Express only")
    if not isinstance(span, SyntaxSpan) or not isinstance(binding, FrameworkBinding):
        raise TypeError("router observations require owned binding/coordinates")
    if location != _location(path, span):
        raise ValueError("router location must match coordinates")


def _prefix(value: str | None) -> None:
    if value is not None and (not isinstance(value, str) or value and not value.startswith("/")):
        raise ValueError("prefix must be empty, slash-prefixed or unsupported")


@dataclass(frozen=True, slots=True)
class RouterPrefixObservation:
    id: str
    path: str
    language: Language
    framework: Framework
    owner_module_id: str
    binding: FrameworkBinding
    prefix: str | None
    location: SourceLocation
    span: SyntaxSpan
    prefix_span: SyntaxSpan | None = None

    def __post_init__(self) -> None:
        _text(self.id)
        _validate_router_source(
            self.path, self.language, self.framework, self.owner_module_id, self.binding, self.span, self.location
        )
        _prefix(self.prefix)
        if self.binding.constructor != ("APIRouter" if self.framework is Framework.FASTAPI else "Router"):
            raise ValueError("router prefix requires canonical router constructor")
        if self.span != self.binding.span:
            raise ValueError("router configuration span must match its constructor")
        if self.prefix_span is not None and (
            not isinstance(self.prefix_span, SyntaxSpan) or not _contains(self.span, self.prefix_span)
        ):
            raise ValueError("prefix coordinates must fit constructor")


@dataclass(frozen=True, slots=True)
class RouterMountObservation:
    id: str
    path: str
    language: Language
    framework: Framework
    owner_module_id: str
    binding: FrameworkBinding
    router_reference: tuple[str, ...]
    prefix: str | None
    location: SourceLocation
    span: SyntaxSpan

    def __post_init__(self) -> None:
        _text(self.id)
        _validate_router_source(
            self.path, self.language, self.framework, self.owner_module_id, self.binding, self.span, self.location
        )
        _prefix(self.prefix)
        if not isinstance(self.router_reference, tuple) or any(
            not isinstance(p, str) or not p.replace("$", "_").isidentifier() for p in self.router_reference
        ):
            raise ValueError("router references must have simple identifier spelling")
        if self.binding.span.end_byte > self.span.start_byte or (
            self.binding.span.end_line,
            self.binding.span.end_column,
        ) > (self.span.start_line, self.span.start_column):
            raise ValueError("mounting binding must precede registration")


def _router_id(value: RouterPrefixObservation | RouterMountObservation) -> str:
    return _identity(
        "arctrellis-router-observation-v1",
        type(value).__name__,
        value.path,
        value.language.value,
        value.framework.value,
        value.owner_module_id,
        value.binding.name,
        value.binding.import_entity_id,
        value.binding.constructor,
        value.binding.span.start_byte,
        value.binding.span.end_byte,
        value.prefix,
        value.span.start_byte,
        value.span.end_byte,
        value.router_reference
        if isinstance(value, RouterMountObservation)
        else (None if value.prefix_span is None else (value.prefix_span.start_byte, value.prefix_span.end_byte)),
    )


def _router_order(value: RouterPrefixObservation | RouterMountObservation) -> tuple[str, int, int, str]:
    return value.path, value.span.start_byte, value.span.end_byte, value.id


@dataclass(frozen=True, slots=True)
class RouterMountResolution:
    observation_id: str
    status: EndpointResolutionStatus
    router_observation_id: str | None
    candidate_router_ids: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        HttpEndpointResolution(
            self.observation_id,
            self.status,
            self.router_observation_id,
            self.candidate_router_ids,
            self.reason,
            "static_router_mount" if self.status is EndpointResolutionStatus.RESOLVED else None,
        )
