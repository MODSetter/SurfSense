"""Everything the live check finds about one entry's server, by how it signs in."""

from typing import Any

from registry_check.live.findings import Findings
from registry_check.live.oauth_findings import oauth_findings
from registry_check.live.server_contact import (
    Listed,
    NotMcp,
    SignInAsked,
    Unreachable,
    contact,
)
from registry_check.live.tool_findings import tool_findings


async def server_findings(entry: dict[str, Any]) -> Findings:
    found = Findings()
    auth = (entry.get("auth") or {}).get("type")
    reached = await contact(entry["url"])
    match reached:
        case Unreachable(reason):
            found.problems.append(f"url: could not be reached: {reason}")
        case NotMcp(_, status) if auth in ("token", "headers") and _is_client_error(
            status
        ):
            # Some servers refuse a missing key with 400 or 404 rather than 401.
            found.warnings.append(
                f"url: answered {status} without a key; checked when a maintainer "
                "connects it with one"
            )
        case NotMcp(reason):
            found.problems.append(
                f"url: does not answer MCP over Streamable HTTP: {reason}"
            )
        case SignInAsked(status) if auth == "none":
            found.problems.append(
                f"auth: none, but the server asks for sign-in ({status})"
            )
        case Listed(tools):
            if auth in ("token", "headers", "oauth"):
                found.warnings.append(
                    f"auth: {auth}, but the server listed its tools without a key"
                )
            found.add(tool_findings(entry, tools))
    # A signed-in server's tools are checked by the maintainer, who connects it.
    if auth == "oauth" and isinstance(reached, SignInAsked | Listed):
        found.add(await oauth_findings(entry))
    return found


def _is_client_error(status: int | None) -> bool:
    return status is not None and 400 <= status < 500
