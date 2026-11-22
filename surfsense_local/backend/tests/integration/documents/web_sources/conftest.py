from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field

import pytest
from httpx import AsyncClient
from starlette.requests import Request
from starlette.responses import Response

from tests.integration.documents.web_sources.stand_in_site import searxng, site
from tests.mcp_test_server import serving


@dataclass
class Site:
    base: str
    asked: list[Request] = field(default_factory=list)

    def at(self, path: str) -> str:
        return f"{self.base}{path}"


@pytest.fixture
def stand_in_site() -> Iterator[Site]:
    """A site on loopback: reading it needs no consent, as nothing leaves the machine."""
    asked: list[Request] = []
    with serving(site(asked)) as base:
        yield Site(base, asked)


@dataclass
class SearchServer:
    base: str
    asked: list[Request]
    answers: list[Response]

    def answer(self, response: Response) -> None:
        self.answers.append(response)


@pytest.fixture
async def search_server(client: AsyncClient) -> AsyncIterator[SearchServer]:
    """A SearXNG server on loopback, chosen in Settings as a firm would choose its own."""
    asked: list[Request] = []
    answers: list[Response] = []

    def answer(_: Request) -> Response:
        return answers.pop(0)

    with serving(searxng(answer, asked)) as base:
        chosen = await client.put("/web-search/server", json={"url": base})
        assert chosen.status_code == 200, chosen.text
        yield SearchServer(base, asked, answers)


@pytest.fixture
async def workspace_id(client: AsyncClient) -> int:
    """Sources belong to a workspace."""
    created = await client.post("/workspaces", json={"name": "Research"})
    return int(created.json()["id"])


async def allow(client: AsyncClient, *hosts: str) -> None:
    """As the consent prompt's Allow does."""
    allowed = await client.put(
        "/egress",
        json={"destinations": [f"host:{host}" for host in hosts], "enabled": True},
    )
    assert allowed.status_code == 200, allowed.text
