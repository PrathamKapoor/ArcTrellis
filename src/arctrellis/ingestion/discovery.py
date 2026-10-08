"""Synchronous metadata-only discovery of a stable, local directory tree.

No target contents are opened. Links and Windows reparse points are not followed.
Pathname checks cannot provide atomic containment against concurrent hostile
filesystem changes; callers must keep the tree stable throughout the scan.
"""

from collections.abc import Set
import os
from pathlib import Path, PurePosixPath
import stat

from .errors import InvalidRepositoryPathError, RepositoryAccessError
from .models import DiscoveredFile, Language, RepositoryInventory, SkippedPath, SkipReason


DEFAULT_EXCLUDED_DIRECTORIES: frozenset[str] = frozenset({
    ".git", "node_modules", ".venv", "venv", "env", "__pycache__", "dist", "build",
    "coverage", ".coverage", ".next", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".cache", "vendor",
})

_EXTENSIONS = {
    ".py": Language.PYTHON, ".pyi": Language.PYTHON,
    ".js": Language.JAVASCRIPT, ".jsx": Language.JAVASCRIPT,
    ".mjs": Language.JAVASCRIPT, ".cjs": Language.JAVASCRIPT,
    ".ts": Language.TYPESCRIPT, ".tsx": Language.TYPESCRIPT,
    ".mts": Language.TYPESCRIPT, ".cts": Language.TYPESCRIPT,
}


def _link_reason(metadata: os.stat_result) -> SkipReason | None:
    if stat.S_ISLNK(metadata.st_mode):
        return SkipReason.SYMBOLIC_LINK
    if getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        if getattr(metadata, "st_reparse_tag", 0) == stat.IO_REPARSE_TAG_MOUNT_POINT:
            return SkipReason.JUNCTION
        return SkipReason.REPARSE_POINT
    return None


def _normalize_root(root: str | os.PathLike[str]) -> tuple[Path, os.stat_result]:
    raw = os.fspath(root)
    if not isinstance(raw, str):
        raise TypeError("root must be a string or a path with string representation")
    if not raw or "\x00" in raw:
        raise InvalidRepositoryPathError("root must be a nonempty local directory path")
    normalized = Path(os.path.abspath(raw))
    metadata = None
    for component in (*reversed(normalized.parents), normalized):
        try:
            metadata = os.lstat(component)
        except (FileNotFoundError, NotADirectoryError) as error:
            raise InvalidRepositoryPathError(f"repository directory does not exist: {component}") from error
        except OSError as error:
            raise RepositoryAccessError(f"cannot inspect repository root: {component}") from error
        if _link_reason(metadata) is not None or not stat.S_ISDIR(metadata.st_mode):
            raise InvalidRepositoryPathError(f"root and ancestors must be ordinary directories: {component}")
    assert metadata is not None
    return normalized, metadata


def _excluded_names(names: Set[str]) -> frozenset[str]:
    if not isinstance(names, (set, frozenset)):
        raise TypeError("excluded_directories must be a set or frozenset of directory names")
    for name in names:
        if not isinstance(name, str):
            raise TypeError("excluded directory names must be strings")
        if (not name or name in (".", "..") or "/" in name or "\\" in name
                or ":" in name or any(ord(char) < 32 for char in name)):
            raise ValueError("excluded directories must be single directory names")
    return frozenset(names)


def _check_directory(path: Path, expected: os.stat_result) -> None:
    current = os.lstat(path)
    if (_link_reason(current) is not None or not stat.S_ISDIR(current.st_mode)
            or (current.st_dev, current.st_ino) != (expected.st_dev, expected.st_ino)):
        raise RepositoryAccessError(f"directory changed during discovery: {path}")


def _walk_directory(root: Path, metadata: os.stat_result, excluded: frozenset[str]) -> RepositoryInventory:
    files: list[DiscoveredFile] = []
    skipped: list[SkippedPath] = []
    pending = [(root, metadata)]
    while pending:
        directory, expected = pending.pop()
        try:
            _check_directory(directory, expected)
            with os.scandir(directory) as entries:
                for entry in entries:
                    path = directory / entry.name
                    relative = path.relative_to(root).as_posix()
                    info = entry.stat(follow_symlinks=False)
                    reason = _link_reason(info)
                    if reason is not None:
                        skipped.append(SkippedPath(relative, reason))
                    elif stat.S_ISDIR(info.st_mode):
                        if entry.name in excluded:
                            skipped.append(SkippedPath(relative, SkipReason.EXCLUDED_DIRECTORY))
                        else:
                            # Windows DirEntry.stat reports zero identity fields.
                            pending.append((path, os.lstat(path)))
                    elif stat.S_ISREG(info.st_mode):
                        language = _EXTENSIONS.get(PurePosixPath(relative).suffix.lower())
                        files.append(DiscoveredFile(relative, info.st_size, language))
                    else:
                        skipped.append(SkippedPath(relative, SkipReason.NON_REGULAR_FILE))
            _check_directory(directory, expected)
        except OSError as error:
            raise RepositoryAccessError(f"filesystem inspection failed under: {directory}: {error}") from error
        except ValueError as error:
            raise RepositoryAccessError(f"filesystem metadata is not representable under: {directory}: {error}") from error
    return RepositoryInventory(tuple(sorted(files, key=lambda item: item.path)),
                               tuple(sorted(skipped, key=lambda item: item.path)))


def scan_repository(
    root: str | os.PathLike[str], *,
    excluded_directories: Set[str] = DEFAULT_EXCLUDED_DIRECTORIES,
) -> RepositoryInventory:
    """Inventory a local directory without reading or executing its files.

    Exclusion names replace defaults and match exactly at any depth. Links are
    always skipped regardless of exclusions. Hidden directories are otherwise
    ordinary directories; .gitignore is not interpreted. Unexpected errors fail
    the entire scan. The input tree must remain stable during inspection.
    """
    excluded = _excluded_names(excluded_directories)
    normalized, metadata = _normalize_root(root)
    return _walk_directory(normalized, metadata, excluded)
