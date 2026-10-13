"""Plugins the registry delisted, and why: read from the copy held, never fetched."""

from modules.plugins.installed.models import InstalledPlugin, PluginSource
from modules.plugins.lists.registry.current_registry import local_registry


def delisted_reasons() -> dict[str, str]:
    current = local_registry()
    if current is None:
        return {}
    return {item.id: item.reason for item in current.document.removed}


def delisted_reason(plugin: InstalledPlugin, reasons: dict[str, str]) -> str | None:
    """Only a plugin connected from the registry: a custom one may share the id."""
    if plugin.source != PluginSource.REGISTRY:
        return None
    return reasons.get(plugin.id)
