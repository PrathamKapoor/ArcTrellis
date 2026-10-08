"""Repository-level failures; ordinary file failures live in summaries."""


class IndexingError(Exception):
    """Base repository indexing failure."""


class RepositoryIndexInvariantError(IndexingError):
    """Semantic graph identity or ownership was inconsistent."""
