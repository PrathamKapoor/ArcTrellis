"""Retrieval failures distinguish caller input from an invalid stored snapshot."""


class RetrievalError(Exception):
    """Base structural retrieval failure."""


class InvalidSearchIndexError(RetrievalError):
    """The supplied graph or index cannot be projected into a search snapshot."""


class RetrievalInvariantError(RetrievalError):
    """Stored records do not satisfy the retrieval snapshot contract."""
