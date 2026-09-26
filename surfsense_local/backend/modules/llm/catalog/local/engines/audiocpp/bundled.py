"""The audio model the app ships, in its models pack beside the embedding model:
read-only, so never deleted, and replaced by the next update."""

from pathlib import Path

from shared.config import get_storage_settings

BUNDLED_DIR_NAME = "audio"


def bundled_audio_dir() -> Path:
    return get_storage_settings().models_dir / BUNDLED_DIR_NAME
