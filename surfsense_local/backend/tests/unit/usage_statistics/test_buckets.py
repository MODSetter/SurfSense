"""The report never carries a number, only the contract's buckets, so each edge is pinned."""

import pytest

from modules.usage_statistics.buckets import (
    GIB,
    plugin_calls_bucket,
    ram_bucket,
    sources_bucket,
    studio_outputs_bucket,
    turns_bucket,
    vram_bucket,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("count", "bucket"),
    [(0, "0"), (1, "1-9"), (9, "1-9"), (10, "10-49"), (49, "10-49"), (50, "50+")],
)
def test_turns_fall_in_the_contracts_buckets(count: int, bucket: str) -> None:
    """Zero is its own bucket: a week with no chat is a different week."""
    assert turns_bucket(count) == bucket


@pytest.mark.parametrize(
    ("count", "bucket"),
    [(0, "0"), (9, "1-9"), (10, "10-99"), (999, "100-999"), (1000, "1000+")],
)
def test_a_library_size_falls_in_the_contracts_buckets(count: int, bucket: str) -> None:
    """A library is counted in orders of magnitude, never exactly."""
    assert sources_bucket(count) == bucket


def test_studio_outputs_and_plugin_calls_have_their_own_edges() -> None:
    """Studio splits at 5, plugin calls at 10."""
    assert [studio_outputs_bucket(n) for n in (0, 4, 5)] == ["0", "1-4", "5+"]
    assert [plugin_calls_bucket(n) for n in (0, 9, 10)] == ["0", "1-9", "10+"]


@pytest.mark.parametrize(
    ("gib", "bucket"),
    [
        (5.8, "<8"),
        (7.6, "8-15"),
        (14.6, "16-31"),
        (15.8, "16-31"),
        (31.2, "32-63"),
        (63.0, "64+"),
    ],
)
def test_memory_is_read_as_the_size_it_was_sold_as(gib: float, bucket: str) -> None:
    """A 16 GB laptop reports under 16 GiB once firmware and graphics take theirs."""
    assert ram_bucket(int(gib * GIB)) == bucket


@pytest.mark.parametrize(
    ("gib", "bucket"),
    [(2.0, "<4"), (5.9, "4-7"), (7.6, "8-11"), (11.9, "12-23"), (24.0, "24+")],
)
def test_a_cards_memory_is_read_as_its_label(gib: float, bucket: str) -> None:
    """An 8 GB card reports a little under 8 GiB and still reads as 8."""
    assert vram_bucket(int(gib * GIB)) == bucket
