from collections.abc import Iterator

import pytest

from proprietary.instagram import fetch


@pytest.fixture(autouse=True)
def fresh_login_walls(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The login-wall latch is process-wide; give each test its own."""
    monkeypatch.setattr(fetch, "_login_walls", {})
    yield


from proprietary.instagram.tests.on_the_host import instagram  # noqa: E402, F401
