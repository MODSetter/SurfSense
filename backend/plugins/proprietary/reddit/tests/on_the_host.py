"""The real Reddit plugin served by the host, as the app reaches it, with its proxy sessions faked."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import pytest

from host.app import host_app
from host.tests.serving import serving
from proprietary.license_check.tests.stand_in_keygen import (
    ACCOUNT,
    StandInKeygen,
    accounts_url,
)
from proprietary.reddit import scraper

LICENSE = {"Authorization": "License k-1"}


@pytest.fixture
def reddit(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The real Reddit plugin on the host, its license checked by a stand-in Keygen."""
    with serving(StandInKeygen({"k-1": "VALID"}).app) as keygen_url:
        monkeypatch.setenv("KEYGEN_API_URL", accounts_url(keygen_url))
        monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
        with serving(host_app(plugins={"reddit"})) as base:
            yield f"{base}/reddit/mcp"


def no_proxy_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    class Holder:
        async def close(self) -> None:
            pass

    async def open_holder() -> Holder:
        return Holder()

    @asynccontextmanager
    async def bind(holder: Holder) -> AsyncIterator[Holder]:
        yield holder

    monkeypatch.setattr(scraper, "open_proxy_holder", open_holder)
    monkeypatch.setattr(scraper, "bind_proxy_holder", bind)
