"""Bounded source reads with current-path checks, not an atomic sandbox."""

import os
import stat
from pathlib import Path, PureWindowsPath

from arctrellis.ingestion import DiscoveredFile

from .errors import SourceReadError, SourceTooLargeError, UnsafeSourceError

DEFAULT_MAX_SOURCE_BYTES = 2 * 1024 * 1024


def _validate_limit(limit: int) -> None:
    if type(limit) is not int:
        raise TypeError("max_source_bytes must be an integer, not a boolean")
    if limit < 1:
        raise ValueError("max_source_bytes must be >= 1")


def _check_size(size: int, limit: int) -> None:
    if size > limit:
        raise SourceTooLargeError(f"source size {size} bytes exceeds limit {limit} bytes")


def _ordinary(metadata: os.stat_result, path: Path, directory: bool) -> None:
    indirect = (
        stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )
    correct_kind = stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode)
    if indirect or not correct_kind:
        raise UnsafeSourceError(f"source path must use ordinary directories and a regular file: {path}")


def _identity(metadata: os.stat_result) -> tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


def _read_source(root: str | os.PathLike[str], item: DiscoveredFile, limit: int) -> bytes:
    raw = os.fspath(root)
    if not isinstance(raw, str):
        raise TypeError("repository_root must be a string path")
    if not raw or "\x00" in raw:
        raise UnsafeSourceError("repository_root must be a nonempty directory path")
    boundary = Path(os.path.abspath(raw))
    components = item.path.split("/")
    if any(PureWindowsPath(component).drive for component in components):
        raise UnsafeSourceError("source path components must not contain Windows drives")
    target = boundary.joinpath(*components)
    try:
        target.relative_to(boundary)
    except ValueError as error:
        raise UnsafeSourceError("source path must remain inside repository_root") from error
    try:
        directories = []
        for path in reversed(target.parents):
            info = os.lstat(path)
            _ordinary(info, path, True)
            directories.append((path, info))
        before = os.lstat(target)
        _ordinary(before, target, False)
        _check_size(before.st_size, limit)
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(target, flags)
        try:
            opened = os.fstat(descriptor)
            _ordinary(opened, target, False)
            if _identity(opened) != _identity(before):
                raise SourceReadError(f"source identity changed before reading: {target}")
            _check_size(opened.st_size, limit)
            chunks = []
            remaining = limit + 1
            while remaining:
                chunk = os.read(descriptor, min(remaining, 64 * 1024))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            source = b"".join(chunks)
            _check_size(len(source), limit)
            after = os.fstat(descriptor)
            if (after.st_size, after.st_mtime_ns) != (opened.st_size, opened.st_mtime_ns) or len(
                source
            ) != after.st_size:
                raise SourceReadError(f"source changed while reading: {target}")
        finally:
            os.close(descriptor)
        current = os.lstat(target)
        _ordinary(current, target, False)
        if (_identity(current), current.st_size, current.st_mtime_ns) != (
            _identity(after),
            after.st_size,
            after.st_mtime_ns,
        ):
            raise SourceReadError(f"source changed after reading: {target}")
        for path, previous in directories:
            current = os.lstat(path)
            _ordinary(current, path, True)
            if _identity(current) != _identity(previous):
                raise SourceReadError(f"source ancestor changed while reading: {path}")
        return source
    except OSError as error:
        raise SourceReadError(f"cannot read source {target}: {error}") from error
