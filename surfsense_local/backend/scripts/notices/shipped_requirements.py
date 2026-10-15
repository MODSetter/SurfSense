"""Which distributions the frozen binaries can carry: `uv export --no-dev`, read for this platform.

The release job's `uv sync` also installs PyInstaller, pytest and ruff, so the
installed set alone would overstate what ships.
"""

import re

from packaging.markers import Marker

# `name==1.0`, `name @ url`, each optionally followed by `; marker`.
_REQUIREMENT = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:==|@)[^;]*(?:;(.*))?$")


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def shipped_names(export: str, environment: dict[str, str] | None = None) -> list[str]:
    """Names from an export whose markers hold here. `-e` lines are our own code."""
    names: set[str] = set()
    for line in export.splitlines():
        match = _REQUIREMENT.match(line.strip())
        if not match:
            continue
        name, marker = match.groups()
        if marker and not Marker(marker.strip()).evaluate(environment):
            continue
        names.add(normalized(name))
    return sorted(names)
