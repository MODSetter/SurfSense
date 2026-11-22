"""A plugin signed in with headers: each name and value, encrypted together as one credential."""

import json

from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.remote.sign_in.headers.header_rules import SignInHeader
from shared.secrets import UnreadableSecretError

HEADERS = "headers"


def bearer(token: str) -> list[SignInHeader]:
    """A key typed alone, sent as most keyed servers read one."""
    return [SignInHeader(name="Authorization", value=f"Bearer {token}")]


def write_headers(plugin: InstalledPlugin, headers: list[SignInHeader]) -> None:
    plugin.credential_kind = HEADERS
    plugin.credential = json.dumps(
        [{"name": h.name.strip(), "value": h.value} for h in headers]
    )


def headers_auth(headers: list[SignInHeader]) -> dict:
    """The entry's `auth`: the names alone, kept when disconnecting drops the values."""
    return {"type": HEADERS, "headers": [{"name": h.name.strip()} for h in headers]}


def header_names(plugin: InstalledPlugin) -> list[str]:
    auth = plugin.entry.get("auth") or {}
    return (
        [h["name"] for h in auth.get("headers", [])]
        if auth.get("type") == HEADERS
        else []
    )


def read_headers(plugin: InstalledPlugin) -> dict[str, str]:
    """Empty when signed out, or when this install cannot read what was stored."""
    try:
        stored = plugin.credential
    except UnreadableSecretError:
        return {}
    if stored is None:
        return {}
    return {header["name"]: header["value"] for header in json.loads(stored)}
