"""The ctypes probe, against the libraries that actually ship.

Skipped when llama.cpp has not been staged, because there is nothing honest to
assert without it: a mocked ggml would only prove the mock works.
"""

from pathlib import Path

import pytest

from modules.llm.hardware import DeviceType, load, probe_devices, select_device

pytestmark = pytest.mark.unit

LIBRARY_DIR = Path(__file__).resolve().parents[5] / "electron" / "llamacpp"
staged = pytest.mark.skipif(
    not LIBRARY_DIR.exists(), reason="run `pnpm build:llamacpp` to stage llama.cpp"
)


@staged
def test_the_probe_finds_the_machines_devices() -> None:
    """Every supported host has at least a CPU device, so an empty list is a bug."""
    devices = probe_devices(LIBRARY_DIR)

    assert devices
    assert any(d.type is DeviceType.CPU for d in devices)


@staged
def test_the_probe_leaves_the_working_directory_where_it_found_it() -> None:
    """It chdirs to satisfy ggml's backend scan, and this process has other work."""
    before = Path.cwd()

    probe_devices(LIBRARY_DIR)

    assert Path.cwd() == before


@staged
def test_a_device_type_outside_the_enum_never_reaches_a_caller() -> None:
    """Accelerate lists on every Mac at a value a three-member enum would reject."""
    for device in probe_devices(LIBRARY_DIR):
        assert isinstance(device.type, DeviceType)


@staged
def test_the_selected_device_is_never_larger_than_a_real_one() -> None:
    """The guard against summing devices, asserted on whatever this host reports."""
    devices = probe_devices(LIBRARY_DIR)
    chosen = select_device(devices)

    if chosen is not None:
        assert chosen.total_bytes <= max(d.total_bytes for d in devices)


@staged
def test_one_handle_resolves_every_symbol_off_windows() -> None:
    """Windows needs two handles because PE exports do not chain. Everywhere else
    the dependency record does it, and a regression here is an AttributeError at
    startup rather than a wrong answer, so it is worth pinning."""
    libraries = load(LIBRARY_DIR)

    assert libraries.core.ggml_backend_load_all
    assert libraries.base.ggml_backend_dev_memory
