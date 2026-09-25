"""A diffusion GGUF's architecture, from the tensor names sd.cpp dispatches on."""

import pytest

from modules.llm.catalog.local.classifier import classify
from modules.llm.catalog.local.engines.sdcpp.evidence import diffusion_architecture
from modules.llm.gguf import read_header_prefix
from modules.llm.model_type import ModelType
from tests.unit.llm.gguf.build import gguf, tensor

pytestmark = pytest.mark.unit

# From kostakoff/stable-diffusion-v1-5-GGUF's v1-5-pruned_Q4_0.gguf, read on
# 23 Sep 2026. The file carries no metadata at all.
SD1_TENSORS = [
    "cond_stage_model.transformer.text_model.embeddings.token_embedding.weight",
    "first_stage_model.decoder.conv_in.weight",
    "model.diffusion_model.input_blocks.0.0.weight",
    "model.diffusion_model.time_embed.0.weight",
]

# From kostakoff/stable-diffusion-xl-base-1.0-GGUF's sd_xl_base_1.0_0_Q4_0.gguf,
# read on 23 Sep 2026: two text encoders, and a label embedding SD 1 lacks.
SDXL_TENSORS = [
    "conditioner.embedders.0.transformer.text_model.embeddings.token_embedding.weight",
    "conditioner.embedders.1.model.token_embedding.weight",
    "first_stage_model.decoder.conv_in.weight",
    "model.diffusion_model.input_blocks.0.0.weight",
    "model.diffusion_model.label_emb.0.0.weight",
]


def _tensors(names: list[str]):
    return read_header_prefix(gguf([], [tensor(n, [4]) for n in names])).tensors


def test_stable_diffusion_1_is_named_by_its_text_encoder() -> None:
    """The architecture the classifier calls an image model."""
    architecture = diffusion_architecture(_tensors(SD1_TENSORS))

    assert architecture == "sd1"
    assert classify(architecture).types == (ModelType.IMAGE_GEN,)


def test_stable_diffusion_xl_is_named_by_its_second_text_encoder() -> None:
    """XL is told from 1 by having two text encoders, as sd.cpp tells it."""
    architecture = diffusion_architecture(_tensors(SDXL_TENSORS))

    assert architecture == "sdxl"
    assert classify(architecture).types == (ModelType.IMAGE_GEN,)


# From gpustack/stable-diffusion-xl-1.0-turbo-GGUF's Q4_0 at 632cbcdd, read on
# 23 Sep 2026: the same two encoders under the older converter's names.
SDXL_TURBO_TENSORS = [
    "cond_stage_model.transformer.text_model.embeddings.token_embedding.weight",
    "cond_stage_model.1.transformer.text_model.embeddings.token_embedding.weight",
    "model.diffusion_model.label_emb.0.0.weight",
]


def test_xl_is_named_whichever_converter_named_its_second_encoder() -> None:
    """A first run of the refresh typed SDXL Turbo as SD 1: its converter calls
    the second encoder `cond_stage_model.1`, which sd.cpp also checks."""
    assert diffusion_architecture(_tensors(SDXL_TURBO_TENSORS)) == "sdxl"


def test_tensors_it_does_not_know_name_nothing() -> None:
    """MiniMax-H3's bare video GGUFs must not pass for an image model."""
    assert diffusion_architecture(_tensors(["blocks.0.attn.weight"])) is None


# The first tensors of each file, and the one sd.cpp dispatches the family on,
# read on 25 Sep 2026. leejet's converter writes no metadata; unsloth's ERNIE
# file declares general.architecture "wan", which is not what it is.
FLUX2_KLEIN_TENSORS = [
    "double_blocks.0.img_attn.norm.query_norm.scale",
    "double_stream_modulation_img.lin.weight",
    "single_blocks.0.linear1.weight",
]
Z_IMAGE_TENSORS = [
    "context_refiner.0.attention.k_norm.weight",
    "cap_pad_token",
    "cap_embedder.0.weight",
]
ERNIE_IMAGE_TENSORS = [
    "adaLN_modulation.1.bias",
    "layers.0.adaLN_mlp_ln.weight",
    "layers.0.adaLN_sa_ln.weight",
]


@pytest.mark.parametrize(
    ("names", "family"),
    [
        (FLUX2_KLEIN_TENSORS, "flux2"),
        (Z_IMAGE_TENSORS, "z_image"),
        (ERNIE_IMAGE_TENSORS, "ernie_image"),
    ],
)
def test_the_newer_families_are_named_by_the_tensor_sd_cpp_reads(
    names: list[str], family: str
) -> None:
    """A standalone diffusion model's names are bare; sd.cpp prefixes them with
    model.diffusion_model. when it loads one, and either form is the family."""
    prefixed = [f"model.diffusion_model.{n}" for n in names]

    assert diffusion_architecture(_tensors(names)) == family
    assert diffusion_architecture(_tensors(prefixed)) == family
    assert classify(family).types == (ModelType.IMAGE_GEN,)


# The first tensors of both curated Wan files, read on 25 Sep 2026; sd.cpp tells
# Wan by the cross attention's key norm.
WAN_TENSORS = [
    "blocks.0.cross_attn.k.bias",
    "blocks.0.cross_attn.k.weight",
    "blocks.0.cross_attn.norm_k.weight",
]


def test_wan_is_named_by_its_cross_attention_and_makes_video() -> None:
    """Wan2.1 and Wan2.2 alike; the classifier calls it a video model."""
    assert diffusion_architecture(_tensors(WAN_TENSORS)) == "wan"
    assert classify("wan").types == (ModelType.VIDEO_GEN,)
