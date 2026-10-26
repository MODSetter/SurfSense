"""A registry written to a temporary folder, valid unless a test spoils it."""

import json
from pathlib import Path
from typing import Any

SQUARE_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    b'<rect width="64" height="64" fill="#2563eb"/></svg>'
)


def valid_entry(**overrides: Any) -> dict[str, Any]:
    entry = {
        "id": "acme",
        "kind": "remote",
        "verification": "community",
        "name": "Acme",
        "description": "Search Acme.",
        "author": "Jane Doe",
        "url": "https://mcp.acme.example/mcp",
        "auth": {"type": "none"},
        "hosts": ["mcp.acme.example"],
        "access": "free",
        "privacy_policy": "https://acme.example/privacy",
        "tools": ["search"],
    }
    entry.update(overrides)
    return entry


def write_registry(
    root: Path,
    plugins: list[dict[str, Any]],
    removed: list[dict[str, Any]] | None = None,
    icons: dict[str, bytes] | None = None,
    first_party: list[dict[str, Any]] | None = None,
) -> tuple[Path, Path]:
    """Return the registry file and the first-party list beside it."""
    (root / "icons").mkdir(parents=True, exist_ok=True)
    for name, content in (icons or {}).items():
        (root / "icons" / name).write_bytes(content)
    registry = root / "plugins.json"
    registry.write_text(
        json.dumps({"schema_version": 1, "plugins": plugins, "removed": removed or []})
    )
    first_party_file = root / "first_party.json"
    first_party_file.write_text(
        json.dumps({"schema_version": 1, "plugins": first_party or []})
    )
    return registry, first_party_file
