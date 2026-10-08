"""Semantic summaries; no source bytes, syntax trees or exception objects."""

from dataclasses import dataclass
from enum import StrEnum

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

    def __post_init__(self) -> None:
        if not isinstance(self.language, Language) or not isinstance(self.status, FileIndexStatus):
            raise TypeError("language/status must be canonical enums")
        DiscoveredFile(self.path, 0, self.language)
        for count in (self.entity_count, self.relationship_count, self.diagnostic_count):
            if type(count) is not int:
                raise TypeError("counts must be non-boolean integers")
            if count < 0:
                raise ValueError("counts must be nonnegative")
        if self.status is FileIndexStatus.FAILED:
            if self.entity_count or self.relationship_count:
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
