"""A diffusion GGUF's architecture from its tensor names, as sd.cpp reads it:
its converter writes no metadata, and another may write a wrong one.
"""

from collections.abc import Iterable

from modules.llm.gguf.header_prefix import HeaderTensor

_SD1_TEXT_ENCODER = "cond_stage_model.transformer.text_model."
# SDXL's second text encoder, under either converter's name: sd.cpp tells XL
# apart by having two.
_SDXL_SECOND_ENCODER = ("conditioner.embedders.1.", "cond_stage_model.1.")
# A standalone diffusion model's names are bare; sd.cpp adds this when it
# loads one.
_DIFFUSION = "model.diffusion_model."
# The tensor sd.cpp's get_sd_version dispatches each newer family on.
_FAMILY_TENSORS = {
    "double_stream_modulation_img.lin.weight": "flux2",
    "cap_embedder.0.weight": "z_image",
    "layers.0.adaLN_sa_ln.weight": "ernie_image",
    "blocks.0.cross_attn.norm_k.weight": "wan",
}
# LongCat is FLUX-shaped, and sd.cpp tells it from FLUX.1 by its text input's
# width: Qwen2.5-VL-7B's hidden size, where FLUX.1's T5 gives 4096.
_LONGCAT_TEXT_WIDTH = 3584


def diffusion_architecture(tensors: Iterable[HeaderTensor]) -> str | None:
    """The classifier's name for this diffusion model, or None when the tensors
    name none it knows."""
    tensors = list(tensors)
    names = [t.name for t in tensors]
    for name in names:
        family = _FAMILY_TENSORS.get(name.removeprefix(_DIFFUSION))
        if family is not None:
            return family
    bare = {t.name.removeprefix(_DIFFUSION): t for t in tensors}
    text_in = bare.get("txt_in.weight")
    if (
        text_in is not None
        and text_in.dims[:1] == (_LONGCAT_TEXT_WIDTH,)
        and any(n.startswith("double_blocks.") for n in bare)
    ):
        return "longcat"
    if any(n.startswith(_SDXL_SECOND_ENCODER) for n in names):
        return "sdxl"
    if any(n.startswith(_SD1_TEXT_ENCODER) for n in names):
        return "sd1"
    return None
