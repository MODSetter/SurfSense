from enum import StrEnum


class ModelType(StrEnum):
    """What a model is for. Classifiers produce it, and a selection is keyed by it.

    The user picks one model per type, so a type is also a slot. A type no
    feature reads yet can still be chosen; the feature that first reads it
    brings the client that calls it.
    """

    TEXT_GEN = "text_gen"
    IMAGE_GEN = "image_gen"
    IMAGE_EDIT = "image_edit"
    VIDEO_GEN = "video_gen"
    AUDIO_GEN = "audio_gen"
