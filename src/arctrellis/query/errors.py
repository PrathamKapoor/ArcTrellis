"""Caller input failures are distinct from absent static paths and corrupt graphs."""


class QueryError(Exception):
    """Base structural query failure."""


class UnknownQueryEntityError(QueryError):
    """An explicit query ID does not exist."""


class InvalidQuerySourceError(QueryError):
    """The entity kind cannot be used for this query."""


class InvalidQueryLimitError(QueryError):
    """A search budget is not a positive non-boolean integer."""


class QueryGraphInvariantError(QueryError):
    """Stored records do not satisfy a structural query contract."""
