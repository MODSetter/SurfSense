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
