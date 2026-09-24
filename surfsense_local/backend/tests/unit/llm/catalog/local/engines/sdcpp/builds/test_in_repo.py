"""Which files in a diffusion repo make an sd.cpp build."""

import pytest

from modules.llm.catalog.local.build import FileRole
from modules.llm.catalog.local.engines.sdcpp.builds.in_repo import builds_in
from modules.llm.catalog.local.listed_file import ListedFile

pytestmark = pytest.mark.unit

REV = "101ff06c98bea9ac8affe6a2c867e9762958d219"

# kostakoff/stable-diffusion-v1-5-GGUF at REV, read on 23 Sep 2026.
SD15_LISTING = (
    ListedFile(".gitattributes", 1604),
    ListedFile("README.md", 3982),
    ListedFile("out.png", 476475, "cb929af09334" + "0" * 52),
    ListedFile("v1-5-pruned_Q4_0.gguf", 3051366272, "24bcd54c" + "0" * 56),
    ListedFile("v1-5-pruned_Q4_K.gguf", 3174685280, "79c3026a" + "0" * 56),
    ListedFile("v1-5-pruned_Q8_0.gguf", 3227903840, "148a2697" + "0" * 56),
    ListedFile("v1-5-pruned_bf16.gguf", 2213675712, "bea21312" + "0" * 56),
)


def test_each_gguf_is_one_self_contained_build() -> None:
    """sd.cpp runs one file holding the UNet, VAE and text encoder, so a build is
    that file alone, pinned to the commit it was listed at."""
    builds = builds_in(
        SD15_LISTING, repo="kostakoff/stable-diffusion-v1-5-GGUF", revision=REV
    )

    assert [b.quantization for b in builds] == ["BF16", "Q4_0", "Q4_K", "Q8_0"]
    q4 = builds[1]
    (weights,) = q4.files
    assert weights.role is FileRole.WEIGHTS
    assert weights.path == "v1-5-pruned_Q4_0.gguf"
    assert weights.size_bytes == 3051366272
    assert weights.revision == REV
