"""Where the packaged manifest lives, and reading it."""

from pathlib import Path

from modules.llm.catalog.local.manifest.schema import SCHEMA_VERSION, LocalManifest

MANIFEST_PATH = Path(__file__).with_name("models.json")


def load_local_manifest(path: Path | None = None) -> LocalManifest:
    return LocalManifest.model_validate_json((path or MANIFEST_PATH).read_text())


def empty_manifest() -> LocalManifest:
    """What the screen runs on when the packaged file cannot be read: installed
    models and search still work without it."""
    return LocalManifest(schema_version=SCHEMA_VERSION, refreshed_at="", models=[])
