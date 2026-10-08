"""Semantic summaries; no source bytes, syntax trees or exception objects."""

from dataclasses import dataclass
from enum import StrEnum

from arctrellis.calls.models import CallSite, _site_order
from arctrellis.core import EntityKind
from arctrellis.extraction.models import _entity_span
from arctrellis.frameworks.composition_models import (
    RouterMountObservation,
    RouterPrefixObservation,
    _router_id,
    _router_order,
)
from arctrellis.frameworks.flow_models import PreHandlerKind, PreHandlerObservation, _pre_id, _pre_order
from arctrellis.frameworks.models import HttpRouteObservation, _contains, _route_order
from arctrellis.graph import CodeGraph
from arctrellis.ingestion import DiscoveredFile, Language, RepositoryInventory


class FileIndexStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class FileIndexResult:
    path: str
    language: Language
    status: FileIndexStatus
    entity_count: int
    relationship_count: int
    diagnostic_count: int
    error_type: str | None = None
    error_message: str | None = None
    call_site_count: int = 0
    route_observation_count: int = 0
    pre_handler_observation_count: int = 0
    router_observation_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.language, Language) or not isinstance(self.status, FileIndexStatus):
            raise TypeError("language/status must be canonical enums")
        DiscoveredFile(self.path, 0, self.language)
        for count in (
            self.entity_count,
            self.relationship_count,
            self.diagnostic_count,
            self.call_site_count,
            self.route_observation_count,
            self.pre_handler_observation_count,
            self.router_observation_count,
        ):
            if type(count) is not int:
                raise TypeError("counts must be non-boolean integers")
            if count < 0:
                raise ValueError("counts must be nonnegative")
        if self.status is FileIndexStatus.FAILED:
            if any(
                (
                    self.entity_count,
                    self.relationship_count,
                    self.call_site_count,
                    self.route_observation_count,
                    self.pre_handler_observation_count,
                    self.router_observation_count,
                )
            ):
                raise ValueError("failed files cannot contribute graph records")
            for text in (self.error_type, self.error_message):
                if not isinstance(text, str):
                    raise TypeError("failure summaries require strings")
                if not text or text != text.strip() or len(text) > 512:
                    raise ValueError("failure strings must be bounded, nonempty and unpadded")
        elif self.error_type is not None or self.error_message is not None:
            raise ValueError("successful files cannot have failure fields")
        elif self.entity_count < 2 or self.relationship_count != self.entity_count - 1:
            raise ValueError("successful file counts include FILE, MODULE and their tree edges")
        if self.status is FileIndexStatus.COMPLETE and self.diagnostic_count:
            raise ValueError("complete files cannot have syntax diagnostics")


@dataclass(frozen=True, slots=True)
class RepositoryIndexResult:
    """Frozen summary shell owning an ordinary mutable CodeGraph.

    Treat graph as a completed snapshot; mutation can invalidate summary counts.
    No local root, parse tree, source contents or exception objects are retained.
    """

    inventory: RepositoryInventory
    graph: CodeGraph
    file_results: tuple[FileIndexResult, ...]
    call_sites: tuple[CallSite, ...] = ()
    route_observations: tuple[HttpRouteObservation, ...] = ()
    pre_handler_observations: tuple[PreHandlerObservation, ...] = ()
    router_prefix_observations: tuple[RouterPrefixObservation, ...] = ()
    router_mount_observations: tuple[RouterMountObservation, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.inventory, RepositoryInventory) or not isinstance(self.graph, CodeGraph):
            raise TypeError("inventory/graph must be canonical objects")
        if not isinstance(self.file_results, tuple) or any(
            not isinstance(f, FileIndexResult) for f in self.file_results
        ):
            raise TypeError("file_results must be an immutable summary tuple")
        expected = tuple((f.path, f.language) for f in self.inventory.supported_files)
        if tuple((f.path, f.language) for f in self.file_results) != expected:
            raise ValueError("one ordered outcome is required per supported inventory file")
        if (
            sum(f.entity_count for f in self.file_results) != self.graph.entity_count
            or sum(f.relationship_count for f in self.file_results) != self.graph.relationship_count
        ):
            raise ValueError("graph counts must match file summaries")
        if not isinstance(self.call_sites, tuple) or any(not isinstance(s, CallSite) for s in self.call_sites):
            raise TypeError("call_sites must be an immutable observation tuple")
        if self.call_sites != tuple(sorted(self.call_sites, key=_site_order)) or len(
            {s.id for s in self.call_sites}
        ) != len(self.call_sites):
            raise ValueError("call sites must be ordered and have unique IDs")
        counts: dict[str, int] = {}
        summaries = {f.path: f for f in self.file_results}
        entities = {e.id: e for e in self.graph.entities()}
        for site in self.call_sites:
            owner = entities.get(site.owner_entity_id)
            summary = summaries.get(site.path)
            if (
                owner is None
                or owner.kind not in (EntityKind.MODULE, EntityKind.FUNCTION, EntityKind.METHOD)
                or owner.location is None
                or owner.location.file_path != site.path
                or owner.language != site.language.value
                or summary is None
                or summary.language is not site.language
                or summary.status is FileIndexStatus.FAILED
            ):
                raise ValueError("call site requires an analyzed file and matching execution owner")
            span = _entity_span(owner)
            if (
                site.span.start_byte < span.start_byte
                or site.span.end_byte > span.end_byte
                or (site.span.start_line, site.span.start_column) < (span.start_line, span.start_column)
                or (site.span.end_line, site.span.end_column) > (span.end_line, span.end_column)
            ):
                raise ValueError("call site coordinates must fit its canonical owner")
            counts[site.path] = counts.get(site.path, 0) + 1
        if any(counts.get(f.path, 0) != f.call_site_count for f in self.file_results):
            raise ValueError("call site counts must match per-file summaries")
        if not isinstance(self.route_observations, tuple) or any(
            not isinstance(r, HttpRouteObservation) for r in self.route_observations
        ):
            raise TypeError("route observations must be an immutable canonical tuple")
        if self.route_observations != tuple(sorted(self.route_observations, key=_route_order)) or len(
            {r.id for r in self.route_observations}
        ) != len(self.route_observations):
            raise ValueError("route observations must be ordered with unique IDs")
        route_counts: dict[str, int] = {}
        for route in self.route_observations:
            module = entities.get(route.owner_module_id)
            summary = summaries.get(route.path)
            witness = entities.get(route.binding.import_entity_id)
            if (
                module is None
                or module.kind is not EntityKind.MODULE
                or module.location is None
                or module.location.file_path != route.path
                or module.language != route.language.value
                or summary is None
                or summary.status is FileIndexStatus.FAILED
                or summary.language is not route.language
                or witness is None
                or witness.kind is not EntityKind.IMPORT
                or witness.parent_id != module.id
            ):
                raise ValueError("route observation requires an analyzed module and import witness")
            span = _entity_span(module)
            if (
                route.span.start_byte < span.start_byte
                or route.span.end_byte > span.end_byte
                or route.binding.span.start_byte < span.start_byte
                or route.binding.span.end_byte > span.end_byte
                or (route.binding.span.start_line, route.binding.span.start_column)
                < (span.start_line, span.start_column)
                or (route.binding.span.end_line, route.binding.span.end_column) > (span.end_line, span.end_column)
                or (route.span.start_line, route.span.start_column) < (span.start_line, span.start_column)
                or (route.span.end_line, route.span.end_column) > (span.end_line, span.end_column)
                or _entity_span(witness).end_byte > route.binding.span.start_byte
            ):
                raise ValueError("route coordinates/provenance must fit the canonical module")
            route_counts[route.path] = route_counts.get(route.path, 0) + 1
        if any(route_counts.get(f.path, 0) != f.route_observation_count for f in self.file_results):
            raise ValueError("route observation counts must match file summaries")

        if not isinstance(self.pre_handler_observations, tuple) or any(
            not isinstance(p, PreHandlerObservation) for p in self.pre_handler_observations
        ):
            raise TypeError("pre-handlers must be an immutable canonical tuple")
        if self.pre_handler_observations != tuple(sorted(self.pre_handler_observations, key=_pre_order)) or len(
            {p.id for p in self.pre_handler_observations}
        ) != len(self.pre_handler_observations):
            raise ValueError("pre-handlers must be ordered and unique")
        routes = {r.id: r for r in self.route_observations}
        pre_counts: dict[str, int] = {}
        from arctrellis.frameworks.extraction import _constructor_import

        for p in self.pre_handler_observations:
            module = entities.get(p.owner_module_id)
            witness = entities.get(p.binding.import_entity_id)
            summary = summaries.get(p.path)
            if (
                module is None
                or module.kind is not EntityKind.MODULE
                or module.location is None
                or module.location.file_path != p.path
                or module.language != p.language.value
                or witness is None
                or witness.kind is not EntityKind.IMPORT
                or witness.parent_id != module.id
                or summary is None
                or summary.status is FileIndexStatus.FAILED
                or not _contains(_entity_span(module), p.span)
                or not _contains(_entity_span(module), p.binding.span)
                or _entity_span(witness).end_byte > p.binding.span.start_byte
                or p.id != _pre_id(p)
            ):
                raise ValueError("pre-handler requires valid analyzed module/provenance/coordinates/identity")
            constructor = _constructor_import(witness)
            if (
                constructor is None
                or constructor[0] is not p.framework
                or p.binding.constructor
                not in (("express", "Router") if p.framework.value == "express" else (constructor[1],))
            ):
                raise ValueError("pre-handler framework constructor witness disagrees")
            if p.route_observation_id:
                pre_route = routes.get(p.route_observation_id)
                if (
                    pre_route is None
                    or pre_route.binding != p.binding
                    or pre_route.framework is not p.framework
                    or pre_route.owner_module_id != p.owner_module_id
                    or not _contains(pre_route.span, p.span)
                ):
                    raise ValueError("pre-handler must belong to its exact route registration")
            if p.semantic_kind is PreHandlerKind.DEPENDENCY and p.provenance_import_id is not None:
                dependency = entities.get(p.provenance_import_id)
                if (
                    dependency is None
                    or dependency.kind is not EntityKind.IMPORT
                    or dependency.parent_id != module.id
                    or any(
                        dict(dependency.metadata).get(k) != v
                        for k, v in (
                            ("module", "fastapi"),
                            ("import_form", "from"),
                            ("relative_level", "0"),
                            ("imported_name", "Depends"),
                        )
                    )
                    or _entity_span(dependency).end_byte > p.span.start_byte
                ):
                    raise ValueError("dependency requires canonical FastAPI Depends import provenance")
            pre_counts[p.path] = pre_counts.get(p.path, 0) + 1
        if any(pre_counts.get(f.path, 0) != f.pre_handler_observation_count for f in self.file_results):
            raise ValueError("pre-handler counts must match file summaries")

        router_counts: dict[str, int] = {}
        groups: tuple[
            tuple[
                tuple[RouterPrefixObservation | RouterMountObservation, ...],
                type[RouterPrefixObservation] | type[RouterMountObservation],
            ],
            ...,
        ] = (
            (self.router_prefix_observations, RouterPrefixObservation),
            (self.router_mount_observations, RouterMountObservation),
        )
        for records, kind in groups:
            if not isinstance(records, tuple) or any(not isinstance(r, kind) for r in records):
                raise TypeError("router observations must be immutable canonical tuples")
            if records != tuple(sorted(records, key=_router_order)) or len({r.id for r in records}) != len(records):
                raise ValueError("router observations must be unique and ordered")
            for r in records:
                module = entities.get(r.owner_module_id)
                witness = entities.get(r.binding.import_entity_id)
                summary = summaries.get(r.path)
                if (
                    module is None
                    or module.kind is not EntityKind.MODULE
                    or module.location is None
                    or module.location.file_path != r.path
                    or module.language != r.language.value
                    or witness is None
                    or witness.kind is not EntityKind.IMPORT
                    or witness.parent_id != module.id
                    or summary is None
                    or summary.status is FileIndexStatus.FAILED
                    or not _contains(_entity_span(module), r.span)
                    or not _contains(_entity_span(module), r.binding.span)
                    or _entity_span(witness).end_byte > r.binding.span.start_byte
                    or r.id != _router_id(r)
                ):
                    raise ValueError("router requires exact analyzed module/provenance/identity")
                constructor = _constructor_import(witness)
                if (
                    constructor is None
                    or constructor[0] is not r.framework
                    or r.binding.constructor
                    not in (("express", "Router") if r.framework.value == "express" else (constructor[1],))
                ):
                    raise ValueError("router constructor witness disagrees")
                router_counts[r.path] = router_counts.get(r.path, 0) + 1
        if any(router_counts.get(f.path, 0) != f.router_observation_count for f in self.file_results):
            raise ValueError("router observation counts must match file summaries")

    @property
    def router_observation_count(self) -> int:
        return len(self.router_prefix_observations) + len(self.router_mount_observations)

    @property
    def pre_handler_observation_count(self) -> int:
        return len(self.pre_handler_observations)

    @property
    def route_observation_count(self) -> int:
        return len(self.route_observations)

    @property
    def call_site_count(self) -> int:
        return len(self.call_sites)

    @property
    def supported_file_count(self) -> int:
        return len(self.file_results)

    @property
    def complete_file_count(self) -> int:
        return sum(f.status is FileIndexStatus.COMPLETE for f in self.file_results)

    @property
    def partial_file_count(self) -> int:
        return sum(f.status is FileIndexStatus.PARTIAL for f in self.file_results)

    @property
    def failed_file_count(self) -> int:
        return sum(f.status is FileIndexStatus.FAILED for f in self.file_results)

    @property
    def is_complete(self) -> bool:
        return not self.partial_file_count and not self.failed_file_count

    @property
    def entity_count(self) -> int:
        return self.graph.entity_count

    @property
    def relationship_count(self) -> int:
        return self.graph.relationship_count
