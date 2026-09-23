from enum import StrEnum


class Source(StrEnum):
    """Where a model comes from: the catalog's source filter.

    Local is what SurfSense downloads and runs itself; remote is anything
    reached through a connection, a local server such as Ollama included.
    """

    LOCAL = "local"
    REMOTE = "remote"
