from pathlib import Path

from pydantic import ValidationError

from surfsense_plugin_manifest.errors.from_validation_errors import errors_from
from surfsense_plugin_manifest.errors.manifest_error import ManifestError
from surfsense_plugin_manifest.manifest import Manifest
from surfsense_plugin_manifest.read_manifest_json import read_manifest_json


def load_manifest(path: Path) -> Manifest:
    """A manifest that follows every rule, or ManifestError listing each broken one."""
    try:
        return Manifest.model_validate(read_manifest_json(path))
    except ValidationError as error:
        raise ManifestError(errors_from(error)) from None
