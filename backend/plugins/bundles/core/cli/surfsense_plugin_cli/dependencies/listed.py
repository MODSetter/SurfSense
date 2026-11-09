"""requirements.in: the libraries a plugin asks for, as the author wrote them."""

import re
from pathlib import Path


def listed(plugin: Path) -> list[str]:
    """Its lines, or none when the plugin has no dependencies."""
    path = plugin / "requirements.in"
    return path.read_text(encoding="utf-8").splitlines() if path.is_file() else []


def library_name(requirement: str) -> str:
    """The name pip compares: tiny_lib, Tiny.Lib and tiny-lib are one library."""
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement)
    return re.sub(r"[-_.]+", "-", match.group(1)).lower() if match else ""
