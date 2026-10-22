"""Counts and sizes turned into the report's buckets, never sent as numbers.

The edges are the contract's (docs/contracts/05-desktop-telemetry.md); changing
one is a new report schema.
"""

from collections.abc import Sequence

GIB = 1024**3


def _bucket(value: float, edges: Sequence[tuple[float, str]], top: str) -> str:
    """The label of the first edge `value` is below, else `top`."""
    return next((label for edge, label in edges if value < edge), top)


def turns_bucket(count: int) -> str:
    if count == 0:
        return "0"
    return _bucket(count, ((10, "1-9"), (50, "10-49")), "50+")


def sources_bucket(count: int) -> str:
    if count == 0:
        return "0"
    return _bucket(count, ((10, "1-9"), (100, "10-99"), (1000, "100-999")), "1000+")


def studio_outputs_bucket(count: int) -> str:
    if count == 0:
        return "0"
    return _bucket(count, ((5, "1-4"),), "5+")


def plugin_calls_bucket(count: int) -> str:
    if count == 0:
        return "0"
    return _bucket(count, ((10, "1-9"),), "10+")


# Installed memory reads up to about 1.5 GiB short once firmware and an
# integrated GPU keep their share: a 16 GB laptop reports 14.5-15.8 GiB.
_RAM_SLACK_GIB = 1.5
# A card reports a little under its label: an 8 GB card, 7.6-8.0 GiB.
_VRAM_SLACK_GIB = 0.5


def ram_bucket(total_bytes: int) -> str:
    gib = total_bytes / GIB + _RAM_SLACK_GIB
    return _bucket(gib, ((8, "<8"), (16, "8-15"), (32, "16-31"), (64, "32-63")), "64+")


def vram_bucket(total_bytes: int) -> str:
    """A card's own memory; "0" is for no card, which the caller decides."""
    gib = total_bytes / GIB + _VRAM_SLACK_GIB
    return _bucket(gib, ((4, "<4"), (8, "4-7"), (12, "8-11"), (24, "12-23")), "24+")
