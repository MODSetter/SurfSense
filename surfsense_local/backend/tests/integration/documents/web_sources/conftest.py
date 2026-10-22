from collections.abc import Iterator
from contextlib import ExitStack

import pytest
from httpx import AsyncClient

from shared.config import get_plugin_host_settings
from tests.integration.documents.web_sources.stand_in_plugins import (
    Answer,
    Calls,
    every_plugin,
    plugin_host,
)
from tests.license_samples import TRIAL_KEY, trust_sample_licenses
from tests.mcp_test_server import RequiringLicense, serving


class ScraperHost:
    """SurfSense's plugin host on loopback, which needs no network consent."""

    def __init__(self, stack: ExitStack, monkeypatch: pytest.MonkeyPatch) -> None:
        self._stack = stack
        self._monkeypatch = monkeypatch
        self.calls: Calls = []
        self.guards: list[RequiringLicense] = []

    def start(self, answers: dict[tuple[str, str], Answer] | None = None) -> None:
        def around(app):
            self.guards.append(RequiringLicense(app, {TRIAL_KEY: "expired"}))
            return self.guards[-1]

        app = plugin_host(every_plugin(answers or {}, self.calls), around)
        base = self._stack.enter_context(serving(app))
        self._monkeypatch.setattr(get_plugin_host_settings(), "plugin_host_url", base)

    def authorizations(self) -> set[str | None]:
        return {sent for guard in self.guards for sent in guard.authorizations}


@pytest.fixture(autouse=True)
def sample_licenses(monkeypatch: pytest.MonkeyPatch) -> None:
    """The contract's sample license files verify."""
    trust_sample_licenses(monkeypatch)


@pytest.fixture
def scraper_host(monkeypatch: pytest.MonkeyPatch) -> Iterator[ScraperHost]:
    """Started by each test with the items its plugins answer."""
    with ExitStack() as stack:
        yield ScraperHost(stack, monkeypatch)


@pytest.fixture
async def workspace_id(client: AsyncClient) -> int:
    """Sources belong to a workspace."""
    created = await client.post("/workspaces", json={"name": "Research"})
    return int(created.json()["id"])
