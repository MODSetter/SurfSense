"""A diffusion GGUF's architecture from its tensor names, as sd.cpp reads it: its
converter writes no metadata. Only SD 1 and SDXL, the tables read so far.
"""

from collections.abc import Iterable

from modules.llm.gguf.header_prefix import HeaderTensor

_SD1_TEXT_ENCODER = "cond_stage_model.transformer.text_model."
# SDXL's second text encoder, under either converter's name: sd.cpp tells XL
# apart by having two.
_SDXL_SECOND_ENCODER = ("conditioner.embedders.1.", "cond_stage_model.1.")


def diffusion_architecture(tensors: Iterable[HeaderTensor]) -> str | None:
    """The classifier's name for this diffusion model, or None when the tensors
    name none it knows."""
    names = [t.name for t in tensors]
    if any(n.startswith(_SDXL_SECOND_ENCODER) for n in names):
        return "sdxl"
    if any(n.startswith(_SD1_TEXT_ENCODER) for n in names):
        return "sd1"
    return None
