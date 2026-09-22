"""Turning the manifest into the rows a screen renders."""

import pytest

from modules.llm.catalog import CuratedModel, curated_rows
from modules.llm.fit import FitState, HardwareBudget

pytestmark = pytest.mark.unit

MIB = 1024**2
GB = 1000**3


def model(label: str, blocks: int, variants: list[dict]) -> CuratedModel:
    """A manifest entry, validated the way the app validates it."""
    return CuratedModel.model_validate({
        "model_id": f"Qwen/{label.replace(' ', '-')}",
        "family": "Qwen3",
        "label": label,
        "parameter_count": label.split()[-1],
        "shape": {
            "architecture": "qwen3", "block_count": blocks, "head_count_kv": 8,
            "key_length": 128, "value_length": 128, "context_length": 40960,
            "n_vocab": 151936,
            "embedding_length": 4096, "feed_forward_length": 12288,
        },
        "variants": variants,
    })


def build(file: str, quant: str, gb: float) -> dict:
    """One downloadable build plus the judgement field beside it."""
    return {
        "repo": "unsloth/q", "file": file, "quantization": quant,
        "size_bytes": int(gb * GB),
    }


# List order is the preference signal: smallest first, most preferred last.
CURATED = [
    model("Qwen3 0.6B", 28, [build("0.6b.gguf", "Q4_K_M", 0.40)]),
    model("Qwen3 8B", 36, [build("8b.gguf", "Q4_K_M", 5.03)]),
    model("Qwen3 32B", 64, [build("32b.gguf", "Q4_K_M", 19.76)]),
]
SMALL = HardwareBudget(5234 * MIB, 6002 * MIB, 1024 * MIB, 8000 * MIB, False, True)


def test_every_row_carries_a_badge() -> None:
    """Fit is subtraction, not judgement: every row has a size, so every row can
    be priced. There is no `unknown` state to fall back to."""
    rows = curated_rows(CURATED, SMALL)

    assert len(rows) == len(CURATED)
    assert all(row.badge.verdict for row in rows)


def test_rows_sort_by_fit_coarsely_then_by_manifest_position_finely() -> None:
    """Sorting by manifest position alone puts a TOO_BIG 32B at the top of a
    small machine's screen, which is the one thing that screen must not do."""
    labels = [row.label for row in curated_rows(CURATED, SMALL)]

    assert labels.index("Qwen3 8B") < labels.index("Qwen3 32B")


def test_a_later_entry_in_the_manifest_sorts_first_within_its_fit_tier() -> None:
    """`CURATED` lists 0.6B before 8B. On a machine roomy enough for both to
    reach the same fit tier, 8B, the later and more preferred rung, still
    leads, because manifest position is the only tiebreaker there is."""
    fits_both = HardwareBudget(
        24000 * MIB, 24576 * MIB, 1024 * MIB, 64000 * MIB, False, True
    )
    labels = [row.label for row in curated_rows(CURATED, fits_both)]

    assert labels.index("Qwen3 8B") < labels.index("Qwen3 0.6B")


def test_a_model_with_two_builds_is_one_row() -> None:
    """The screen's job is choosing a model. Listing builds separately shows the
    same model twice."""
    two = [model("Qwen3 8B", 36, [
        build("8b-q8.gguf", "Q8_0", 60.0),
        build("8b-q4.gguf", "Q4_K_M", 5.03),
    ])]

    rows = curated_rows(two, SMALL)

    assert len(rows) == 1
    assert rows[0].variant.quantization == "Q4_K_M"


def test_a_row_takes_the_best_state_among_its_builds() -> None:
    """A model whose large build is refused is still offered on its small one."""
    two = [model("Qwen3 8B", 36, [
        build("8b-q8.gguf", "Q8_0", 60.0),
        build("8b-q4.gguf", "Q4_K_M", 5.03),
    ])]

    assert curated_rows(two, SMALL)[0].fit.state is not FitState.TOO_BIG


def test_only_physics_blocks_installing() -> None:
    """Reduced speed installs exactly like Full speed. It runs, slower."""
    rows = {row.label: row for row in curated_rows(CURATED, SMALL)}

    assert rows["Qwen3 8B"].can_install
    assert not rows["Qwen3 32B"].can_install


def test_no_row_carries_a_quality_score_where_a_renderer_could_read_it() -> None:
    """The manifest's own list order selects the star and orders this list. It
    is never displayed, and the surest way to keep that true is not to send
    it — there is no score field on a row at all to accidentally send."""
    row = curated_rows(CURATED, SMALL)[0]

    assert not hasattr(row, "rank")
    assert not hasattr(row.variant, "rank")
