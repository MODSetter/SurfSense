"""Ids SurfSense keeps for its own plugins, which a contributed plugin cannot take."""

from surfsense_plugin_cli.repository import CORE

RESERVED_PREFIX = "surfsense-"


def is_reserved(plugin_id: str) -> bool:
    """Listed in plugins/core/policy/reserved-plugin-ids.txt, or named surfsense-*."""
    listed = (CORE / "policy" / "reserved-plugin-ids.txt").read_text(encoding="utf-8")
    return plugin_id in listed.split() or plugin_id.startswith(RESERVED_PREFIX)
