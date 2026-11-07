"""Exception hierarchy for CII.

All CII-specific errors derive from :class:`CiiError` so callers can catch a
single base type at module boundaries. Errors carry a human-readable message;
they never carry secrets or full source content.
"""


class CiiError(Exception):
    """Base class for all CII errors."""


class ConfigurationError(CiiError):
    """Configuration is missing, unreadable, or invalid."""


class ProjectRootError(CiiError):
    """The configured or detected project root is unusable."""


class PathSecurityError(CiiError, ValueError):
    """A path escaped the project root or violated a filesystem policy.

    Also a :class:`ValueError` so Pydantic field validators can raise it and
    get standard ``ValidationError`` handling at model boundaries.
    """


class DatabaseError(CiiError):
    """The database could not be opened or is unusable."""


class MigrationError(CiiError):
    """A schema migration could not be applied."""
