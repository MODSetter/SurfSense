"""One reading of the machine, with the app's share of each resource.

The figures are the Windows test machine's while a chat model was loaded: an
RTX 3080 with 10 GB, llama-server holding 5.7 GB of it, a browser 2.4 GB.
"""

import pytest

from modules.resource_usage.engines import Engine
from modules.resource_usage.gpu.reading import GpuReading
from modules.resource_usage.snapshot import ProcessSample, SystemSample, assemble

pytestmark = pytest.mark.unit

GIB = 1024**3
MIB = 1024**2

LLAMA, LLAMA_WORKER, API, SHELL, SHELL_GPU, BROWSER = 25028, 25029, 300, 100, 101, 1788

SYSTEM = SystemSample(
    cpu_percent=31.0,
    logical_cores=16,
    memory_total_bytes=16 * GIB,
    memory_available_bytes=6 * GIB,
)

PROCESSES = [
    ProcessSample(LLAMA, Engine.LLAMACPP, cpu_percent=2.0, memory_bytes=20 * MIB),
    ProcessSample(LLAMA_WORKER, Engine.LLAMACPP, 400.0, 1161 * MIB),
    ProcessSample(API, Engine.BACKEND, 16.0, 1500 * MIB),
    ProcessSample(SHELL, Engine.INTERFACE, 1.0, 196 * MIB),
    ProcessSample(SHELL_GPU, Engine.INTERFACE, 1.0, 54 * MIB),
]

RTX_3080 = GpuReading(
    name="NVIDIA GeForce RTX 3080",
    total_bytes=10_541_334_528,
    used_bytes=7_928_270_848,
    busy_percent=64.0,
    process_bytes={LLAMA_WORKER: 5673 * MIB, SHELL_GPU: 90 * MIB, BROWSER: 2406 * MIB},
    process_busy={LLAMA_WORKER: 60.0, BROWSER: 4.0},
)


def engine(usage, name: Engine):
    """The engine row with this name."""
    return next(e for e in usage.engines if e.engine is name)


def test_the_app_share_of_memory_is_the_sum_of_its_processes() -> None:
    """In use is total minus available; the app is its processes' resident sizes."""
    usage = assemble(PROCESSES, SYSTEM, [])

    assert usage.memory.total_bytes == 16 * GIB
    assert usage.memory.used_bytes == 10 * GIB
    assert usage.memory.app_bytes == (20 + 1161 + 1500 + 196 + 54) * MIB


def test_cpu_is_a_share_of_the_whole_machine_not_of_one_core() -> None:
    """psutil reports a process busy on four cores as 400%. On sixteen cores
    that is a quarter of the machine."""
    usage = assemble(PROCESSES, SYSTEM, [])

    assert usage.cpu.percent == 31.0
    assert usage.cpu.app_percent == pytest.approx((2 + 400 + 16 + 1 + 1) / 16)
    assert engine(usage, Engine.LLAMACPP).cpu_percent == pytest.approx(402 / 16)


def test_only_the_apps_processes_count_toward_its_graphics_memory() -> None:
    """The browser's 2.4 GB is in the card's total and not in the app's share."""
    usage = assemble(PROCESSES, SYSTEM, [RTX_3080])

    (card,) = usage.gpus
    assert card.name == "NVIDIA GeForce RTX 3080"
    assert card.memory.used_bytes == 7_928_270_848
    assert card.memory.app_bytes == (5673 + 90) * MIB
    assert card.load.percent == 64.0
    assert card.load.app_percent == 60.0
    assert engine(usage, Engine.LLAMACPP).gpu_memory_bytes == 5673 * MIB
    assert engine(usage, Engine.INTERFACE).gpu_memory_bytes == 90 * MIB


def test_every_engine_is_listed_even_when_it_is_not_running() -> None:
    """sd-server runs only once an image model is on disk."""
    usage = assemble(PROCESSES, SYSTEM, [RTX_3080])

    assert [e.engine for e in usage.engines] == list(Engine)
    idle = engine(usage, Engine.SDCPP)
    assert (idle.processes, idle.memory_bytes, idle.gpu_memory_bytes) == (0, 0, 0)


def test_a_card_that_cannot_attribute_its_memory_says_unknown_not_zero() -> None:
    """amdgpu on Linux and Apple's unified memory report the device only. Zero
    would read as the app using none of it."""
    device_only = GpuReading("AMD GPU", total_bytes=16 * GIB, used_bytes=9 * GIB)

    usage = assemble(PROCESSES, SYSTEM, [device_only])

    assert usage.gpus[0].memory.app_bytes is None
    assert usage.gpus[0].load.app_percent is None
    assert engine(usage, Engine.LLAMACPP).gpu_memory_bytes is None


def test_a_machine_without_a_graphics_card_reports_none() -> None:
    """No card: no graphics rows, and the engines' graphics figures are unknown."""
    usage = assemble(PROCESSES, SYSTEM, [])

    assert usage.gpus == []
    assert engine(usage, Engine.LLAMACPP).gpu_memory_bytes is None


def test_shared_pages_counted_per_process_never_exceed_what_is_in_use() -> None:
    """Each process's resident size counts the libraries it shares, so the sum
    can pass the machine's own figure, and a meter past full is nonsense."""
    tight = SystemSample(
        10.0, 16, memory_total_bytes=4 * GIB, memory_available_bytes=2 * GIB
    )

    usage = assemble(PROCESSES, tight, [])

    assert usage.memory.app_bytes == 2 * GIB
