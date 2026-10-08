"""Semantic summaries; no source bytes, syntax trees or exception objects."""

from dataclasses import dataclass
from enum import StrEnum

from arctrellis.calls.models import CallSite, _site_order
from arctrellis.core import EntityKind
from arctrellis.extraction.models import _entity_span
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

    def __post_init__(self) -> None:
        if not isinstance(self.language, Language) or not isinstance(self.status, FileIndexStatus):
            raise TypeError("language/status must be canonical enums")
        DiscoveredFile(self.path, 0, self.language)
        for count in (self.entity_count, self.relationship_count, self.diagnostic_count, self.call_site_count):
            if type(count) is not int:
                raise TypeError("counts must be non-boolean integers")
            if count < 0:
                raise ValueError("counts must be nonnegative")
        if self.status is FileIndexStatus.FAILED:
            if self.entity_count or self.relationship_count or self.call_site_count:
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
