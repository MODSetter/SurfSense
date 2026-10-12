"""Every id the registry holds, delisted ones too: an id is never reused once listed."""

from modules.plugins.lists.registry.current_registry import local_registry


def registry_ids() -> set[str]:
    current = local_registry()
    if current is None:
        return set()
    document = current.document
    return {entry.id for entry in document.entries} | {
        item.id for item in document.removed
    }
