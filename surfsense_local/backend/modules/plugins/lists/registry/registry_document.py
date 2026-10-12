"""A registry file read into the entries this app offers, the delisted ones, and its date."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError

from modules.plugins.lists.registry.offered_entry import refusal
from modules.plugins.lists.registry.registry_entry import RegistryEntry, RemovedEntry

logger = logging.getLogger(__name__)

# Rises only when the structure breaks; a newer one is ignored, keeping the cached copy.
SCHEMA_VERSION = 1


class UnreadableRegistryError(Exception):
    pass


@dataclass(frozen=True)
class RegistryDocument:
    generated_at: datetime | None
    entries: list[RegistryEntry]
    removed: list[RemovedEntry]

    def entry(self, plugin_id: str) -> RegistryEntry | None:
        return next((e for e in self.entries if e.id == plugin_id), None)


def read_document(body: bytes) -> RegistryDocument:
    """One bad entry is dropped with a log line; it never hides the rest of the list."""
    try:
        raw = json.loads(body)
        if raw.get("schema_version") != SCHEMA_VERSION:
            raise UnreadableRegistryError(
                f"schema_version {raw.get('schema_version')!r} is not {SCHEMA_VERSION}"
            )
        generated_at = _instant(raw.get("generated_at"))
        listed, delisted = raw.get("plugins", []), raw.get("removed", [])
    except (ValueError, AttributeError, TypeError) as error:
        raise UnreadableRegistryError(str(error)) from error

    removed = []
    for item in delisted:
        try:
            removed.append(RemovedEntry.model_validate(item))
        except ValidationError:
            logger.warning("registry: dropped a removed entry that does not parse")
    gone = {item.id for item in removed}

    entries: list[RegistryEntry] = []
    for item in listed:
        name = item.get("id", "?") if isinstance(item, dict) else "?"
        try:
            entry = RegistryEntry.model_validate(item)
        except ValidationError as error:
            logger.warning("registry: dropped %s: %s", name, error)
            continue
        why = refusal(entry) or (
            "listed twice" if any(e.id == entry.id for e in entries) else None
        )
        if why is None and entry.id in gone:
            why = "also removed"
        if why is not None:
            logger.warning("registry: dropped %s: %s", name, why)
            continue
        entries.append(entry)
    return RegistryDocument(generated_at, entries, removed)


def _instant(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
