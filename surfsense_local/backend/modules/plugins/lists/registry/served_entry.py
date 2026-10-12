"""An entry as this build reaches it: a developer's local plugin host stands in for SurfSense's."""

from urllib.parse import urlsplit

from modules.plugins.lists.plugin_host import as_served
from modules.plugins.lists.registry.registry_entry import RegistryEntry


def served_entry(entry: RegistryEntry) -> RegistryEntry:
    return entry.model_copy(
        update={
            "url": as_served(entry.url),
            "hosts": [
                urlsplit(as_served(f"https://{host}")).hostname or ""
                for host in entry.hosts
            ],
        }
    )
