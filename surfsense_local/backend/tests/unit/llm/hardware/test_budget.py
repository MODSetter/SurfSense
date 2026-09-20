"""Turning a device listing into the numbers the estimator subtracts."""

import pytest

from modules.llm.hardware import BudgetMode, Device, DeviceType, build_budget

pytestmark = pytest.mark.unit

MIB = 1024**2

DISCRETE = Device("Vulkan0", "RTX 3050", DeviceType.GPU, 6002 * MIB, 5234 * MIB)
INTEGRATED = Device("Vulkan1", "Radeon", DeviceType.IGPU, 16198 * MIB, 16198 * MIB)
CPU_LIVE = Device("CPU", "Ryzen 5", DeviceType.CPU, 31884 * MIB, 22750 * MIB)
CPU_RESTATED = Device("CPU", "Apple M2", DeviceType.CPU, 8192 * MIB, 8192 * MIB)
METAL = Device("MTL0", "Apple M2", DeviceType.GPU, 5461 * MIB, 5461 * MIB)


def test_the_reserve_is_llama_cpps_own_margin_not_an_estimate_of_it() -> None:
    """fit_params_target defaults to one GiB per device, so usable is exact."""
    budget = build_budget([DISCRETE, INTEGRATED, CPU_LIVE], ram_available_bytes=22750 * MIB)

    assert budget.fit_reserve_bytes == 1024 * MIB
    assert budget.usable_vram_bytes == (5234 - 1024) * MIB


def test_the_budget_never_exceeds_the_one_device_it_chose() -> None:
    """The integrated part advertises three times the memory and holds no layers."""
    budget = build_budget([DISCRETE, INTEGRATED, CPU_LIVE], ram_available_bytes=22750 * MIB)

    assert budget.device_total_bytes == 6002 * MIB


def test_unified_memory_is_flagged_so_the_copy_can_branch() -> None:
    """On Apple Silicon there is no separate pool to spill into, so the badge says
    CPU rather than system RAM, which would describe a transfer that never happens."""
    assert build_budget([METAL, CPU_RESTATED], ram_available_bytes=2000 * MIB).uma


def test_a_machine_with_no_gpu_still_produces_a_budget() -> None:
    """It badges as running on the processor. PARTIAL is unreachable, not an error."""
    budget = build_budget([CPU_LIVE], ram_available_bytes=22750 * MIB)

    assert not budget.has_gpu
    assert budget.usable_vram_bytes == 0


def test_the_ram_half_comes_from_the_caller_not_from_ggml() -> None:
    """ggml's CPU device restates the total on macOS and under WSL2, and that
    number is what separates PARTIAL from TOO_BIG."""
    budget = build_budget([METAL, CPU_RESTATED], ram_available_bytes=1500 * MIB)

    assert budget.ram_available_bytes == 1500 * MIB


def test_catalog_pricing_uses_capacity_not_whatever_is_free_right_now() -> None:
    """Two modes, and using the wrong one makes the catalog lie.

    Pricing against live free memory means the badges move with whatever else the
    machine happens to be doing: an 8 GB Mac with a browser open reports a couple
    of GB free and every large row reads TOO_BIG, though the model would run once
    the memory is reclaimed. Capacity is the honest basis for a shelf of models
    you might install later.
    """
    busy = build_budget(
        [METAL, CPU_RESTATED], ram_available_bytes=2000 * MIB, mode=BudgetMode.CAPACITY
    )
    idle = build_budget(
        [METAL, CPU_RESTATED], ram_available_bytes=7000 * MIB, mode=BudgetMode.CAPACITY
    )

    assert busy.ram_available_bytes == idle.ram_available_bytes


def test_launch_decisions_use_what_is_actually_free() -> None:
    """The opposite case: a model is about to be loaded now, into memory that
    exists now, so the live reading is the one that governs."""
    budget = build_budget(
        [METAL, CPU_RESTATED], ram_available_bytes=2000 * MIB, mode=BudgetMode.LIVE
    )

    assert budget.ram_available_bytes == 2000 * MIB


def test_capacity_never_reports_less_memory_than_is_free_right_now() -> None:
    """Found in dev: with no CPU device to state physical RAM, capacity fell back
    to the live reading and then subtracted the host reserve from it anyway.

    On a busy 8 GB machine that is 1.9 GB minus 2 GB, which floors at zero and
    badges every model `Won't fit ... This PC has 0 GB`. A fallback is a floor,
    not another thing to deduct from.
    """
    live = 1_900_000_000

    budget = build_budget([], ram_available_bytes=live, mode=BudgetMode.CAPACITY)

    assert budget.ram_available_bytes >= live


def test_capacity_still_holds_a_reserve_back_when_it_knows_the_total() -> None:
    """The reserve is what the host keeps once a model is resident, and it is
    only meaningful against physical RAM."""
    budget = build_budget(
        [METAL, CPU_RESTATED], ram_available_bytes=1_900_000_000,
        mode=BudgetMode.CAPACITY,
    )

    assert budget.ram_available_bytes == 8192 * MIB - 2 * 1024**3


def test_unified_memory_is_bounded_by_what_is_actually_free() -> None:
    """Metal reports `recommendedMaxWorkingSetSize` as both total and free, a
    static figure that never moves however busy the machine is.

    Spending it as though it were live is what sized a 28,672 token window on a
    Mac with 2.3 GB reclaimable: 4,355 MiB of weights and cache came out of the
    same 8 GB the OS was using, the load paged, and it took 43 seconds.
    """
    budget = build_budget(
        [METAL, CPU_RESTATED],
        ram_available_bytes=2300 * MIB,
        mode=BudgetMode.LIVE,
    )

    assert budget.device_free_bytes <= 2300 * MIB


def test_unified_memory_still_respects_the_graphics_working_set() -> None:
    """Both limits apply. Metal refuses allocations past the working set however
    much system memory is free, so the smaller of the two governs."""
    budget = build_budget(
        [METAL, CPU_RESTATED],
        ram_available_bytes=7000 * MIB,
        mode=BudgetMode.LIVE,
    )

    assert budget.device_free_bytes <= METAL.free_bytes


def test_a_unified_catalog_prices_against_capacity_not_this_moment() -> None:
    """Rows must not move because a browser is open, so the shelf is priced
    against what the machine could give a model, minus what the host keeps."""
    busy = build_budget(
        [METAL, CPU_RESTATED], ram_available_bytes=1000 * MIB,
        mode=BudgetMode.CAPACITY,
    )
    idle = build_budget(
        [METAL, CPU_RESTATED], ram_available_bytes=7000 * MIB,
        mode=BudgetMode.CAPACITY,
    )

    assert busy.device_free_bytes == idle.device_free_bytes


def test_a_discrete_card_is_untouched_by_the_mode() -> None:
    """Dedicated VRAM is a separate pool and its `free` really is live, so
    nothing about host memory should narrow it."""
    live = build_budget([DISCRETE, CPU_LIVE], 22750 * MIB, mode=BudgetMode.LIVE)
    capacity = build_budget([DISCRETE, CPU_LIVE], 22750 * MIB, mode=BudgetMode.CAPACITY)

    assert live.device_free_bytes == DISCRETE.free_bytes
    assert capacity.device_free_bytes == DISCRETE.free_bytes
