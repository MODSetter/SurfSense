"""The tools a server lists, against the entry's `tools` and MCP's safety hints."""

from typing import Any

from registry_check.live.findings import Findings


def tool_findings(entry: dict[str, Any], listed: list[dict[str, Any]]) -> Findings:
    found = Findings()
    names = sorted(tool["name"] for tool in listed)
    declared = entry.get("tools")
    if declared is None:
        found.warnings.append(
            f"tools: not listed; the server lists {', '.join(names) or 'none'}"
        )
    else:
        missing = sorted(set(declared) - set(names))
        extra = sorted(set(names) - set(declared))
        if missing:
            # Some servers list more once signed in; the maintainer confirms those.
            found.warnings.append(
                f"tools: {', '.join(missing)} not listed without sign-in; "
                "a maintainer confirms them when connecting"
            )
        if extra:
            found.problems.append(
                f"tools: the server also lists {', '.join(extra)}; add them"
            )
    # Optional in MCP: without either hint the app asks before every call, which works.
    for tool in listed:
        hints = tool.get("annotations") or {}
        if "readOnlyHint" not in hints and "destructiveHint" not in hints:
            found.warnings.append(
                f"{tool['name']}: no readOnlyHint or destructiveHint, "
                "so the app asks before every call"
            )
    return found
