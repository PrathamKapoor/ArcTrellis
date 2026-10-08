"""Public errors for graph identity conflicts and unknown references."""


class GraphError(Exception):
    """Base class for graph consistency and lookup errors."""


class DuplicateEntityError(GraphError):
    """An entity ID is already associated with a different record."""


class DuplicateRelationshipError(GraphError):
    """A relationship ID is already associated with a different record."""


class UnknownEntityError(GraphError):
    """An entity ID does not exist in the graph."""


class UnknownRelationshipError(GraphError):
    """A relationship ID does not exist in the graph."""
