"""Reading manifest.json as a JSON object, or saying plainly why it cannot be read."""

import json
from pathlib import Path

from surfsense_plugin_manifest.errors.manifest_error import ManifestError


def read_manifest_json(path: Path) -> dict:
    """The file as a JSON object, or one error saying why it is not one."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ManifestError([f"{path.name}: does not exist"]) from None
    try:
        declared = json.loads(text)
    except json.JSONDecodeError as error:
        raise ManifestError(
            [
                f"{path.name}: is not valid JSON, line {error.lineno} column {error.colno}"
            ]
        ) from None
    if not isinstance(declared, dict):
        raise ManifestError([f"{path.name}: must be a JSON object"])
    return declared
