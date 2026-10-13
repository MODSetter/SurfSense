from collections.abc import Iterator

import pytest
from httpx import AsyncClient

from shared.config import get_plugin_host_settings
from tests.license_samples import (
    INDIVIDUAL_KEY,
    TRIAL_KEY,
    import_license,
    trust_sample_licenses,
)
from tests.mcp_test_server import (
    RequiringLicense,
    plugin_host,
    reddit_server,
    serving,
)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def sample_licenses(monkeypatch: pytest.MonkeyPatch) -> None:
    """The contract's sample license files verify."""
    trust_sample_licenses(monkeypatch)


@pytest.fixture
def host(monkeypatch: pytest.MonkeyPatch) -> Iterator[RequiringLicense]:
    """SurfSense's plugin host run locally, as a developer's build points at it."""
    guarded: list[RequiringLicense] = []

    def around(app):
        guarded.append(RequiringLicense(app, {TRIAL_KEY: "expired"}))
        return guarded[0]

    with serving(plugin_host("reddit", reddit_server(), around)) as base:
        monkeypatch.setattr(get_plugin_host_settings(), "plugin_host_url", base)
        yield guarded[0]


async def test_surfsense_s_plugins_are_listed_before_any_is_connected(
    client: AsyncClient,
) -> None:
    """Read from the list packaged into the app: no network, no consent."""
    listed = await client.get("/plugins/first-party")

    assert listed.status_code == 200
    reddit = next(entry for entry in listed.json() if entry["id"] == "reddit")
    assert reddit["name"] == "Reddit"
    assert reddit["access"] == "license"
    assert reddit["connected"] is False
    assert reddit["has_icon"] is True
    assert reddit["tools"] == ["scrape"]
    assert reddit["added"] == "2026-10"
    assert reddit["about"] and reddit["about"] != reddit["description"]


async def test_a_first_party_icon_is_served_from_the_app(client: AsyncClient) -> None:
    """Packaged beside the list, so no network; sandboxed, as the registry's are."""
    icon = await client.get("/plugins/first-party/icons/reddit")
    unknown = await client.get("/plugins/first-party/icons/nope")

    assert icon.status_code == 200
    assert icon.headers["content-type"] == "image/svg+xml"
    assert "sandbox" in icon.headers["content-security-policy"]
    assert icon.content.lstrip().startswith(b"<svg")
    assert unknown.status_code == 404


async def test_connecting_with_a_license_sends_its_key(
    client: AsyncClient, host: RequiringLicense
) -> None:
    """Every request to SurfSense's plugin host carries the imported license's key."""
    await import_license(client, "individual.lic")

    connected = await client.post("/plugins/first-party/reddit")

    assert connected.status_code == 201, connected.text
    plugin = connected.json()
    assert (plugin["source"], plugin["publisher"]) == ("first_party", "surfsense")
    assert plugin["check_failure"] is None
    assert [tool["name"] for tool in plugin["tools"]] == ["search_posts"]
    assert set(host.authorizations) == {f"License {INDIVIDUAL_KEY}"}
    listed = (await client.get("/plugins/first-party")).json()
    assert [entry["id"] for entry in listed if entry["connected"]] == ["reddit"]


async def test_connecting_without_a_license_says_one_is_needed(
    client: AsyncClient, host: RequiringLicense
) -> None:
    """Connect is never blocked: the server's refusal says what is missing."""
    connected = await client.post("/plugins/first-party/reddit")

    assert connected.status_code == 201, connected.text
    assert connected.json()["check_failure"] == "needs_license"
    assert set(host.authorizations) == {None}


async def test_an_expired_license_reads_as_expired(
    client: AsyncClient, host: RequiringLicense
) -> None:
    """The server's reason, not a generic sign-in failure."""
    await import_license(client, "trial.lic")

    connected = await client.post("/plugins/first-party/reddit")

    assert connected.json()["check_failure"] == "license_expired"


async def test_a_new_license_is_used_at_the_next_check(
    client: AsyncClient, host: RequiringLicense
) -> None:
    """The key is read from the license each time, never copied onto the plugin."""
    await client.post("/plugins/first-party/reddit")
    await import_license(client, "individual.lic")

    checked = await client.post("/plugins/reddit/check")

    assert checked.json()["check_failure"] is None


async def test_the_key_never_leaves_for_another_host(
    client: AsyncClient, host: RequiringLicense, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A plugin connected on one plugin host, checked after the build points elsewhere."""
    await import_license(client, "individual.lic")
    await client.post("/plugins/first-party/reddit")
    monkeypatch.setattr(
        get_plugin_host_settings(), "plugin_host_url", "http://127.0.0.1:9"
    )
    host.authorizations.clear()

    await client.post("/plugins/reddit/check")

    assert set(host.authorizations) == {None}


async def test_connecting_twice_is_refused(
    client: AsyncClient, host: RequiringLicense
) -> None:
    """A stale screen gets a clear answer, not a second copy."""
    await client.post("/plugins/first-party/reddit")

    again = await client.post("/plugins/first-party/reddit")

    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "plugin_already_connected"


async def test_an_unlisted_plugin_is_a_404(client: AsyncClient) -> None:
    """Only the packaged list's plugins connect this way."""
    assert (await client.post("/plugins/first-party/nope")).status_code == 404


async def test_a_custom_plugin_never_takes_a_first_party_id(
    client: AsyncClient, notes_url: str
) -> None:
    """So SurfSense's own plugin can still be connected under its id."""
    added = await client.post(
        "/plugins/custom", json={"url": notes_url, "name": "Reddit"}
    )

    assert added.json()["id"] == "reddit-plugin"
