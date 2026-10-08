"""Immutable metadata returned by repository discovery."""

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PureWindowsPath


class Language(StrEnum):
    """Languages recognized from filenames, without inspecting contents."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"


class SkipReason(StrEnum):
    """Intentional structural omissions from a complete scan."""

    EXCLUDED_DIRECTORY = "excluded_directory"
    SYMBOLIC_LINK = "symbolic_link"
    JUNCTION = "junction"
    REPARSE_POINT = "reparse_point"
    NON_REGULAR_FILE = "non_regular_file"


def _require_path(path: str) -> None:
    if not isinstance(path, str):
        raise TypeError("path must be a string")
    if (
        not path
        or PureWindowsPath(path).anchor
        or "\\" in path
        or any(ord(char) < 32 for char in path)
        or any(part in ("", ".", "..") for part in path.split("/"))
    ):
        raise ValueError("path must be an unmodified repository-relative forward-slash path")


@dataclass(frozen=True, slots=True)
class DiscoveredFile:
    """An ordinary file's relative path, byte size and optional supported language."""

    path: str
    size_bytes: int
    language: Language | None = None

    def __post_init__(self) -> None:
        _require_path(self.path)
        if type(self.size_bytes) is not int:
            raise TypeError("size_bytes must be an integer, not a boolean")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be >= 0")
        if self.language is not None and not isinstance(self.language, Language):
            raise TypeError("language must be Language or None")


@dataclass(frozen=True, slots=True)
class SkippedPath:
    """A relative path intentionally omitted, without enumerating its descendants."""

    path: str
    reason: SkipReason

    def __post_init__(self) -> None:
        _require_path(self.path)
        if not isinstance(self.reason, SkipReason):
            raise TypeError("reason must be SkipReason")


def _require_ordered_records(
    records: tuple[DiscoveredFile | SkippedPath, ...],
    record_type: type[DiscoveredFile] | type[SkippedPath],
    field: str,
) -> None:
    if not isinstance(records, tuple) or any(not isinstance(item, record_type) for item in records):
        raise TypeError(f"{field} must be a tuple of {record_type.__name__} records")
    paths = tuple(item.path for item in records)
    if paths != tuple(sorted(set(paths))):
        raise ValueError(f"{field} paths must be sorted and unique")


@dataclass(frozen=True, slots=True)
class RepositoryInventory:
    """Complete metadata for the visited tree; paths sort by Python string order.

    The caller retains the scan root separately. Policy omissions are explicit;
    unexpected filesystem failures never produce this result.
    """

    files: tuple[DiscoveredFile, ...] = ()
    skipped_paths: tuple[SkippedPath, ...] = ()

    def __post_init__(self) -> None:
        _require_ordered_records(self.files, DiscoveredFile, "files")
        _require_ordered_records(self.skipped_paths, SkippedPath, "skipped_paths")
        if {item.path for item in self.files} & {item.path for item in self.skipped_paths}:
            raise ValueError("files and skipped_paths must not overlap")

    @property
    def supported_files(self) -> tuple[DiscoveredFile, ...]:
        """Supported parser inputs in the same order as the full inventory."""
        return tuple(item for item in self.files if item.language is not None)

    @property
    def file_count(self) -> int:
        """Number of discovered ordinary files, including unsupported files."""
        return len(self.files)

    @property
    def supported_file_count(self) -> int:
        """Number of files recognized as supported source."""
        return sum(item.language is not None for item in self.files)

    @property
    def language_counts(self) -> tuple[tuple[Language, int], ...]:
        """Nonzero supported-language counts, ordered by canonical language value."""
        counts = Counter(item.language for item in self.files if item.language is not None)
        return tuple(sorted(counts.items()))
