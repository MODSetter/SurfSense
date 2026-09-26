"""The protocol between the probe child and its parent."""

import pytest

from modules.llm.hardware import Device, DeviceType, decode_lines, encode_line

pytestmark = pytest.mark.unit

GIB = 1024**3


def test_a_device_survives_the_round_trip() -> None:
    """The contract, stated once."""
    device = Device("Vulkan0", "NVIDIA GeForce RTX 3050", DeviceType.GPU, 6 * GIB, 5 * GIB)

    assert decode_lines(encode_line(device)) == [device]


def test_a_separator_inside_a_description_does_not_shift_the_fields() -> None:
    """A description carries whatever a driver put in it, and the fields are
    read positionally, so a stray tab would move memory into the type column."""
    device = Device("Vulkan0", "Weird\tVendor\tCard", DeviceType.GPU, 6 * GIB, 5 * GIB)

    decoded = decode_lines(encode_line(device))

    assert decoded[0].total_bytes == 6 * GIB
    assert decoded[0].type is DeviceType.GPU


def test_a_log_line_on_the_same_stream_is_skipped_not_fatal() -> None:
    """ggml logs to stdout on some backends, and losing the whole listing over
    one of its lines would turn a working machine into a GPU-less one."""
    device = Device("MTL0", "Apple M2", DeviceType.GPU, 8 * GIB, 5 * GIB)
    noisy = "ggml_metal_init: found device\n" + encode_line(device) + "\nload: done\n"

    assert decode_lines(noisy) == [device]


def test_a_device_type_the_enum_does_not_know_is_not_a_crash() -> None:
    """ggml has added a member twice and will again, and this runs at startup."""
    assert decode_lines(f"X\tY\t99\t{GIB}\t{GIB}")[0].type is DeviceType.UNKNOWN


def test_nothing_at_all_decodes_to_nothing() -> None:
    """An empty listing is a real answer: a machine ggml found no devices on."""
    assert decode_lines("") == []
