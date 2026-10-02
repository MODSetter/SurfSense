from enum import StrEnum


class ModelType(StrEnum):
    """What a model is for. Classifiers produce it, and a selection is keyed by it.

    The user picks one model per type, so a type is also a slot. A type no
    feature reads yet can still be chosen; the feature that first reads it
    brings the client that calls it.

    EMBEDDING is the exception: a catalog type, so the manifest and an engine can
    describe it, never a slot. The embedder belongs to the index, which onboarding
    fixes once; a selection would offer the swap that breaks search.
    """

    TEXT_GEN = "text_gen"
    IMAGE_GEN = "image_gen"
    IMAGE_EDIT = "image_edit"
    VIDEO_GEN = "video_gen"
    AUDIO_GEN = "audio_gen"
    EMBEDDING = "embedding"
