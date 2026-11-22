"""Settings > Network's search server: none until the user names one."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

SERVER = "/web-search/server"


async def test_no_server_is_named_until_the_user_names_one(
    client: AsyncClient,
) -> None:
    """There is no default server, so a fresh install searches nowhere."""
    read = await client.get(SERVER)

    assert read.json() == {"url": None}


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


async def test_choosing_none_turns_search_off_again(
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
        "https://search.firm.example:88a8",
        "https://search.firm.example:99999",
        "http://192.168.1.256:8888",
    ],
)
async def test_an_address_that_is_not_a_servers_base_is_refused(
    client: AsyncClient, url: str
) -> None:
    """No scheme, another scheme, a password kept in plain text, a query, a bad port,
    or a host no request can be sent to, such as a mistyped LAN address."""
    refused = await client.put(SERVER, json={"url": url})

    assert refused.status_code == 422
    assert (await client.get(SERVER)).json()["url"] is None
