"""What one registry entry must say, per docs/architecture/plugin-registry.md.

Each problem is `field: message`; unknown fields are allowed so newer apps can add them.
"""

import ipaddress
import re
from typing import Any
from urllib.parse import urlsplit

ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
HOSTNAME_PATTERN = re.compile(
    r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$"
)
SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$"
)
DISPLAY_LENGTHS = {"name": 80, "description": 200, "author": 80}
# license is the first-party list's alone: a fetched file never receives the key.
# `verified`: a maintainer's judgement that the author runs the server, set in review.
VERIFICATIONS = {"verified", "community"}
REGISTRY_ACCESS = {"free", "external"}
TOKEN_LABEL_LENGTHS = {"title": 80, "description": 200}
# MCP's own rule for a tool name.
TOOL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
ABOUT_LENGTH = 600
# The month the plugin joined the list.
ADDED_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
# An HTTP token (RFC 9110), as the app checks the headers a user gives.
HEADER_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]{1,64}$")
# The transport sets these; an entry naming one would replace them.
REFUSED_HEADERS = {
    "host",
    "content-length",
    "content-type",
    "accept",
    "connection",
    "transfer-encoding",
    "cookie",
    "mcp-session-id",
    "mcp-protocol-version",
    "last-event-id",
}
HEADER_WORDING_LENGTHS = {"label": 80, "description": 200}


def entry_problems(entry: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    problems += _identity_problems(entry)
    problems += _display_problems(entry)
    problems += _url_problems(entry)
    problems += _auth_problems(entry.get("auth"))
    problems += _host_problems(entry)
    problems += _access_problems(entry)
    problems += _page_problems(entry)
    problems += _listing_problems(entry)
    if entry.get("transport", "streamable_http") != "streamable_http":
        # MCP deprecated SSE, and neither of SurfSense's engines speaks it.
        problems.append(
            "transport: SurfSense speaks Streamable HTTP only; give the server's "
            "Streamable HTTP address and remove this field"
        )
    version = entry.get("min_app_version")
    if version is not None and not (
        isinstance(version, str) and SEMVER_PATTERN.match(version)
    ):
        problems.append("min_app_version: must be a version like 2.3.0")
    return problems


def _identity_problems(entry: dict[str, Any]) -> list[str]:
    problems = []
    entry_id = entry.get("id")
    if not (isinstance(entry_id, str) and ID_PATTERN.match(entry_id)):
        problems.append(f"id: must match {ID_PATTERN.pattern}")
    if entry.get("kind") != "remote":
        problems.append("kind: must be remote")
    if entry.get("verification") not in VERIFICATIONS:
        problems.append("verification: must be verified or community")
    return problems


def _display_problems(entry: dict[str, Any]) -> list[str]:
    return [
        f"{field}: must be 1 to {longest} characters"
        for field, longest in DISPLAY_LENGTHS.items()
        if not _is_text(entry.get(field), longest)
    ]


def _url_problems(entry: dict[str, Any]) -> list[str]:
    url = entry.get("url")
    if not isinstance(url, str):
        return ["url: required"]
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        return ["url: must be https"]
    if parts.username is not None or parts.password is not None:
        return ["url: must hold no credentials"]
    return []


def _auth_problems(auth: Any) -> list[str]:
    if not isinstance(auth, dict):
        return ["auth: must be an object with a type"]
    if any("secret" in str(key).lower() for key in auth):
        return ["auth: must never carry a client secret"]
    kind = auth.get("type")
    if kind == "none":
        return []
    if kind == "token":
        # Optional: without them the app asks in its own translated words.
        given = {
            f: n for f, n in TOKEN_LABEL_LENGTHS.items() if auth.get(f) is not None
        }
        if all(_is_text(auth[f], n) for f, n in given.items()):
            return []
        return ["auth: a token's title is 1-80 characters, its description 1-200"]
    if kind == "headers":
        return _headers_problems(auth.get("headers"))
    if kind == "oauth":
        return _oauth_problems(auth)
    return ["auth: type must be none, token, headers or oauth"]


def _headers_problems(headers: Any) -> list[str]:
    """Where the user's key goes, worded for them; an entry never holds a value."""
    if not (isinstance(headers, list) and headers):
        return ["auth: headers must name at least one header"]
    seen: set[str] = set()
    for header in headers:
        name = header.get("name") if isinstance(header, dict) else None
        if not (isinstance(name, str) and HEADER_NAME.match(name)):
            return [f"auth: {name!r} is not a header name"]
        if name.lower() in REFUSED_HEADERS:
            return [f"auth: {name} is set by the app itself"]
        if name.lower() in seen:
            return [f"auth: {name} is named twice"]
        seen.add(name.lower())
        prefix = header.get("prefix")
        if prefix is not None and not (
            isinstance(prefix, str)
            and len(prefix) <= 32
            and not set(prefix) & set("\r\n\0")
        ):
            return [f"auth: {name}'s prefix must be up to 32 characters, one line"]
        for field, longest in HEADER_WORDING_LENGTHS.items():
            value = header.get(field)
            if value is not None and not _is_text(value, longest):
                return [f"auth: {name}'s {field} must be 1 to {longest} characters"]
    return []


def _oauth_problems(auth: dict[str, Any]) -> list[str]:
    if not isinstance(auth.get("user_client", False), bool):
        return ["auth: user_client must be true or false"]
    client_id = auth.get("client_id")
    if client_id is not None and not _is_text(client_id, 255):
        return ["auth: client_id must be a string"]
    scopes = auth.get("scopes")
    if scopes is not None and not (
        isinstance(scopes, list) and all(_is_text(s, 255) for s in scopes)
    ):
        return ["auth: scopes must be a list of strings"]
    return []


def _host_problems(entry: dict[str, Any]) -> list[str]:
    hosts = entry.get("hosts")
    if not (isinstance(hosts, list) and hosts):
        return ["hosts: must list every host the app contacts"]
    for host in hosts:
        if not (isinstance(host, str) and HOSTNAME_PATTERN.match(host)):
            return [f"hosts: {host!r} is not an exact lowercase hostname"]
        if _is_loopback(host):
            return [f"hosts: {host} is loopback"]
    if len(set(hosts)) != len(hosts):
        return ["hosts: lists a host twice"]
    url = entry.get("url")
    url_host = urlsplit(url).hostname if isinstance(url, str) else None
    if url_host and url_host not in hosts:
        return [f"hosts: must include the url's host, {url_host}"]
    return []


def _access_problems(entry: dict[str, Any]) -> list[str]:
    access = entry.get("access")
    if access not in REGISTRY_ACCESS:
        return ["access: must be free or external"]
    if access == "external" and not _is_text(entry.get("access_note"), 200):
        return ["access_note: required when access is external (1-200 characters)"]
    return []


def _page_problems(entry: dict[str, Any]) -> list[str]:
    problems = []
    if entry.get("privacy_policy") is None:
        problems.append("privacy_policy: required")
    for field in ("privacy_policy", "homepage"):
        page = entry.get(field)
        if page is not None and not _is_https_page(page):
            problems.append(f"{field}: must be an https URL")
    return problems


def _listing_problems(entry: dict[str, Any]) -> list[str]:
    """`about`, `tools` and `added`, what the plugin's public page shows."""
    problems = []
    about = entry.get("about")
    if about is not None and not _is_text(about, ABOUT_LENGTH):
        problems.append(f"about: must be 1 to {ABOUT_LENGTH} characters")
    tools = entry.get("tools")
    # The plugin's page lists them before anyone connects.
    if tools is None:
        problems.append("tools: required")
    else:
        problems += _tool_list_problems(tools)
    added = entry.get("added")
    if added is not None and not (
        isinstance(added, str) and ADDED_PATTERN.match(added)
    ):
        problems.append("added: must be a month like 2026-10")
    return problems


def _tool_list_problems(tools: Any) -> list[str]:
    if not isinstance(tools, list):
        return ["tools: must be a list of tool names"]
    for tool in tools:
        if not (isinstance(tool, str) and TOOL_NAME_PATTERN.match(tool)):
            return [f"tools: {tool!r} is not an MCP tool name"]
    if len(set(tools)) != len(tools):
        return ["tools: lists a tool twice"]
    return []


def _is_text(value: Any, longest: int) -> bool:
    return isinstance(value, str) and 1 <= len(value.strip()) <= len(value) <= longest


def _is_https_page(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parts = urlsplit(value)
    return parts.scheme == "https" and bool(parts.hostname)


def _is_loopback(host: str) -> bool:
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
