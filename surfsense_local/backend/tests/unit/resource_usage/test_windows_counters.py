"""Turning Windows' GPU performance counters into one reading per card.

Instance names and values are the test machine's, read through PDH while
llama-server held a model: an RTX 3080 beside Microsoft's software renderer.
PDH writes the LUID's hex in upper case, and DXGI's LUID is two integers.
"""

import pytest

from modules.resource_usage.gpu.windows.adapters import Adapter
from modules.resource_usage.gpu.windows.counters import readings

pytestmark = pytest.mark.unit

MIB = 1024**2
RTX = "0x00000000_0x00015a31"
SOFTWARE = "0x00000000_0x00018132"

ADAPTERS = [
    Adapter(luid=RTX, name="NVIDIA GeForce RTX 3080", dedicated_bytes=10_541_334_528),
    Adapter(luid=SOFTWARE, name="Microsoft Basic Render Driver", dedicated_bytes=0),
]
ADAPTER_MEMORY = {
    "luid_0x00000000_0x00015A31_phys_0": 7_912_718_336,
    "luid_0x00000000_0x00018132_phys_0": 0,
}
PROCESS_MEMORY = {
    "pid_5972_luid_0x00000000_0x00015A31_phys_0": 5_926_080_512,
    "pid_1788_luid_0x00000000_0x00015A31_phys_0": 2_471_825_408,
    "pid_47092_luid_0x00000000_0x00015A31_phys_0": 90 * MIB,
}
ENGINE_BUSY = {
    "pid_5972_luid_0x00000000_0x00015A31_phys_0_eng_1_engtype_Compute_0": 45.0,
    "pid_5972_luid_0x00000000_0x00015A31_phys_0_eng_0_engtype_3D": 30.0,
    "pid_1788_luid_0x00000000_0x00015A31_phys_0_eng_0_engtype_3D": 20.0,
    "pid_12016_luid_0x00000000_0x00015A31_phys_0_eng_5_engtype_Copy": 0.0,
}


def test_a_card_reads_its_memory_in_use_and_each_process_share() -> None:
    """Upper-case LUIDs from PDH match DXGI's lower-case ones."""
    (card,) = readings(ADAPTERS, ADAPTER_MEMORY, PROCESS_MEMORY, ENGINE_BUSY)

    assert card.name == "NVIDIA GeForce RTX 3080"
    assert card.total_bytes == 10_541_334_528
    assert card.used_bytes == 7_912_718_336
    assert card.process_bytes == {
        5972: 5_926_080_512,
        1788: 2_471_825_408,
        47092: 90 * MIB,
    }


def test_busy_is_the_busiest_engine_as_task_manager_reads_it() -> None:
    """Each engine sums every process on it; the card is its busiest engine.
    Averaging would read a card saturated on Compute as a quarter busy."""
    (card,) = readings(ADAPTERS, ADAPTER_MEMORY, PROCESS_MEMORY, ENGINE_BUSY)

    assert card.busy_percent == 50.0
    assert card.process_busy == {5972: 45.0, 1788: 20.0, 12016: 0.0}


def test_busy_is_unknown_until_two_samples_give_a_rate() -> None:
    """The first sample has nothing to pair with. Zero would read as an idle
    card while a model is generating on it."""
    (card,) = readings(ADAPTERS, ADAPTER_MEMORY, PROCESS_MEMORY, {})

    assert card.busy_percent is None
    assert card.process_busy is None


def test_the_software_renderer_is_not_a_card() -> None:
    """It holds no memory of its own and is on every Windows machine."""
    cards = readings(ADAPTERS, ADAPTER_MEMORY, PROCESS_MEMORY, ENGINE_BUSY)

    assert [c.name for c in cards] == ["NVIDIA GeForce RTX 3080"]


def test_an_integrated_part_with_a_token_carve_out_is_not_listed() -> None:
    """Intel's 128 MB is a reservation, not graphics memory worth a meter."""
    igpu = Adapter(
        luid="0x00000000_0x0000abcd",
        name="Intel(R) UHD Graphics",
        dedicated_bytes=128 * MIB,
    )

    assert readings([igpu], {}, {}, {}) == []


def test_linked_adapters_add_up_across_their_physical_parts() -> None:
    """A linked adapter lists one instance per physical part."""
    both = {
        "luid_0x00000000_0x00015a31_phys_0": 3 * MIB,
        "luid_0x00000000_0x00015a31_phys_1": 4 * MIB,
    }

    (card,) = readings(ADAPTERS[:1], both, {}, {})

    assert card.used_bytes == 7 * MIB


def test_an_instance_name_it_cannot_parse_is_skipped() -> None:
    """An unexpected instance, such as a total, is skipped rather than raising."""
    (card,) = readings(
        ADAPTERS[:1], {"_Total": 1, **ADAPTER_MEMORY}, {"garbage": 5}, {}
    )

    assert card.used_bytes == 7_912_718_336
    assert card.process_bytes == {}
