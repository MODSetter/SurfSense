"""Why this app will not offer a registry entry, or None when it will."""

from importlib.metadata import PackageNotFoundError

from modules.plugins.lists.first_party.first_party_list import (
    FIRST_PARTY_LIST,
    checked_entries,
)
from modules.plugins.lists.registry.registry_entry import RegistryEntry
from shared.app_version import app_version

# Only the first-party list speaks for SurfSense, so no fetched file can claim the license key.
_SURFSENSE_ONLY = "claims to be SurfSense's"


def refusal(entry: RegistryEntry) -> str | None:
    if (
        entry.publisher == "surfsense"
        or entry.auth.type == "license"
        or entry.access == "license"
    ):
        return _SURFSENSE_ONLY
    if entry.id in {listed.id for listed in checked_entries(FIRST_PARTY_LIST)}:
        return "takes a first-party id"
    if entry.min_app_version is not None and not _reached(entry.min_app_version):
        return f"needs app {entry.min_app_version}"
    return None


def _reached(minimum: str) -> bool:
    """An unreadable minimum, or an unknown app version, is treated as not reached."""
    try:
        return _parts(app_version()) >= _parts(minimum)
    except (ValueError, PackageNotFoundError):
        return False


def _parts(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))
