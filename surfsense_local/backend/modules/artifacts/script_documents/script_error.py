"""How a failed version says its script was at fault, so the agent rewrites the script only then.

A failure outside the script (a busy database, the embedder, a closed app) fails
the same version; the script that was right is rendered again as it is.
"""

PREFIX = "Script error: "


def script_error(reason: str) -> str:
    """The stored reason of a run the script failed."""
    return f"{PREFIX}{reason}"


def is_script_error(reason: str | None) -> bool:
    """Whether a failed version's reason came from its script."""
    return (reason or "").startswith(PREFIX)
