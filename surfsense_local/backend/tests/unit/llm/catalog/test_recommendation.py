"""Which curated build gets the star.

The regression this file exists for: on a 6 GB card a residency-only rule stars
a 1.7B while the owner is happily running an 8B. Residency is a mechanism and
speed is the goal, and on small cards they disagree.
"""

import pytest

from modules.llm.catalog.manifest import CuratedModel
from modules.llm.catalog.recommendation import recommend
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
        "embedding_length": 4096,
        "feed_forward_length": 12288,
    }


def build(repo: str, file: str, quant: str, size: int) -> dict:
    """One downloadable build."""
    return {
        "repo": repo,
        "file": file,
        "quantization": quant,
        "size_bytes": size,
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


# List order is the preference signal: smallest first, most preferred last.
CURATED = [
    model("Qwen/Qwen3-0.6B", "Qwen3 0.6B", 28, [build("u/q", "0.6b.gguf", "Q4_K_M", int(0.40 * GB))]),
    model("Qwen/Qwen3-1.7B", "Qwen3 1.7B", 28, [build("u/q", "1.7b.gguf", "Q4_K_M", int(1.11 * GB))]),
    model("Qwen/Qwen3-4B", "Qwen3 4B", 36, [build("u/q", "4b.gguf", "Q4_K_M", int(2.50 * GB))]),
    model("Qwen/Qwen3-8B", "Qwen3 8B", 36, [build("u/q", "8b.gguf", "Q4_K_M", int(5.03 * GB))]),
    model("Qwen/Qwen3-32B", "Qwen3 32B", 64, [build("u/q", "32b.gguf", "Q4_K_M", int(19.76 * GB))]),
]

# The measured machine: RTX 3050, 5234 MiB free, llama.cpp's own 1024 MiB margin.
RTX_3050 = HardwareBudget(5234 * MIB, 6002 * MIB, 1024 * MIB, 22750 * MIB, False, True)


def test_a_spilling_model_can_be_recommended_over_a_resident_one() -> None:
    """A FITS-only rule fails this, which is the point.

    A small discrete card, mostly free: the 4B spills a fifth of a layer or so
    (0.22) rather than fitting whole, and still outranks the fully resident
    1.7B and 0.6B, since it sits later in the manifest. A residency-only rule
    would star the 1.7B instead, which is not conservative, it is wrong: the 4B
    demonstrably runs.
    """
    small_discrete = HardwareBudget(4000 * MIB, 4300 * MIB, 1024 * MIB, 16000 * MIB, False, True)

    pick = recommend(CURATED, small_discrete)

    assert pick is not None
    assert pick.entry.label == "Qwen3 4B"


def test_physics_still_refuses_whatever_the_manifest_prefers() -> None:
    """The ceiling relaxes residency, never physics."""
    tiny = HardwareBudget(2200 * MIB, 2200 * MIB, 1024 * MIB, 3200 * MIB, False, True)

    pick = recommend(CURATED, tiny)

    assert pick is not None
    assert pick.entry.label in {"Qwen3 0.6B", "Qwen3 1.7B"}


def test_a_roomy_machine_takes_the_most_preferred_build() -> None:
    """Where residency and speed agree, manifest position decides."""
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
            build("u/q", "8b-q8.gguf", "Q8_0", int(60.0 * GB)),
            build("u/q", "8b-q4.gguf", "Q4_K_M", int(5.03 * GB)),
        ])
    ]
    # A roomier discrete card than RTX_3050: the Q4 build spills lightly
    # (0.19) here rather than the third RTX_3050 would cost it, which is
    # enough to demonstrate the point without also needing full residency.
    roomier_discrete = HardwareBudget(6000 * MIB, 6800 * MIB, 1024 * MIB, 22750 * MIB, False, True)

    pick = recommend(two_builds, roomier_discrete)

    assert pick is not None
    assert pick.variant.quantization == "Q4_K_M"


def test_a_machine_with_no_gpu_still_gets_a_recommendation() -> None:
    """The measured bug: nothing was ever starred on a CPU only machine.

    Every row came back as a full spill, which the speed gate then refused, so
    the one screen whose job is to choose a model chose nothing on the hardware
    that most needs the help.
    """
    no_gpu = HardwareBudget(0, 0, 1024 * MIB, 14 * 1024 * MIB, False, False)

    pick = recommend(CURATED, no_gpu)

    assert pick is not None
    assert pick.entry.label == "Qwen3 8B"


def test_a_machine_with_no_gpu_is_still_refused_what_it_cannot_hold() -> None:
    """The star moves down the ladder rather than off it.

    1500 MiB holds the 0.6B, which needs 1013 with a quantized cache, and not
    the 1.7B, which needs 1690 even with one.
    """
    tiny = HardwareBudget(0, 0, 1024 * MIB, 1500 * MIB, False, False)

    pick = recommend(CURATED, tiny)

    assert pick is not None
    assert pick.entry.label == "Qwen3 0.6B"


def test_a_quantized_cache_is_allowed_to_rescue_a_larger_model() -> None:
    """The star has to name the model the loader will actually run.

    2600 MiB does not hold the 1.7B with a full cache, at 2953 MiB, and does
    hold it with a quantized one, at 2113. `plan_load` already chose the
    quantized cache here, so pricing the star against the full one pointed at
    the 0.6B while the app was perfectly able to run the rung above it. That
    mattered most on the machines with the least to choose from.
    """
    small = HardwareBudget(0, 0, 1024 * MIB, 2600 * MIB, False, False)

    pick = recommend(CURATED, small)

    assert pick is not None
    assert pick.entry.label == "Qwen3 1.7B"
