from surfsense_plugin_manifest import load_manifest

from modules.plugins.bundles.models import PluginRun
from shared.config import get_storage_settings


def declared_timeout(run: PluginRun) -> int:
    """How long the run's action may take, as its installed manifest.json says."""
    folder = get_storage_settings().plugin_dir(run.plugin_id, run.version)
    manifest = load_manifest(folder / "manifest.json")
    return next(
        action.timeout_seconds
        for action in manifest.actions
        if action.name == run.action
    )
