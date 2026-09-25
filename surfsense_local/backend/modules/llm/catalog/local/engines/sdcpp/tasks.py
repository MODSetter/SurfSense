"""The slots an sd.cpp model fills: a video model the video slot, an image model
the ones its entry's tasks name."""

from modules.llm.catalog.local.manifest import CuratedModel
from modules.llm.model_type import ModelType

_IMAGE_TYPES = {"generate": ModelType.IMAGE_GEN, "edit": ModelType.IMAGE_EDIT}


def model_types(model: CuratedModel) -> tuple[ModelType, ...]:
    if model.video is not None:
        return (ModelType.VIDEO_GEN,)
    tasks = model.image.tasks if model.image is not None else ["generate"]
    return tuple(_IMAGE_TYPES[task] for task in dict.fromkeys(tasks))
