"""Settings > Network's search server: SurfSense's, or one the user names."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

SERVER = "/web-search/server"


async def test_searches_go_to_surfsenses_server_until_another_is_named(
    client: AsyncClient,
) -> None:
    """The default is named, so Settings can show where searches go."""
    read = await client.get(SERVER)

    assert read.json() == {"url": None, "default_url": "https://searxng.surfsense.com"}


async def test_a_firms_own_server_is_kept_without_its_trailing_slash(
    client: AsyncClient,
) -> None:
    """Under a path too: `/search` is added to whatever base the user gives."""
    chosen = await client.put(
        SERVER, json={"url": "https://search.firm.example/searx/"}
    )

    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["url"] == "https://search.firm.example/searx"
    assert (await client.get(SERVER)).json()["url"] == (
        "https://search.firm.example/searx"
    )


async def test_choosing_none_goes_back_to_surfsenses_server(
    client: AsyncClient,
) -> None:
    """The setting's reset."""
    await client.put(SERVER, json={"url": "https://search.firm.example"})

    reset = await client.put(SERVER, json={"url": None})

    assert reset.json()["url"] is None


@pytest.mark.parametrize(
    "url",
    [
        "search.firm.example",
        "ftp://search.firm.example",
        "https://user:secret@search.firm.example",
        "https://search.firm.example/?q=tides",
    ],
)
async def test_an_address_that_is_not_a_servers_base_is_refused(
    client: AsyncClient, url: str
) -> None:
    """No scheme, another scheme, a password kept in plain text, or a query."""
    refused = await client.put(SERVER, json={"url": url})

    assert refused.status_code == 422
    assert (await client.get(SERVER)).json()["url"] is None
