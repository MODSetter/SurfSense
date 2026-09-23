"""The badge has to describe the load the app will actually perform.

The screen said `Reduced speed` for Qwen3 4B on an 8 GB Mac while `plan_load`
placed it entirely on the GPU, because the row was priced with a full cache and
the loader chose a quantized one. Two modules, two answers, one model.

Parametrised over every budget shape the app can produce rather than the Mac
alone, because the precision rule is pure arithmetic and must not start
depending on which machine it runs on.
"""

import pytest

from modules.llm.catalog.manifest import load_curated_models
from modules.llm.catalog.recommendation import recommend
from modules.llm.catalog.rows import curated_rows
from modules.llm.fit import HardwareBudget, plan_load

pytestmark = pytest.mark.unit

MIB = 1024**2

BUDGETS = {
    # Windows or Linux with a card: two real pools, so spilling is a transfer.
    "discrete-6gb": HardwareBudget(5234 * MIB, 6002 * MIB, 1024 * MIB, 22750 * MIB, False, True),
    "discrete-24gb": HardwareBudget(23000 * MIB, 24576 * MIB, 1024 * MIB, 32000 * MIB, False, True),
    # Apple Silicon: one memory with two ceilings on it.
    "unified-8gb": HardwareBudget(5222 * MIB, 5461 * MIB, 1024 * MIB, 6144 * MIB, True, True),
    "unified-16gb": HardwareBudget(10922 * MIB, 11468 * MIB, 1024 * MIB, 14336 * MIB, True, True),
    # No card ggml can use, on any platform. Nothing to spill from.
    "no-gpu-16gb": HardwareBudget(0, 0, 1024 * MIB, 14 * 1024 * MIB, False, False),
    "no-gpu-4gb": HardwareBudget(0, 0, 1024 * MIB, 3 * 1024 * MIB, False, False),
    # A card the runtime cannot reach: priced against the host, like no GPU.
    "broken-install": HardwareBudget(0, 0, 1024 * MIB, 30 * 1024 * MIB, False, False),
}

CURATED = load_curated_models().models


def _live(budget: HardwareBudget, factor: float) -> HardwareBudget:
    """The same machine with more or less free right now than the shelf assumes."""
    return HardwareBudget(
        device_free_bytes=int(budget.device_free_bytes * factor),
        device_total_bytes=budget.device_total_bytes,
        fit_reserve_bytes=budget.fit_reserve_bytes,
        ram_available_bytes=int(budget.ram_available_bytes * factor),
        uma=budget.uma,
        has_gpu=budget.has_gpu,
    )


# None is the catalog's own call. The other two are what `reprice` passes: a
# busy machine, and an idle one with more free than the shelf was priced for.
LIVE_FACTORS = (None, 0.4, 1.6)


@pytest.mark.parametrize("budget_name", BUDGETS)
@pytest.mark.parametrize("factor", LIVE_FACTORS)
def test_every_row_is_badged_as_it_will_be_loaded(budget_name, factor) -> None:
    """The invariant that was broken, on every machine shape.

    A row whose badge and load plan disagree is a promise the app does not keep,
    in whichever direction: pessimistic sells a model short, optimistic tells
    someone a model will be fast when it will not.

    Swept over what is free at load as well as over the machine, because
    `reprice` passes both budgets and the widening search reads the live one.
    An idle machine is the case that caught a second mismatch: widening against
    a more generous `live` and reporting against capacity said PARTIAL for a row
    the catalog had badged FITS.
    """
    budget = BUDGETS[budget_name]
    live = None if factor is None else _live(budget, factor)

    shapes = {model.model_id: model.model_shape for model in CURATED}

    for row in curated_rows(CURATED, budget):
        plan = plan_load(shapes[row.model_id], row.variant.size_bytes, budget, live=live)

        assert row.fit.state is plan.verdict.state, (
            f"{row.label} badges {row.fit.state.value} and loads "
            f"{plan.verdict.state.value} at {plan.precision.value}"
        )


@pytest.mark.parametrize("budget_name", BUDGETS)
def test_the_star_is_badged_as_it_will_be_loaded(budget_name) -> None:
    """The one row a user is steered to, so the one that must not mislead."""
    budget = BUDGETS[budget_name]
    pick = recommend(CURATED, budget)
    if pick is None:
        return

    plan = plan_load(pick.entry.model_shape, pick.variant.size_bytes, budget)

    assert pick.verdict.state is plan.verdict.state


def test_a_model_resident_only_with_a_quantized_cache_reads_full_speed() -> None:
    """The measured case. Qwen3 4B on an 8 GB Mac needs 4857 MiB with a full
    cache against 4198 resident, and 3777 with a quantized one, so it is placed
    entirely on the GPU and the badge has to say so."""
    budget = BUDGETS["unified-8gb"]
    rows = {row.label: row for row in curated_rows(CURATED, budget)}

    assert rows["Qwen3 4B"].badge.verdict == "Full speed"


def test_a_machine_with_no_gpu_is_never_told_about_a_graphics_card() -> None:
    """Whatever the precision rule decides, there is no device to be too big for."""
    for name in ("no-gpu-16gb", "no-gpu-4gb", "broken-install"):
        for row in curated_rows(CURATED, BUDGETS[name]):
            assert "graphics card" not in row.badge.reason
            assert row.badge.verdict in {"Works here", "Won't fit"}


@pytest.mark.parametrize("budget_name", BUDGETS)
def test_a_recommended_row_never_carries_spill_wording(budget_name) -> None:
    """The invariant the badge and the star share now: a starred build's own
    badge can never be the wording that tells someone to expect it to be slow.

    Swept over every curated model and every budget shape rather than one
    fixture, because this has to hold for whichever build ends up starred on
    whichever machine, not just the one screenshot that found the gap.
    """
    budget = BUDGETS[budget_name]
    rows = {row.model_id: row for row in curated_rows(CURATED, budget)}
    pick = recommend(CURATED, budget)
    if pick is None:
        return

    starred = rows[pick.entry.model_id]

    assert starred.badge.verdict in {"Full speed", "Works here"}
