"""Contacts each entry a pull request adds or changes; an unchanged one was checked before."""

import json
import logging
from pathlib import Path
from typing import Any

import anyio

from registry_check.live.findings import Findings
from registry_check.live.server_check import server_findings


def live_findings(registry_path: Path, base_path: Path | None) -> Findings:
    # The SDK logs a bad answer whole; this check reports reasons of its own instead.
    logging.getLogger("mcp").setLevel(logging.CRITICAL + 1)
    plugins = _plugins(registry_path)
    before = {
        entry.get("id"): entry for entry in (_plugins(base_path) if base_path else [])
    }
    found = Findings()
    for index, entry in enumerate(plugins):
        if before.get(entry.get("id")) == entry:
            continue
        label = f'plugins[{index}] "{entry.get("id")}"'
        one = anyio.run(server_findings, entry)
        found.problems += [f"{label}: {p}" for p in one.problems]
        found.warnings += [f"{label}: warning: {w}" for w in one.warnings]
    return found


def _plugins(path: Path) -> list[dict[str, Any]]:
    plugins = json.loads(path.read_text()).get("plugins")
    if not isinstance(plugins, list):
        return []
    return [entry for entry in plugins if isinstance(entry, dict) and "url" in entry]
