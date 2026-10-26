"""What a submitted server says about itself: how it signs in, the hosts that takes, its tools.

Found the way the app finds them, so the submitter never writes `auth`, `hosts` or `tools`
for a server that lists its tools without a key.
"""

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx2
from mcp.client.auth.utils import should_use_client_metadata_url

from registry_check.live.oauth_findings import (
    SURFSENSE_CLIENT,
    discovered,
    sign_in_endpoints,
)
from registry_check.live.server_check import server_findings
from registry_check.live.server_contact import (
    Listed,
    NotMcp,
    SignInAsked,
    Unreachable,
    answers_sse,
    contact,
)


@dataclass
class ServerReport:
    auth: dict[str, Any]
    hosts: list[str]
    # None when the server asks for sign-in before listing them.
    tools: list[str] | None
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# What a server without Streamable HTTP answers its POST, as the app reads it.
NOT_STREAMABLE = {400, 404, 405}


async def report_server(url: str) -> ServerReport:
    host = urlsplit(url).hostname or ""
    if _is_sse_address(url):
        return await _sse_address(url, host)
    reached = await contact(url)
    if (
        isinstance(reached, NotMcp)
        and reached.status in NOT_STREAMABLE
        and await answers_sse(url)
    ):
        return _refused(
            host,
            "answers only the older HTTP+SSE transport, which SurfSense does not "
            "speak. Give its Streamable HTTP address, which often ends in /mcp",
        )
    match reached:
        case Unreachable(reason):
            return _refused(host, f"could not be reached: {reason}")
        case NotMcp(reason, status):
            # A server wanting a key answers 401; another code is most often a wrong path.
            hint = ". Check it is your MCP endpoint" if status else ""
            return _refused(
                host, f"does not answer MCP over Streamable HTTP: {reason}{hint}"
            )
        case Listed(tools):
            report = ServerReport(
                {"type": "none"}, [host], sorted(t["name"] for t in tools)
            )
        case SignInAsked():
            report = await _signing_in(url, host)
    found = await server_findings(
        {
            "url": url,
            "auth": report.auth,
            "hosts": report.hosts,
            "tools": report.tools,
        }
    )
    report.problems += found.problems
    report.warnings += found.warnings
    return report


async def _signing_in(url: str, host: str) -> ServerReport:
    """OAuth when the server names an authorization server, a key otherwise."""
    try:
        issuer, metadata = await discovered(url)
    except httpx2.HTTPError:
        metadata = None
    if metadata is None:
        return ServerReport({"type": "token"}, [host], None)
    hosts = [host]
    for endpoint in sign_in_endpoints(url, issuer, metadata):
        reached = urlsplit(endpoint).hostname
        if reached and reached not in hosts:
            hosts.append(reached)
    auth: dict[str, Any] = {"type": "oauth"}
    if not (
        metadata.registration_endpoint
        or should_use_client_metadata_url(metadata, SURFSENSE_CLIENT)
    ):
        # Neither way for SurfSense to register: each user brings their own app.
        auth["user_client"] = True
    return ServerReport(auth, hosts, None)


def _is_sse_address(url: str) -> bool:
    """As providers' docs still give theirs; the app refuses the same rule."""
    return urlsplit(url).path.rstrip("/").lower().endswith("/sse")


async def _sse_address(url: str, host: str) -> ServerReport:
    """Named as SSE whatever it answers, since a 401 there would read as a key to take;
    the `/mcp` beside it is named when MCP answers there, signed in or not."""
    parts = urlsplit(url)
    path = parts.path.rstrip("/")[: -len("/sse")] + "/mcp"
    beside = urlunsplit(parts._replace(path=path))
    problem = "is an address on the older HTTP+SSE transport, which SurfSense does not speak. "
    if isinstance(await contact(beside), Listed | SignInAsked):
        return _refused(
            host, f"{problem}Its server answers MCP at {beside}: submit that address"
        )
    return _refused(
        host, f"{problem}Give its Streamable HTTP address, which often ends in /mcp"
    )


def _refused(host: str, problem: str) -> ServerReport:
    return ServerReport({"type": "none"}, [host], None, problems=[problem])
