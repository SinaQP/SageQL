"""SageQL errors."""


class GenerationError(Exception):
    """A provider could not produce a usable SQL candidate."""


class InvalidSQL(GenerationError):
    """A candidate is not a single read-only SQLite query."""
