"""Whether an audio.cpp model fits in what the computer has free, said in the
words of the work it would do."""

import pytest

from modules.llm.providers.audiocpp.memory import (
    NotEnoughMemoryError,
    OtherModel,
    check_memory,
    needed_bytes,
)

pytestmark = pytest.mark.unit

GB = 10**9


def test_a_model_needs_its_measured_peak_and_a_gibibyte_more() -> None:
    """Nemotron's measured peak of 1,776 MiB, and the headroom left for the rest."""
    assert needed_bytes(1776) == 2_936_012_800


def test_enough_free_memory_passes() -> None:
    """Exactly the peak and the headroom is enough."""
    check_memory("Transcribing", 1776, needed_bytes(1776))


def test_a_shortfall_names_the_work_and_both_sizes() -> None:
    """The sentence opens with the work it would do."""
    with pytest.raises(NotEnoughMemoryError) as refused:
        check_memory("Transcribing", 1776, int(1.8 * GB))

    assert str(refused.value) == (
        "Transcribing needs about 2.9 GB free; this computer has 1.8 GB."
    )


def test_a_shortfall_names_the_first_lighter_model_that_fits() -> None:
    """In the manifest's order: a heavier one listed first is passed over."""
    with pytest.raises(NotEnoughMemoryError) as refused:
        check_memory(
            "Voicing",
            2400,
            int(2.5 * GB),
            [OtherModel("Heavy", 3000), OtherModel("Light", 400)],
        )

    assert str(refused.value) == (
        "Voicing needs about 3.6 GB free; this computer has 2.5 GB. "
        "Light needs about 1.5 GB."
    )
