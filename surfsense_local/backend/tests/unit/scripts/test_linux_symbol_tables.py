"""Linux stripping keeps only copies glibc will still load."""

import struct

import pytest
from linux_symbol_tables import loads_aligned

pytestmark = pytest.mark.unit


def _elf(*loads: tuple[int, int], align: int = 0x1000) -> bytes:
    """A 64-bit little-endian ELF header with one PT_LOAD per (offset, vaddr)."""
    header = bytearray(0x40)
    header[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<Q", header, 0x20, 0x40)
    struct.pack_into("<HH", header, 0x36, 56, len(loads))
    for offset, vaddr in loads:
        entry = bytearray(56)
        struct.pack_into("<I", entry, 0, 1)
        struct.pack_into("<QQ", entry, 8, offset, vaddr)
        struct.pack_into("<Q", entry, 48, align)
        header += entry
    return bytes(header)


def test_a_segment_off_its_own_alignment_is_not_used() -> None:
    """Newer glibc checks the segment's p_align, not just the page."""
    assert not loads_aligned(_elf((0x1000, 0x201000 + 0x1000), align=0x200000))


def test_a_library_whose_segments_stay_on_the_page_grid_loads() -> None:
    """The ordinary layout: each segment's address and offset agree mod 4096."""
    assert loads_aligned(_elf((0, 0), (0x1F000, 0x20F000)))


def test_a_library_strip_moved_off_the_page_grid_does_not() -> None:
    """What strip did to numpy's OpenBLAS and torchvision's image_stable.so."""
    assert not loads_aligned(_elf((0, 0), (0x1F010, 0x20F000)))


def test_anything_but_a_64_bit_little_endian_elf_is_never_replaced() -> None:
    """The bundle is built for x86-64 only; anything else keeps its original."""
    assert not loads_aligned(b"MZ" + bytes(0x40))
