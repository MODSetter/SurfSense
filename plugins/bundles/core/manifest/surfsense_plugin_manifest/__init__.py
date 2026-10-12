"""The rules a plugin's manifest.json must follow, shared by the app and the checks."""

from surfsense_plugin_manifest.errors.manifest_error import ManifestError
from surfsense_plugin_manifest.load_manifest import load_manifest
from surfsense_plugin_manifest.manifest import Action, Input, Manifest, Secret

__all__ = ["Action", "Input", "Manifest", "ManifestError", "Secret", "load_manifest"]
