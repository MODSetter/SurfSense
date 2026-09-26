"""What a remote model is for, read off the modalities its manifest entry declares.

Text input is required for every type, because each slot hands the model a
typed prompt and transcription entries ignore one. An image on the way in as
well as out means the model edits on top of generating.
"""

from modules.llm.catalog.remote.manifest.schema import RemoteModel
from modules.llm.catalog.remote.not_text_gen import can_answer_in_prose
from modules.llm.model_type import ModelType

__all__ = ["classify"]


def classify(model_id: str, model: RemoteModel) -> frozenset[ModelType]:
    """Every type this model is for. Empty means it fills no slot."""
    inputs = set(model.modalities.input)
    outputs = set(model.modalities.output)
    if "text" not in inputs:
        return frozenset()

    types: set[ModelType] = set()
    # The GPT image models declare text output too, so modalities alone would
    # make them chat models. A model you can converse with always reports a
    # context window.
    if "text" in outputs and model.context and can_answer_in_prose(model_id):
        types.add(ModelType.TEXT_GEN)
    if "image" in outputs:
        types.add(ModelType.IMAGE_GEN)
        if "image" in inputs:
            types.add(ModelType.IMAGE_EDIT)
    if "video" in outputs:
        types.add(ModelType.VIDEO_GEN)
    if "audio" in outputs:
        types.add(ModelType.AUDIO_GEN)
    return frozenset(types)
