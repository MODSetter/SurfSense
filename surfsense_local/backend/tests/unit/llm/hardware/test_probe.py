"""The in-process ctypes probe, against the libraries that actually ship.

The fallback path, used when a child process cannot be spawned. What the app
calls is `probe_devices`, which runs this in a child.

Skipped when llama.cpp has not been staged, because there is nothing honest to
assert without it: a mocked ggml would only prove the mock works.
"""

import logging
import os
from pathlib import Path

import pytest

from modules.llm.hardware import (
    DeviceType,
    load,
    probe_devices,
    probe_devices_in_process,
    select_device,
)

pytestmark = pytest.mark.unit

LIBRARY_DIR = Path(__file__).resolve().parents[5] / "electron" / "llamacpp"
staged = pytest.mark.skipif(
    not LIBRARY_DIR.exists(), reason="run `pnpm build:llamacpp` to stage llama.cpp"
)


@staged
def test_the_probe_finds_the_machines_devices() -> None:
    """Every supported host has at least a CPU device, so an empty list is a bug."""
    devices = probe_devices_in_process(LIBRARY_DIR)

    assert devices
    assert any(d.type is DeviceType.CPU for d in devices)


@staged
def test_the_probe_leaves_the_working_directory_where_it_found_it() -> None:
    """It chdirs to satisfy ggml's backend scan, and this process has other work."""
    before = Path.cwd()

    probe_devices_in_process(LIBRARY_DIR)

    assert Path.cwd() == before


@staged
def test_a_device_type_outside_the_enum_never_reaches_a_caller() -> None:
    """Accelerate lists on every Mac at a value a three-member enum would reject."""
    for device in probe_devices_in_process(LIBRARY_DIR):
        assert isinstance(device.type, DeviceType)


@staged
def test_the_selected_device_is_never_larger_than_a_real_one() -> None:
    """The guard against summing devices, asserted on whatever this host reports."""
    devices = probe_devices_in_process(LIBRARY_DIR)
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


@staged
def test_the_child_process_sees_what_this_process_sees(caplog) -> None:
    """The two paths must agree, and the child must be the one that answered.

    Comparing the results alone proves nothing: the fallback returns the same
    devices, so a child that never ran passes a comparison. It was a relative
    library path that broke this, spawned into a working directory it was then
    resolved against, and the answer stayed correct while the Metal compile
    moved back into this process. So the absence of the fallback warning is the
    assertion that matters.
    """
    with caplog.at_level(logging.WARNING, logger="modules.llm.hardware.probe_subprocess"):
        devices = probe_devices(LIBRARY_DIR)

    assert devices == probe_devices_in_process(LIBRARY_DIR)
    assert caplog.records == []


@staged
def test_a_relative_library_directory_still_reaches_the_child(caplog) -> None:
    """The caller passes whatever the settings hold, and that can be relative."""
    relative = Path(os.path.relpath(LIBRARY_DIR, Path.cwd()))

    with caplog.at_level(logging.WARNING, logger="modules.llm.hardware.probe_subprocess"):
        devices = probe_devices(relative)

    assert devices
    assert caplog.records == []


def test_a_missing_runtime_is_an_oserror_not_an_empty_listing(tmp_path: Path) -> None:
    """The catalog renders without a staged runtime by catching this. An empty
    list would instead read as a machine that genuinely has no devices."""
    with pytest.raises(OSError):
        probe_devices(tmp_path / "nowhere")
