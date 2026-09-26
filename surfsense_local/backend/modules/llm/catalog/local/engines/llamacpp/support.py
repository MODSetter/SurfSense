"""What a local build can do, from GGUF keys under the names llama.cpp writes.

The evidence is llama.cpp's own words, never a label of ours, so a curated
build's committed copy of these keys and a searched build's live header go
through the same functions and cannot disagree. `None` means the evidence is
silent, not that the answer is no.
"""

from typing import Any

from gguf.constants import Keys

_GENERAL_TYPE = Keys.General.TYPE
_ARCHITECTURE = Keys.General.ARCHITECTURE
_HAS_VISION = Keys.Clip.HAS_VISION_ENCODER
_PROJECTION_DIM = Keys.ClipVision.PROJECTION_DIM
_EMBEDDING = Keys.LLM.EMBEDDING_LENGTH

# The GGUF keys a projector file carries into the manifest, so a curated build
# answers from the same keys a searched one reads live.
PROJECTOR_KEYS = (_GENERAL_TYPE, _ARCHITECTURE, _HAS_VISION, _PROJECTION_DIM)


def is_projector(kv: dict[str, Any]) -> bool:
    return (
        kv.get(_GENERAL_TYPE) == "mmproj"
        or str(kv.get(_ARCHITECTURE, "")).lower() == "clip"
    )


def projector_reads_images(kv: dict[str, Any]) -> bool:
    """A projector whose header says it carries a vision encoder."""
    return is_projector(kv) and kv.get(_HAS_VISION) is True


def projector_fits_model(
    projector_kv: dict[str, Any], model_kv: dict[str, Any]
) -> bool:
    """Whether the projector's output is as wide as the model's input.

    The one check a name cannot make: a repo holding two sizes of a family, or a
    projector copied from another model, pairs by name and fails to load. A
    width either side leaves unwritten cannot be held against the pair.
    """
    width = projector_kv.get(_PROJECTION_DIM)
    architecture = model_kv.get(_ARCHITECTURE)
    embedding = (
        model_kv.get(_EMBEDDING.format(arch=architecture)) if architecture else None
    )
    if not isinstance(width, int) or not isinstance(embedding, int):
        return True
    return width == embedding


def template_support(template: str | None) -> tuple[bool | None, bool | None]:
    """Whether the chat template accepts tools, and whether it can think.

    Read from the template text, so the catalog never loads a model to say what
    it supports. The runtime's own `/props` answer stays the word chat trusts.
    """
    if not template:
        return None, None
    tools = "tools" in template
    reasoning = "<think>" in template or "enable_thinking" in template
    return tools, reasoning
