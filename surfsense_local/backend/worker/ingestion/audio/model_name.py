"""The name a transcript's header gives the model that wrote it, as Settings
shows it: the curated entry whose file the server knows the model by."""

from functools import cache
from pathlib import PurePosixPath

from modules.llm.catalog.local.manifest import load_local_manifest

__all__ = ["model_name"]


def model_name(model_id: str) -> str:
    """The id itself for a model no curated entry names."""
    return _names().get(model_id, model_id)


@cache
def _names() -> dict[str, str]:
    return {
        PurePosixPath(file.path).stem: model.name
        for model in load_local_manifest().models
        if model.transcription is not None
        for build in model.builds
        for file in build.files
    }
