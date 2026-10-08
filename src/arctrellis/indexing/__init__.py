"""In-memory semantic indexing, without persistent storage or target execution."""

from .errors import IndexingError, RepositoryIndexInvariantError
from .models import FileIndexResult, FileIndexStatus, RepositoryIndexResult
from .repository import index_repository

__all__ = [
    "IndexingError",
    "RepositoryIndexInvariantError",
    "FileIndexResult",
    "FileIndexStatus",
    "RepositoryIndexResult",
    "index_repository",
]
