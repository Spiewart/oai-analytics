"""Base class for errors the CLI shows as plain messages (no traceback)."""


class OAIError(Exception):
    """A user-facing error: bad configuration, unknown table, invalid manifest, ..."""
