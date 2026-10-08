"""Failures that distinguish invalid roots from incomplete discovery."""


class IngestionError(Exception):
    """Base exception for repository discovery."""


class InvalidRepositoryPathError(IngestionError):
    """The supplied root is missing, indirect or not an ordinary directory."""


class RepositoryAccessError(IngestionError):
    """Filesystem inspection failed; no complete inventory is available."""
