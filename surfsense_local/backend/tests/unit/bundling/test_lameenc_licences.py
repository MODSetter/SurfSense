"""The worker ships what LGPL-3 §4 asks of lameenc and LAME beside the module."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

BUNDLING = Path(__file__).resolve().parents[3] / "bundling"
LICENCES = BUNDLING / "licenses" / "lameenc"


@pytest.mark.parametrize(
    "name",
    [
        "lameenc-LGPL-3.0.txt",
        "GPL-3.0.txt",
        "LAME-COPYING",
        "LAME-README",
        "SOURCE.txt",
    ],
)
def test_each_licence_text_is_there_and_not_empty(name: str) -> None:
    """An empty file would ship a notice that satisfies nothing."""
    assert (LICENCES / name).stat().st_size > 0


def test_the_worker_bundles_the_licence_folder() -> None:
    """The dist-info carries lameenc's LGPL only: no GPL, nothing of LAME's."""
    inputs = (BUNDLING / "worker_inputs.py").read_text()

    assert '"bundling" / "licenses" / "lameenc"' in inputs
