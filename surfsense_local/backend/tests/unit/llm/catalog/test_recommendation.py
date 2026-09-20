"""Which curated build gets the star.

The regression this file exists for: on a 6 GB card a residency-only rule stars
a 1.7B while the owner is happily running an 8B. Residency is a mechanism and
speed is the goal, and on small cards they disagree.
"""

import pytest

from modules.llm.catalog import CuratedModel, recommend
from modules.llm.fit import HardwareBudget

pytestmark = pytest.mark.unit

MIB = 1024**2
GB = 1000**3


def qwen(block_count: int) -> dict:
    """Every shipped Qwen3 has 8 KV heads and 128 wide keys; only depth differs."""
    return {
        "architecture": "qwen3",
        "block_count": block_count,
        "head_count_kv": 8,
        "key_length": 128,
        "value_length": 128,
        "context_length": 40960,
        "n_vocab": 151936,
    }


def build(repo: str, file: str, quant: str, size: int, rank: int) -> dict:
    """One downloadable build plus the judgement fields beside it."""
    return {
        "repo": repo,
        "file": file,
        "quantization": quant,
        "size_bytes": size,
        "rank": rank,
        "rank_basis": "llmfit-1.1.11",
    }


def model(model_id: str, label: str, blocks: int, variants: list[dict]) -> CuratedModel:
    """A manifest entry, validated the way the app validates it."""
    return CuratedModel.model_validate(
        {
            "model_id": model_id,
            "family": "Qwen3",
            "label": label,
            "parameter_count": label.split()[-1],
            "shape": qwen(blocks),
            "variants": variants,
        }
    )


CURATED = [
    model("Qwen/Qwen3-0.6B", "Qwen3 0.6B", 28, [build("u/q", "0.6b.gguf", "Q4_K_M", int(0.40 * GB), 33)]),
    model("Qwen/Qwen3-1.7B", "Qwen3 1.7B", 28, [build("u/q", "1.7b.gguf", "Q4_K_M", int(1.11 * GB), 48)]),
    model("Qwen/Qwen3-4B", "Qwen3 4B", 36, [build("u/q", "4b.gguf", "Q4_K_M", int(2.50 * GB), 63)]),
    model("Qwen/Qwen3-8B", "Qwen3 8B", 36, [build("u/q", "8b.gguf", "Q4_K_M", int(5.03 * GB), 78)]),
    model("Qwen/Qwen3-32B", "Qwen3 32B", 64, [build("u/q", "32b.gguf", "Q4_K_M", int(19.76 * GB), 92)]),
]

# The measured machine: RTX 3050, 5234 MiB free, llama.cpp's own 1024 MiB margin.
RTX_3050 = HardwareBudget(5234 * MIB, 6002 * MIB, 1024 * MIB, 22750 * MIB, False, True)


def test_a_spilling_model_can_be_recommended_over_a_resident_one() -> None:
    """The measured contradiction. A FITS-only rule fails this, which is the point.

    On this card the 8B spills about a fifth and runs without noticeable lag,
    while a residency-only rule stars the 1.7B.
    """
    pick = recommend(CURATED, RTX_3050)

    assert pick is not None
    assert pick.entry.label == "Qwen3 8B"


def test_physics_still_refuses_whatever_the_rank() -> None:
    """The ceiling relaxes residency, never physics."""
    tiny = HardwareBudget(2000 * MIB, 2000 * MIB, 1024 * MIB, 3000 * MIB, False, True)

    pick = recommend(CURATED, tiny)

    assert pick is not None
    assert pick.entry.label in {"Qwen3 0.6B", "Qwen3 1.7B"}


def test_a_roomy_machine_takes_the_best_ranked_build() -> None:
    """Where residency and speed agree, rank decides."""
    workstation = HardwareBudget(
        24000 * MIB, 24576 * MIB, 1024 * MIB, 64000 * MIB, False, True
    )

    assert recommend(CURATED, workstation).entry.label == "Qwen3 32B"


def test_nothing_is_recommended_when_nothing_can_run() -> None:
    """No star is honest. Every non-refused build stays installable regardless."""
    postage_stamp = HardwareBudget(64 * MIB, 64 * MIB, 1024 * MIB, 64 * MIB, False, True)

    assert recommend(CURATED, postage_stamp) is None


def test_the_policy_ranges_over_builds_so_a_smaller_one_can_rescue_an_entry() -> None:
    """A model whose big build is refused is still recommendable on its small one."""
    two_builds = [
        model("Qwen/Qwen3-8B", "Qwen3 8B", 36, [
            build("u/q", "8b-q8.gguf", "Q8_0", int(60.0 * GB), 83),
            build("u/q", "8b-q4.gguf", "Q4_K_M", int(5.03 * GB), 78),
        ])
    ]

    pick = recommend(two_builds, RTX_3050)

    assert pick is not None
    assert pick.variant.quantization == "Q4_K_M"
