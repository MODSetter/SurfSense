"""Every offline rule over the registry, as lines naming the entry and the field."""

import json
from pathlib import Path
from typing import Any

from registry_check.static.entry_rules import entry_problems
from registry_check.static.icon_rules import icon_problems
from registry_check.static.list_rules import (
    id_problems,
    removed_problems,
    shape_problems,
)


def problems_in(registry_path: Path, first_party_path: Path) -> list[str]:
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"{registry_path.name}: unreadable: {error}"]
    problems = shape_problems(registry)
    if problems:
        return problems
    plugins: list[Any] = registry["plugins"]
    removed: list[Any] = registry.get("removed", [])
    first_party = json.loads(first_party_path.read_text(encoding="utf-8"))
    first_party_ids = {e["id"] for e in first_party["plugins"]}

    for index, entry in enumerate(plugins):
        if not isinstance(entry, dict):
            problems.append(f"plugins[{index}]: must be an object")
            continue
        problems += [f"{_label(plugins, index)}: {p}" for p in entry_problems(entry)]
    problems += [
        f"{_label(plugins, index)}: {p}"
        for index, p in id_problems(plugins, removed, first_party_ids)
    ]
    problems += [
        f"{_label(removed, index, 'removed')}: {p}"
        for index, p in removed_problems(removed)
    ]
    problems += icon_problems(plugins, registry_path.parent / "icons")
    return problems


def _label(entries: list[Any], index: int, section: str = "plugins") -> str:
    entry = entries[index]
    entry_id = entry.get("id") if isinstance(entry, dict) else None
    if isinstance(entry_id, str):
        return f'{section}[{index}] "{entry_id}"'
    return f"{section}[{index}]"
