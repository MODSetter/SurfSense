"""Reading every license, past the 100 one Keygen list request returns."""

from __future__ import annotations

import httpx2
import pytest

from license import keygen
from license.settings import config

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def keygen_config(monkeypatch):
    monkeypatch.setattr(config, "KEYGEN_ACCOUNT_ID", "acct")
    monkeypatch.setattr(config, "KEYGEN_API_TOKEN", "token")
    monkeypatch.setattr(config, "KEYGEN_API_URL", "")
    monkeypatch.setattr(config, "KEYGEN_HOST", "")


def licenses(start: int, count: int) -> list[dict]:
    return [{"id": f"lic-{n}", "type": "licenses"} for n in range(start, start + count)]


async def read_all(pages: list[dict], **kwargs) -> tuple[list[str], list[httpx2.URL]]:
    """Every id the iterator yields, and the URL of every request it sent."""
    seen: list[httpx2.URL] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request.url)
        number = int(request.url.params["page[number]"])
        return httpx2.Response(200, json=pages[number - 1])

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as client:
        ids = [
            item["id"]
            async for item in keygen.iter_licenses(client=client, page_size=2, **kwargs)
        ]
    return ids, seen


async def test_pages_are_read_until_a_short_one():
    ids, seen = await read_all(
        [{"data": licenses(0, 2)}, {"data": licenses(2, 2)}, {"data": licenses(4, 1)}]
    )

    assert ids == ["lic-0", "lic-1", "lic-2", "lic-3", "lic-4"]
    assert [url.params["page[number]"] for url in seen] == ["1", "2", "3"]
    assert {url.params["page[size]"] for url in seen} == {"2"}


async def test_a_full_page_with_no_next_link_is_the_last():
    ids, seen = await read_all([{"data": licenses(0, 2), "links": {"next": None}}])

    assert ids == ["lic-0", "lic-1"]
    assert len(seen) == 1


async def test_an_empty_page_ends_the_read():
    ids, seen = await read_all([{"data": licenses(0, 2)}, {"data": []}])

    assert ids == ["lic-0", "lic-1"]
    assert len(seen) == 2


async def test_filters_are_sent_on_every_page():
    _, seen = await read_all(
        [{"data": licenses(0, 2)}, {"data": []}],
        metadata={"plan": "trial"},
        policy="policy-trial",
    )

    assert all(url.params["metadata[plan]"] == "trial" for url in seen)
    assert all(url.params["policy"] == "policy-trial" for url in seen)
