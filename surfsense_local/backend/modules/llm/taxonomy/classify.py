"""What a models.dev entry is for, read off the modalities it declares.

Text input is required for every type, because each tab hands the model a
typed prompt and transcription entries ignore one. An image on the way in as
well as out means the model edits on top of generating.
"""

from collections.abc import Mapping
from typing import Any

from modules.llm.taxonomy.not_text_gen import can_answer_in_prose
from modules.llm.taxonomy.supports import supports
from modules.llm.taxonomy.types import ModelType

__all__ = ["classify"]


def classify(model_id: str, entry: Mapping[str, Any]) -> frozenset[ModelType]:
    """Every type this model is for. Empty means offer it nowhere."""
    modalities = entry.get("modalities") or {}
    inputs = set(modalities.get("input") or ())
    outputs = set(modalities.get("output") or ())
    if "text" not in inputs:
        return frozenset()

    # The GPT image models declare text output too, so modalities alone put
    # them in the chat tab. A model you can converse with always reports a
    # context window.
    window = supports(entry).context_window

    types: set[ModelType] = set()
    if "text" in outputs and window and can_answer_in_prose(model_id):
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
