"""A looser key, used only to match a tested row to how another server spells the model.

Folds what a server adds to the name: quantisation tags, a file extension, the
instruct tag and Ollama's name:tag. Every size and version stays, so 27b never
matches 35b and 3.8 never matches 3.6.
"""

import re

from modules.llm.capability.model_key import model_key

__all__ = ["match_key"]

_EXTENSION = re.compile(r"\.(gguf|ggml|bin|safetensors)$")
_QUANTISATION = re.compile(
    r"i?q\d+(_[a-z0-9]+)*|ud|qat|gguf|ggml|mlx|awq|gptq|exl2"
    r"|f16|f32|bf16|fp\d+|int\d+|\d+bit"
)
_INSTRUCT = frozenset({"instruct", "it", "chat"})
# Ollama writes gemma4 where OpenRouter writes gemma-4.
_LETTER_THEN_DIGIT = re.compile(r"(?<=[a-z])(?=\d)")


def match_key(model_id: str) -> str | None:
    """The key a row is matched by; None for an alias or no id, as `model_key`."""
    if model_key(model_id) is None:
        return None
    # A file path's folders, as llama.cpp and LM Studio name a model, are not the model.
    key = model_key(re.split(r"[\\/]", model_id.strip())[-1])
    if key is None:
        return None
    name = _EXTENSION.sub("", key).replace(":", "-")
    kept = [
        part
        for part in name.split("-")
        if part and part not in _INSTRUCT and not _QUANTISATION.fullmatch(part)
    ]
    return _LETTER_THEN_DIGIT.sub("-", "-".join(kept)) or None
