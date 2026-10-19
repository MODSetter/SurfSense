"""What a submitted server says about itself: how it signs in, the hosts that takes, its tools.

Found the way the app finds them, so the submitter never writes `auth`, `hosts` or `tools`
for a server that lists its tools without a key.
"""

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx2

from registry_check.live.oauth_findings import discovered, sign_in_endpoints
from registry_check.live.server_check import server_findings
from registry_check.live.server_contact import (
    Listed,
    NotMcp,
    SignInAsked,
    Unreachable,
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


async def report_server(url: str, client_id: str | None = None) -> ServerReport:
    """`client_id`: one registered with the publisher's sign-in, for a server taking no other."""
    host = urlsplit(url).hostname or ""
    reached = await contact(url)
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
    if report.auth["type"] == "oauth" and client_id:
        report.auth["client_id"] = client_id
    found = await server_findings(
        {"url": url, "auth": report.auth, "hosts": report.hosts, "tools": report.tools}
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
    return ServerReport({"type": "oauth"}, hosts, None)


def _refused(host: str, problem: str) -> ServerReport:
    return ServerReport({"type": "none"}, [host], None, problems=[problem])
