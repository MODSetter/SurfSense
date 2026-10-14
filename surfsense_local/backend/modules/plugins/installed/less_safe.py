"""Whether a tool's new annotations claim less safety than the ones the user approved."""

from typing import Any

# MCP's defaults for an annotation a server leaves out: the unsafe reading.
DEFAULTS = {"readOnlyHint": False, "destructiveHint": True, "openWorldHint": True}


def became_less_safe(before: dict[str, Any], after: dict[str, Any]) -> bool:
    def hint(annotations: dict[str, Any], name: str) -> bool:
        return annotations.get(name, DEFAULTS[name]) is True

    return (
        (hint(before, "readOnlyHint") and not hint(after, "readOnlyHint"))
        or (not hint(before, "destructiveHint") and hint(after, "destructiveHint"))
        or (not hint(before, "openWorldHint") and hint(after, "openWorldHint"))
    )
