from collections.abc import Iterator

import pytest

from proprietary.reddit import fetch


@pytest.fixture(autouse=True)
def fresh_closed_latch(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The closed-endpoint latch is process-wide; give each test its own."""
    monkeypatch.setattr(fetch, "_closed", fetch._ClosedLatch())
    yield


from proprietary.reddit.tests.on_the_host import reddit  # noqa: E402, F401
