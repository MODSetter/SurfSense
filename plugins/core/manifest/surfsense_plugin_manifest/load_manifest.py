from pathlib import Path

from pydantic import ValidationError

from surfsense_plugin_manifest.errors.from_validation_errors import errors_from
from surfsense_plugin_manifest.errors.manifest_error import ManifestError
from surfsense_plugin_manifest.manifest import Manifest
from surfsense_plugin_manifest.read_manifest_json import read_manifest_json
from surfsense_plugin_manifest.rules.duplicate_names import errors_for_duplicate_names
from surfsense_plugin_manifest.rules.fields_the_release_sets import (
    errors_for_fields_the_release_sets,
)


def load_manifest(path: Path) -> Manifest:
    declared = read_manifest_json(path)
    errors = errors_for_fields_the_release_sets(declared)
    try:
        manifest = Manifest.model_validate(declared)
    except ValidationError as error:
        errors += errors_from(error)
    errors += errors_for_duplicate_names(declared)
    if errors:
        raise ManifestError(errors)
    return manifest
