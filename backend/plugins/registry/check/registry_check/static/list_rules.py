"""What the registry as a whole must say: its shape, and ids that never collide."""

from typing import Any

SCHEMA_VERSION = 1


def shape_problems(registry: Any) -> list[str]:
    if not isinstance(registry, dict):
        return ["the registry must be a JSON object"]
    problems = []
    if registry.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"schema_version: must be {SCHEMA_VERSION}")
    if not isinstance(registry.get("plugins"), list):
        problems.append("plugins: must be a list")
    if not isinstance(registry.get("removed", []), list):
        problems.append("removed: must be a list")
    return problems


def removed_problems(removed: list[Any]) -> list[tuple[int, str]]:
    """Each problem with the index of the removed entry it is about."""
    problems = []
    for index, entry in enumerate(removed):
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            problems.append((index, "id: required"))
        elif not (isinstance(entry.get("reason"), str) and entry["reason"].strip()):
            problems.append((index, "reason: required"))
    return problems


def id_problems(
    plugins: list[Any], removed: list[Any], first_party_ids: set[str]
) -> list[tuple[int, str]]:
    """Each problem with the index of the plugin it is about."""
    removed_ids = {e.get("id") for e in removed if isinstance(e, dict)}
    seen: set[str] = set()
    problems = []
    for index, entry in enumerate(plugins):
        entry_id = entry.get("id") if isinstance(entry, dict) else None
        if not isinstance(entry_id, str):
            continue
        if entry_id in seen:
            problems.append((index, "id: listed twice"))
        elif entry_id in first_party_ids:
            problems.append((index, "id: already used by the first-party list"))
        elif entry_id in removed_ids:
            problems.append((index, "id: removed, and an id is never reused"))
        seen.add(entry_id)
    return problems
