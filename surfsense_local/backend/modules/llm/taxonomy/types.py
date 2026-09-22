from enum import StrEnum


class ModelType(StrEnum):
    """What a model is for. The value names its catalogue tab.

    A model can be several of these at once, so callers hold a set.
    """

    TEXT_GEN = "text_gen"
    IMAGE_GEN = "image_gen"
    IMAGE_EDIT = "image_edit"
    VIDEO_GEN = "video_gen"
    AUDIO_GEN = "audio_gen"
