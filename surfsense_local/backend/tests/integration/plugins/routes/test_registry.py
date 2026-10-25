import json
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.plugins.gateway.listing import list_tools
from modules.plugins.lists.registry import (
    current_registry,
    registry_keys,
    registry_origin,
)
from shared.config import get_plugin_host_settings
from shared.db import create_session_factory
from tests.mcp_test_server import RequiringHeader, RequiringToken, notes_server, serving
from tests.registry_stand_in import SVG, StandInRegistry, entry

pytestmark = pytest.mark.integration


@pytest.fixture
def registry(monkeypatch: pytest.MonkeyPatch) -> Iterator[StandInRegistry]:
    """A packaged app reaching SurfSense's plugin host, run locally, with its key trusted."""
    stand_in = StandInRegistry()
    notes = notes_server()
    keyed = notes_server()
    headed = notes_server()
    app = stand_in.app(
        {
            "notes": notes.streamable_http_app(),
            "keyed": RequiringToken(keyed.streamable_http_app(), "k-1"),
            "headed": RequiringHeader(headed.streamable_http_app(), "x-api-key", "k-9"),
        },
        [notes, keyed, headed],
    )
    monkeypatch.setattr(registry_origin, "reads_repository", lambda: False)
    monkeypatch.setattr(
        registry_keys, "REGISTRY_PUBLIC_KEYS_HEX", (stand_in.public_key_hex,)
    )
    with serving(app) as base:
        monkeypatch.setattr(get_plugin_host_settings(), "plugin_host_url", base)
        yield stand_in


async def allow_third_party(client: AsyncClient) -> None:
    """Turn third-party plugins on, as the switch's Allow does."""
    allowed = await client.put("/plugins/third-party", json={"allowed": True})
    assert allowed.status_code == 204


@pytest.mark.third_party_off
async def test_nothing_is_fetched_while_third_party_plugins_are_off(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """The route answers that they are off, and no request leaves the machine."""
    listed = await client.get("/plugins/registry")

    assert listed.status_code == 200
    assert listed.json()["third_party_off"] is True
    assert listed.json()["plugins"] == []
    assert registry.requests == []


async def test_a_signed_registry_is_listed_once_third_party_plugins_are_allowed(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """A plugin proven to be its author's is verified; the rest are community, both by their author."""
    registry.publish(
        [
            entry(
                "notes",
                about="Search and count your notes.",
                tools=["search", "count"],
                added="2026-10",
            ),
            entry(
                "keyed",
                verification="verified",
                author="Keyed Inc.",
                auth={
                    "type": "token",
                    "title": "API key",
                    "description": "From your account page.",
                },
                access="external",
                access_note="Requires a Keyed account.",
            ),
        ]
    )
    await allow_third_party(client)

    listed = (await client.get("/plugins/registry")).json()

    assert listed["third_party_off"] is False
    assert listed["fetched_at"] is not None
    notes, keyed = listed["plugins"]
    assert (notes["id"], notes["verification"], notes["verified"]) == (
        "notes",
        "community",
        False,
    )
    assert notes["author"] == "Notes Project"
    assert notes["about"] == "Search and count your notes."
    assert notes["tools"] == ["search", "count"]
    assert notes["added"] == "2026-10"
    assert keyed["added"] is None
    assert keyed["about"] is None
    assert keyed["tools"] is None
    assert notes["connected"] is False
    assert (keyed["verification"], keyed["verified"], keyed["author"]) == (
        "verified",
        True,
        "Keyed Inc.",
    )
    # As this build reaches it: a developer's plugin host stands in for SurfSense's.
    assert (notes["server_host"], notes["sign_in_hosts"]) == (notes["hosts"][0], [])
    assert (keyed["auth_type"], keyed["auth_title"]) == ("token", "API key")
    assert keyed["access_note"] == "Requires a Keyed account."
    assert registry.requests == ["/plugins.json", "/plugins.json.sig"]


async def test_an_oauth_plugin_lists_its_sign_in_hosts_apart_from_its_server(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """The server receives every call; a sign-in host only the sign-in."""
    registry.publish(
        [
            entry(
                "notes",
                auth={"type": "oauth"},
                hosts=["plugins.surfsense.com", "accounts.example.com"],
            )
        ]
    )
    await allow_third_party(client)

    [notes] = (await client.get("/plugins/registry")).json()["plugins"]

    assert notes["server_host"] == notes["hosts"][0]
    assert notes["sign_in_hosts"] == ["accounts.example.com"]


def refresh_every_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """As if the last fetch were long ago, so each request fetches again."""
    monkeypatch.setattr(current_registry, "REFRESH_EVERY", timedelta(0))


async def listed_ids(client: AsyncClient) -> list[str]:
    """The ids the registry route lists now."""
    listed = await client.get("/plugins/registry")
    assert listed.status_code == 200, listed.text
    return [plugin["id"] for plugin in listed.json()["plugins"]]


async def test_the_list_is_fetched_at_most_every_few_minutes(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """Opening the screen again soon after reads the cached copy."""
    registry.publish([entry("notes")])
    await allow_third_party(client)
    await client.get("/plugins/registry")

    await client.get("/plugins/registry")

    assert registry.requests == ["/plugins.json", "/plugins.json.sig"]


async def test_a_list_with_a_bad_signature_is_ignored_and_the_cached_copy_kept(
    client: AsyncClient, registry: StandInRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A list no compiled key signed changes nothing."""
    refresh_every_time(monkeypatch)
    registry.publish([entry("notes")])
    await allow_third_party(client)
    assert await listed_ids(client) == ["notes"]

    registry.serve_bytes(
        b'{"schema_version": 1, "generated_at": "2026-10-11T00:00:00Z", "plugins": []}',
        sign_with=Ed25519PrivateKey.generate(),
    )

    assert await listed_ids(client) == ["notes"]


async def test_an_older_list_never_replaces_a_newer_one(
    client: AsyncClient, registry: StandInRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """So an old copy cannot bring back a plugin since removed."""
    refresh_every_time(monkeypatch)
    registry.publish(
        [],
        removed=[{"id": "notes", "reason": "Gone."}],
        generated_at="2026-10-10T12:00:00Z",
    )
    await allow_third_party(client)
    await client.get("/plugins/registry")

    registry.publish([entry("notes")], generated_at="2026-10-09T12:00:00Z")
    listed = (await client.get("/plugins/registry")).json()

    assert listed["plugins"] == []
    assert listed["removed"] == [{"id": "notes", "reason": "Gone."}]


async def test_a_list_of_an_unknown_schema_is_ignored(
    client: AsyncClient, registry: StandInRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A list written for a newer app keeps the cached copy."""
    refresh_every_time(monkeypatch)
    registry.publish([entry("notes")])
    await allow_third_party(client)
    await client.get("/plugins/registry")

    registry.publish(
        [entry("keyed")], generated_at="2026-10-11T00:00:00Z", schema_version=2
    )

    assert await listed_ids(client) == ["notes"]


async def test_offline_the_cached_copy_is_listed_with_its_date(
    client: AsyncClient, registry: StandInRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The section stays listed, dated when it was fetched."""
    refresh_every_time(monkeypatch)
    registry.publish([entry("notes")])
    await allow_third_party(client)
    first = (await client.get("/plugins/registry")).json()
    monkeypatch.setattr(
        get_plugin_host_settings(), "plugin_host_url", "http://127.0.0.1:9"
    )

    offline = (await client.get("/plugins/registry")).json()

    assert [plugin["id"] for plugin in offline["plugins"]] == ["notes"]
    assert offline["fetched_at"] == first["fetched_at"]


async def test_with_no_verified_copy_the_list_is_unavailable(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """Nothing trusted to show: the screen says the list could not be fetched."""
    registry.serve_bytes(b"{}", sign_with=Ed25519PrivateKey.generate())
    await allow_third_party(client)

    listed = await client.get("/plugins/registry")

    assert listed.status_code == 502
    assert listed.json()["detail"]["code"] == "registry_unavailable"


async def test_entries_only_the_first_party_list_may_hold_are_dropped(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """No fetched file can take the license, take SurfSense's ids, or outrun this app."""
    registry.publish(
        [
            entry("wants-license", auth={"type": "license"}),
            entry("sells-license", access="license"),
            entry("amazon"),
            entry("from-the-future", min_app_version="99.0.0"),
            entry("from-the-past", min_app_version="2.0.0"),
            entry("notes"),
        ]
    )
    await allow_third_party(client)

    assert await listed_ids(client) == ["from-the-past", "notes"]


async def test_fetching_needs_the_plugin_host_allowed(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A packaged app asks for plugins.surfsense.com first, and fetches nothing until then."""
    monkeypatch.setattr(registry_origin, "reads_repository", lambda: False)
    await allow_third_party(client)

    listed = await client.get("/plugins/registry")

    assert listed.status_code == 403
    detail = listed.json()["detail"]
    assert detail["code"] == "egress_disabled"
    assert detail["hosts"] == ["plugins.surfsense.com"]
    assert detail["purpose"] == "plugin_registry"


async def test_an_icon_is_served_once_its_bytes_match_the_signed_hash(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """An icon whose hash differs from its entry's is not shown."""
    registry.publish(
        [
            entry("notes", icon="notes.svg"),
            entry("keyed", icon="keyed.svg", icon_sha256="0" * 64),
        ],
        icons={"notes.svg": SVG, "keyed.svg": SVG},
    )
    await allow_third_party(client)

    listed = (await client.get("/plugins/registry")).json()["plugins"]
    notes = await client.get("/plugins/registry/icons/notes")
    keyed = await client.get("/plugins/registry/icons/keyed")

    assert [plugin["has_icon"] for plugin in listed] == [True, False]
    assert notes.status_code == 200
    assert notes.headers["content-type"] == "image/svg+xml"
    assert notes.content == SVG
    assert keyed.status_code == 404


async def test_no_icon_is_served_while_third_party_plugins_are_off(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """Nothing from the registry is shown while they are off."""
    registry.publish([entry("notes", icon="notes.svg")], icons={"notes.svg": SVG})
    await allow_third_party(client)
    await client.get("/plugins/registry")
    await client.put("/plugins/third-party", json={"allowed": False})

    assert (await client.get("/plugins/registry/icons/notes")).status_code == 404


async def test_in_development_the_checkout_s_list_is_read_unsigned(
    client: AsyncClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing is fetched, so no consent is needed."""
    checkout = tmp_path / "checkout-registry"
    (checkout / "icons").mkdir(parents=True)
    (checkout / "icons" / "notes.svg").write_bytes(SVG)
    (checkout / "plugins.json").write_text(
        json.dumps({"schema_version": 1, "plugins": [entry("notes", icon="notes.svg")]})
    )
    monkeypatch.setattr(registry_origin, "reads_repository", lambda: True)
    monkeypatch.setattr(registry_origin, "REPOSITORY_REGISTRY", checkout)
    await allow_third_party(client)

    listed = (await client.get("/plugins/registry")).json()["plugins"]
    icon = await client.get("/plugins/registry/icons/notes")

    assert [(plugin["id"], plugin["has_icon"]) for plugin in listed] == [
        ("notes", True)
    ]
    assert icon.content == SVG


async def test_a_plugin_with_no_sign_in_connects_from_the_registry(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """Stored as the registry's."""
    registry.publish([entry("notes")])
    await allow_third_party(client)

    connected = await client.post("/plugins/registry/notes")

    assert connected.status_code == 201, connected.text
    plugin = connected.json()
    assert plugin["source"] == "registry"
    assert [tool["name"] for tool in plugin["tools"]] == ["search", "count"]
    listed = (await client.get("/plugins/registry")).json()["plugins"]
    assert [p["id"] for p in listed if p["connected"]] == ["notes"]


async def test_a_token_plugin_connects_with_its_key_and_never_returns_it(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """The server refuses it without the key; with it, the key stays inside the app."""
    registry.publish([entry("keyed", auth={"type": "token", "title": "API key"})])
    await allow_third_party(client)

    without = await client.post("/plugins/registry/keyed", json={})
    connected = await client.post("/plugins/registry/keyed", json={"token": "k-1"})

    assert without.status_code == 422
    assert without.json()["detail"]["code"] == "plugin_needs_sign_in"
    assert connected.status_code == 201, connected.text
    assert connected.json()["check_failure"] is None
    assert "k-1" not in (await client.get("/plugins")).text


async def test_a_headers_plugin_connects_with_each_header_its_entry_names(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """The entry names the header and words it; the value is the user's, and stays inside."""
    registry.publish(
        [
            entry(
                "headed",
                auth={
                    "type": "headers",
                    "headers": [{"name": "x-api-key", "label": "Exa API key"}],
                },
            )
        ]
    )
    await allow_third_party(client)

    listed = (await client.get("/plugins/registry")).json()["plugins"][0]
    connected = await client.post(
        "/plugins/registry/headed",
        json={"headers": [{"name": "x-api-key", "value": "k-9"}]},
    )

    assert listed["auth_type"] == "headers"
    assert listed["auth_headers"] == [
        {"name": "x-api-key", "label": "Exa API key", "description": None}
    ]
    assert connected.status_code == 201, connected.text
    assert connected.json()["auth_type"] == "headers"
    assert connected.json()["header_names"] == ["x-api-key"]
    assert "k-9" not in (await client.get("/plugins")).text


async def test_a_headers_entry_adds_its_prefix_to_the_value_typed(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """`Bearer ` is the entry's to add, so the user pastes the key alone."""
    registry.publish(
        [
            entry(
                "keyed",
                auth={
                    "type": "headers",
                    "headers": [{"name": "Authorization", "prefix": "Bearer "}],
                },
            )
        ]
    )
    await allow_third_party(client)

    connected = await client.post(
        "/plugins/registry/keyed",
        json={"headers": [{"name": "Authorization", "value": "k-1"}]},
    )

    assert connected.status_code == 201, connected.text


async def test_editing_a_registry_plugins_headers_keeps_its_entrys_wording(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """The reviewed entry still names the headers and adds their prefix."""
    named = {
        "type": "headers",
        "headers": [{"name": "Authorization", "prefix": "Bearer "}],
    }
    registry.publish([entry("keyed", auth=named)])
    await allow_third_party(client)
    await client.post(
        "/plugins/registry/keyed",
        json={"headers": [{"name": "Authorization", "value": "k-1"}]},
    )

    replaced = await client.put(
        "/plugins/keyed/headers",
        json={"headers": [{"name": "Authorization", "value": "k-1"}]},
    )
    other = await client.put(
        "/plugins/keyed/headers", json={"headers": [{"name": "x-other", "value": "v"}]}
    )

    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["check_failure"] is None
    assert other.status_code == 422
    assert other.json()["detail"]["code"] == "plugin_header_not_allowed"


async def test_a_header_the_entry_does_not_name_is_refused(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """Values go only in the headers the reviewed entry names."""
    registry.publish(
        [entry("headed", auth={"type": "headers", "headers": [{"name": "x-api-key"}]})]
    )
    await allow_third_party(client)

    refused = await client.post(
        "/plugins/registry/headed",
        json={"headers": [{"name": "x-other", "value": "v"}]},
    )

    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "plugin_header_not_allowed"


async def test_an_entry_taking_only_registered_apps_is_kept_needing_the_users_own(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """Kept before any request: the entry already knows the provider takes no other."""
    registry.publish([entry("notes", auth={"type": "oauth", "user_client": True})])
    await allow_third_party(client)

    listed = (await client.get("/plugins/registry")).json()["plugins"][0]
    kept = await client.post("/plugins/registry/notes", json={})

    assert listed["user_client"] is True
    assert kept.status_code == 201, kept.text
    assert kept.json()["needs_own_app"] == "needs_client"
    assert kept.json()["check_failure"] == "sign_in"
    (plugin,) = (await client.get("/plugins")).json()
    assert plugin["source"] == "registry"


async def test_a_registry_naming_a_transport_still_lists(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """An older list may name SSE; the app speaks Streamable HTTP alone, and reads no transport."""
    registry.publish([entry("notes", transport="sse"), entry("keyed")])
    await allow_third_party(client)

    listed = (await client.get("/plugins/registry")).json()["plugins"]

    assert [p["id"] for p in listed] == ["notes", "keyed"]
    assert all("transport" not in p for p in listed)


@pytest.mark.third_party_off
async def test_nothing_connects_from_the_registry_while_third_party_plugins_are_off(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """Refused before any request leaves the machine."""
    registry.publish([entry("notes")])

    connected = await client.post("/plugins/registry/notes")

    assert connected.status_code == 403
    assert connected.json()["detail"]["code"] == "third_party_off"
    assert registry.requests == []


async def test_an_unlisted_or_connected_plugin_is_refused(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """A stale screen gets a clear answer, not a second copy."""
    registry.publish([entry("notes")])
    await allow_third_party(client)
    await client.post("/plugins/registry/notes")

    again = await client.post("/plugins/registry/notes")
    unlisted = await client.post("/plugins/registry/nope")

    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "plugin_already_connected"
    assert unlisted.status_code == 404


async def test_a_removed_plugin_keeps_its_connection_but_offers_no_tools(
    client: AsyncClient,
    registry: StandInRegistry,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Its row says why, so nothing is lost if it comes back."""
    refresh_every_time(monkeypatch)
    registry.publish([entry("notes")])
    await allow_third_party(client)
    await client.post("/plugins/registry/notes")
    with create_session_factory(engine)() as session:
        assert {tool.plugin_id for tool in list_tools(session)} == {"notes"}

    registry.publish(
        [],
        removed=[{"id": "notes", "reason": "The service shut down."}],
        generated_at="2026-10-11T12:00:00Z",
    )
    await client.get("/plugins/registry")

    plugins = (await client.get("/plugins")).json()
    assert [(p["id"], p["removed_reason"]) for p in plugins] == [
        ("notes", "The service shut down.")
    ]
    with create_session_factory(engine)() as session:
        assert list_tools(session) == []


async def test_a_custom_plugin_never_takes_a_registry_id(
    client: AsyncClient, registry: StandInRegistry
) -> None:
    """Listed or delisted, so a listed plugin can still connect under its own id."""
    registry.publish([entry("notes")], removed=[{"id": "wiki", "reason": "Gone."}])
    await allow_third_party(client)
    await client.get("/plugins/registry")

    with (
        serving(notes_server().streamable_http_app()) as first,
        serving(notes_server().streamable_http_app()) as second,
    ):
        notes = await client.post(
            "/plugins/custom", json={"url": f"{first}/mcp", "name": "Notes"}
        )
        wiki = await client.post(
            "/plugins/custom", json={"url": f"{second}/mcp", "name": "Wiki"}
        )

    assert (notes.json()["id"], wiki.json()["id"]) == ("notes-plugin", "wiki-plugin")


async def test_settings_network_lists_the_plugin_host_off_before_anything_asks(
    client: AsyncClient,
) -> None:
    """One switch there covers the registry and SurfSense's own plugins."""
    destinations = {
        row["destination"]: row for row in (await client.get("/egress")).json()
    }

    assert destinations["host:plugins.surfsense.com"]["enabled"] is False
