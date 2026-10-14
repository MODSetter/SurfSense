from collections.abc import Callable, Iterator
from contextlib import ExitStack

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
    amazon_server,
    plugin_host,
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

    with serving(plugin_host("amazon", amazon_server(), around)) as base:
        monkeypatch.setattr(get_plugin_host_settings(), "plugin_host_url", base)
        yield guarded[0]


async def test_surfsense_s_plugins_are_listed_before_any_is_connected(
    client: AsyncClient,
) -> None:
    """Read from the list packaged into the app: no network, no consent."""
    listed = await client.get("/plugins/first-party")

    assert listed.status_code == 200
    amazon = next(entry for entry in listed.json() if entry["id"] == "amazon")
    assert amazon["name"] == "Amazon"
    assert amazon["access"] == "license"
    assert amazon["connected"] is False
    assert amazon["has_icon"] is True
    assert amazon["tools"] == ["scrape"]
    assert amazon["added"] == "2026-10"
    assert amazon["about"] and amazon["about"] != amazon["description"]


async def test_a_first_party_icon_is_served_from_the_app(client: AsyncClient) -> None:
    """Packaged beside the list, so no network; sandboxed, as the registry's are."""
    icon = await client.get("/plugins/first-party/icons/indeed")
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

    connected = await client.post("/plugins/first-party/amazon")

    assert connected.status_code == 201, connected.text
    plugin = connected.json()
    assert plugin["source"] == "first_party"
    assert plugin["check_failure"] is None
    assert [tool["name"] for tool in plugin["tools"]] == ["search_products"]
    assert set(host.authorizations) == {f"License {INDIVIDUAL_KEY}"}
    listed = (await client.get("/plugins/first-party")).json()
    assert [entry["id"] for entry in listed if entry["connected"]] == ["amazon"]


async def test_connecting_without_a_license_says_one_is_needed(
    client: AsyncClient, host: RequiringLicense
) -> None:
    """Connect is never blocked: the server's refusal says what is missing."""
    connected = await client.post("/plugins/first-party/amazon")

    assert connected.status_code == 201, connected.text
    assert connected.json()["check_failure"] == "needs_license"
    assert set(host.authorizations) == {None}


async def test_an_expired_license_reads_as_expired(
    client: AsyncClient, host: RequiringLicense
) -> None:
    """The server's reason, not a generic sign-in failure."""
    await import_license(client, "trial.lic")

    connected = await client.post("/plugins/first-party/amazon")

    assert connected.json()["check_failure"] == "license_expired"


async def test_a_new_license_is_used_at_the_next_check(
    client: AsyncClient, host: RequiringLicense
) -> None:
    """The key is read from the license each time, never copied onto the plugin."""
    await client.post("/plugins/first-party/amazon")
    await import_license(client, "individual.lic")

    checked = await client.post("/plugins/amazon/check")

    assert checked.json()["check_failure"] is None


async def test_the_key_never_leaves_for_another_host(
    client: AsyncClient, host: RequiringLicense, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A plugin connected on one plugin host, checked after the build points elsewhere."""
    await import_license(client, "individual.lic")
    await client.post("/plugins/first-party/amazon")
    monkeypatch.setattr(
        get_plugin_host_settings(), "plugin_host_url", "http://127.0.0.1:9"
    )
    host.authorizations.clear()

    await client.post("/plugins/amazon/check")

    assert set(host.authorizations) == {None}


async def test_connecting_twice_is_refused(
    client: AsyncClient, host: RequiringLicense
) -> None:
    """A stale screen gets a clear answer, not a second copy."""
    await client.post("/plugins/first-party/amazon")

    again = await client.post("/plugins/first-party/amazon")

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
        "/plugins/custom", json={"url": notes_url, "name": "Amazon"}
    )

    assert added.json()["id"] == "amazon-plugin"


class LicenseHost:
    """A plugin host started on demand, with what it was asked."""

    def __init__(self, guard: RequiringLicense, asks: list[str | None]) -> None:
        self.guard = guard
        self.license_asks = asks


@pytest.fixture
def start_host(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., LicenseHost]]:
    """SurfSense's plugin host, with `/license` served, missing, or down."""
    with ExitStack() as stack:

        def start(license_route: str = "served") -> LicenseHost:
            guarded: list[RequiringLicense] = []
            asks: list[str | None] = []

            def around(app):
                guarded.append(RequiringLicense(app, {TRIAL_KEY: "expired"}))
                return guarded[-1]

            base = stack.enter_context(
                serving(
                    plugin_host(
                        "amazon",
                        amazon_server(),
                        around,
                        license_asks=asks,
                        license_route=license_route,
                    )
                )
            )
            monkeypatch.setattr(get_plugin_host_settings(), "plugin_host_url", base)
            return LicenseHost(guarded[0], asks)

        yield start


async def amazon_failure(client: AsyncClient) -> str | None:
    """The connected Amazon plugin's last check, as Settings > Plugins reads it."""
    plugins = (await client.get("/plugins")).json()
    return next(p for p in plugins if p["id"] == "amazon")["check_failure"]


async def test_removing_the_license_says_one_is_needed_at_once(
    client: AsyncClient, start_host: Callable[..., LicenseHost]
) -> None:
    """Asked once of the plugin host, not by listing each paid plugin."""
    host = start_host()
    await import_license(client, "individual.lic")
    await client.post("/plugins/first-party/amazon")
    listings = len(host.guard.authorizations)

    await client.delete("/license")
    checked = await client.post("/plugins/license/check")

    assert checked.status_code == 204
    assert await amazon_failure(client) == "needs_license"
    assert host.license_asks == [None]
    assert len(host.guard.authorizations) == listings


async def test_a_license_imported_again_clears_the_verdict_at_once(
    client: AsyncClient, start_host: Callable[..., LicenseHost]
) -> None:
    """No Refresh tools needed: importing asks the host straight away."""
    start_host()
    await client.post("/plugins/first-party/amazon")
    assert await amazon_failure(client) == "needs_license"

    await import_license(client, "individual.lic")
    await client.post("/plugins/license/check")

    assert await amazon_failure(client) is None


async def test_a_host_without_the_route_changes_nothing(
    client: AsyncClient, start_host: Callable[..., LicenseHost]
) -> None:
    """No `/license` is no answer: the verdict stays, and nothing is listed for it."""
    host = start_host(license_route="missing")
    await import_license(client, "individual.lic")
    await client.post("/plugins/first-party/amazon")
    listings = len(host.guard.authorizations)

    await client.delete("/license")
    await client.post("/plugins/license/check")

    assert await amazon_failure(client) is None
    assert len(host.guard.authorizations) == listings


async def test_no_answer_from_the_host_keeps_the_last_verdict(
    client: AsyncClient, start_host: Callable[..., LicenseHost]
) -> None:
    """Keygen down, or the host unreachable, never changes what the user sees."""
    start_host(license_route="down")
    await client.post("/plugins/first-party/amazon")

    await import_license(client, "individual.lic")
    await client.post("/plugins/license/check")

    assert await amazon_failure(client) == "needs_license"


async def test_a_fresh_verdict_is_not_asked_for_again(
    client: AsyncClient, start_host: Callable[..., LicenseHost]
) -> None:
    """Opening Plugins asks only when the last answer is older than five minutes."""
    host = start_host()
    await import_license(client, "individual.lic")
    await client.post("/plugins/first-party/amazon")

    await client.post("/plugins/license/check")
    await client.post("/plugins/license/check", params={"if_stale": True})

    assert len(host.license_asks) == 1
