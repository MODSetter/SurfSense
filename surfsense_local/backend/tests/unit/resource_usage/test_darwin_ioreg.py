"""Apple Silicon's GPU from `ioreg -r -d 1 -w 0 -c IOAccelerator`.

The listing is the accelerator node an M2 prints, trimmed to the keys read and
a few beside them. The memory is system RAM, so the reading is unified.
"""

import pytest

from modules.resource_usage.gpu.darwin.ioreg import parse

pytestmark = pytest.mark.unit

M2 = """\
+-o AGXAcceleratorG14G  <class AGXAcceleratorG14G, id 0x1000002d5, registered, matched, active, busy 0 (0 ms), retain 88>
    {
      "IOClass" = "AGXAcceleratorG14G"
      "model" = "Apple M2"
      "PerformanceStatistics" = {"In use system memory (driver)"=0,"Alloc system memory"=5460459520,"Tiler Utilization %"=3,"Renderer Utilization %"=11,"In use system memory"=2684354560,"Device Utilization %"=12}
      "gpu-core-count" = 10
    }
"""


def test_reads_the_memory_in_use_and_how_busy_the_gpu_is() -> None:
    """The two statistics the panel shows, and the model name."""
    (gpu,) = parse(M2)

    assert gpu.name == "Apple M2"
    assert gpu.in_use_bytes == 2_684_354_560
    assert gpu.busy_percent == 12.0


def test_the_drivers_own_figure_is_not_mistaken_for_the_total() -> None:
    """The driver's own "In use system memory (driver)" comes first and is 0."""
    (gpu,) = parse(M2)

    assert gpu.in_use_bytes != 0


def test_a_node_without_statistics_is_skipped() -> None:
    """Not every accelerator node carries PerformanceStatistics."""
    bare = '+-o IOAccelerator  <class IOAccelerator>\n    {\n      "IOClass" = "X"\n    }\n'

    assert parse(bare) == []


def test_an_unnamed_gpu_still_reads() -> None:
    """A node without a model key is still a GPU worth a row."""
    (gpu,) = parse(M2.replace('"model" = "Apple M2"', ""))

    assert gpu.name == "Apple GPU"
