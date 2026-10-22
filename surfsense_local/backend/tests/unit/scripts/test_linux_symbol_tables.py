"""Linux stripping leaves the libraries auditwheel rewrote alone."""

from pathlib import Path

import pytest
from linux_symbol_tables import _vendored_by_auditwheel

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "path",
    [
        "numpy.libs/libscipy_openblas64_-61654e39.so",
        "scipy.libs/libgfortran-040039e1.so.5.0.0",
        "torch/lib/libgomp-a34b3233.so.1",
        "opencv_python_headless.libs/libpng16-2a9e1b8b.so.16.43.0",
    ],
)
def test_a_library_auditwheel_vendored_is_not_stripped(path: str) -> None:
    """patchelf rewrote its headers, and strip then leaves it unloadable."""
    assert _vendored_by_auditwheel(Path(path))


@pytest.mark.parametrize(
    "path",
    [
        "torch/lib/libtorch_cpu.so",
        "numpy/_core/_multiarray_umath.cpython-312-x86_64-linux-gnu.so",
        "onnxruntime/capi/onnxruntime_pybind11_state.so",
    ],
)
def test_every_other_library_is(path: str) -> None:
    """Their symbol tables are what the strip saves."""
    assert not _vendored_by_auditwheel(Path(path))
