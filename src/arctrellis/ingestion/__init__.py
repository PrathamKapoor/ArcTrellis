"""Public filesystem discovery API; independent of parsing and graph storage."""

from .discovery import DEFAULT_EXCLUDED_DIRECTORIES, scan_repository
from .errors import IngestionError, InvalidRepositoryPathError, RepositoryAccessError
from .models import DiscoveredFile, Language, RepositoryInventory, SkippedPath, SkipReason

__all__ = [
    "DEFAULT_EXCLUDED_DIRECTORIES",
    "DiscoveredFile",
    "IngestionError",
    "InvalidRepositoryPathError",
    "Language",
    "RepositoryAccessError",
    "RepositoryInventory",
    "SkippedPath",
    "SkipReason",
    "scan_repository",
]
