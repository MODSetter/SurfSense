"""Signing in with the user's own OAuth app, and signing in again for more access."""

import logging
from collections.abc import Iterator
from urllib.parse import parse_qs, urlsplit

import pytest
from httpx import AsyncClient

from tests.integration.plugins.routes.test_oauth_sign_in import (
    SignInServers,
    approve_in_browser,
)
from tests.mcp_test_server import notes_server, serving
from tests.oauth_stand_in import ProtectedByStandIn, StandInAuthorizationServer

pytestmark = pytest.mark.integration

OWN_APP = {"client_id": "own-1", "client_secret": "s-own-1"}


@pytest.fixture
def registered_only() -> Iterator[SignInServers]:
    """A provider with no dynamic registration, which knows the user's app `own-1`."""
    authorization = StandInAuthorizationServer(
        registration=False, secret_clients={"own-1": "s-own-1"}
    )
    with serving(authorization.app()) as issuer:
        authorization.issuer = issuer
        protected = ProtectedByStandIn(
            notes_server().streamable_http_app(), authorization
        )
        with serving(protected) as base:
            yield SignInServers(authorization, protected, f"{base}/mcp")


@pytest.fixture
def servers() -> Iterator[SignInServers]:
    """A provider with dynamic registration, protecting the notes server."""
    authorization = StandInAuthorizationServer()
    with serving(authorization.app()) as issuer:
        authorization.issuer = issuer
        protected = ProtectedByStandIn(
            notes_server().streamable_http_app(), authorization
        )
        with serving(protected) as base:
            yield SignInServers(authorization, protected, f"{base}/mcp")


async def _signed_in(client: AsyncClient, url: str, **write) -> dict:
    """Added, then Connect on its row, with the user's own app when one is given."""
    added = await client.post("/plugins/custom", json={"url": url, "name": "Notes"})
    assert added.status_code == 201, added.text
    started = await client.post("/plugins/notes/sign-in", json=write or None)
    assert started.status_code == 202, started.text
    page = await approve_in_browser(client, started.json()["authorization_url"])
    assert "Signed in to Notes" in page.text, page.text
    return started.json()


async def test_a_server_registering_no_app_is_kept_needing_the_users_own(
    client: AsyncClient, registered_only: SignInServers
) -> None:
    """Saved before any browser opens, as Needs an OAuth app, to set up from its row."""
    added = await client.post(
        "/plugins/custom", json={"url": registered_only.mcp_url, "name": "Notes"}
    )

    assert added.status_code == 201, added.text
    assert added.json()["needs_own_app"] == "needs_client"
    assert added.json()["check_failure"] == "sign_in"
    assert added.json()["tools"] == []
    # Its metadata names no registration, so none is tried: no request is sent only to fail.
    assert registered_only.authorization.registration_attempts == 0
    assert not [p for p in registered_only.protected.paths if p.endswith("/register")]
    (listed,) = (await client.get("/plugins")).json()
    assert listed["needs_own_app"] == "needs_client"


async def test_sign_in_on_a_plugin_needing_the_users_own_app_says_so(
    client: AsyncClient, registered_only: SignInServers
) -> None:
    """With the callback to register one; the plugin stays as it was."""
    await client.post(
        "/plugins/custom", json={"url": registered_only.mcp_url, "name": "Notes"}
    )

    refused = await client.post("/plugins/notes/sign-in")

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "plugin_oauth_needs_client"
    # The address to register the app with, which is the API's own in a developer's build.
    assert refused.json()["detail"]["redirect_uri"] == (
        "http://127.0.0.1:8000/plugins/oauth/callback"
    )
    (listed,) = (await client.get("/plugins")).json()
    assert listed["needs_own_app"] == "needs_client"


async def test_signing_in_with_the_users_own_app_clears_the_need(
    client: AsyncClient, registered_only: SignInServers
) -> None:
    """It is no longer marked, and offers to change the app rather than set one up."""
    await client.post(
        "/plugins/custom", json={"url": registered_only.mcp_url, "name": "Notes"}
    )

    started = await client.post(
        "/plugins/notes/sign-in", json={"oauth_client": OWN_APP}
    )
    await approve_in_browser(client, started.json()["authorization_url"])

    (listed,) = (await client.get("/plugins")).json()
    assert listed["needs_own_app"] is None
    assert listed["own_app"] is True
    assert listed["check_failure"] is None


async def test_the_users_own_app_signs_in_with_its_secret_and_keeps_it(
    client: AsyncClient, registered_only: SignInServers
) -> None:
    """No registration; the secret goes to the token endpoint only, never back out."""
    sign_in = await _signed_in(client, registered_only.mcp_url, oauth_client=OWN_APP)

    query = parse_qs(urlsplit(sign_in["authorization_url"]).query)
    assert query["client_id"] == ["own-1"]
    assert registered_only.authorization.registered == []
    exchange = registered_only.authorization.token_requests[-1]
    assert exchange["client_secret"] == "s-own-1"
    listed = await client.get("/plugins")
    assert listed.json()[0]["auth_type"] == "oauth"
    assert listed.json()[0]["check_failure"] is None
    assert "s-own-1" not in listed.text
    assert "s-own-1" not in str(sign_in)


async def test_the_users_own_app_refreshes_with_its_secret(
    client: AsyncClient, registered_only: SignInServers
) -> None:
    """An expired token is refreshed as the same app, its secret sent again."""
    await _signed_in(client, registered_only.mcp_url, oauth_client=OWN_APP)
    registered_only.authorization.expire_access_tokens()

    checked = await client.post("/plugins/notes/check")

    assert checked.json()["check_failure"] is None
    refresh = registered_only.authorization.token_requests[-1]
    assert refresh["grant_type"] == "refresh_token"
    assert refresh["client_secret"] == "s-own-1"


async def test_signing_in_again_reuses_the_users_own_app(
    client: AsyncClient, registered_only: SignInServers
) -> None:
    """The app and its secret stay with the plugin for Sign in again."""
    await _signed_in(client, registered_only.mcp_url, oauth_client=OWN_APP)

    again = await client.post("/plugins/notes/sign-in")

    assert again.status_code == 202, again.text
    query = parse_qs(urlsplit(again.json()["authorization_url"]).query)
    assert query["client_id"] == ["own-1"]


async def test_a_server_asking_for_more_access_is_signed_in_again_with_it(
    client: AsyncClient, servers: SignInServers
) -> None:
    """403 `insufficient_scope` at a check: Needs more access, then a sign-in asking for it."""
    await _signed_in(client, servers.mcp_url)
    servers.protected.required_scope = "notes:write"

    checked = await client.post("/plugins/notes/check")
    assert checked.json()["check_failure"] == "sign_in"
    assert checked.json()["needs_scopes"] == ["notes:write"]

    again = await client.post("/plugins/notes/sign-in")
    query = parse_qs(urlsplit(again.json()["authorization_url"]).query)
    assert "notes:write" in query["scope"][0].split()
    await approve_in_browser(client, again.json()["authorization_url"])

    listed = (await client.get("/plugins")).json()[0]
    assert listed["check_failure"] is None
    assert listed["needs_scopes"] == []


async def test_the_callback_to_register_an_app_with_is_given(
    client: AsyncClient,
) -> None:
    """The one this build signs in with: the API's own in a developer's build."""
    answered = await client.get("/plugins/oauth/redirect-uri")

    assert answered.status_code == 200
    assert answered.json() == {
        "redirect_uri": "http://127.0.0.1:8000/plugins/oauth/callback"
    }


async def test_a_provider_registering_only_clients_with_a_secret_issues_one(
    client: AsyncClient,
) -> None:
    """Asked again for a secret of this install's own, which signs in and refreshes."""
    authorization = StandInAuthorizationServer(public_registration=False)
    with serving(authorization.app()) as issuer:
        authorization.issuer = issuer
        protected = ProtectedByStandIn(
            notes_server().streamable_http_app(), authorization
        )
        with serving(protected) as base:
            await _signed_in(client, f"{base}/mcp")
            authorization.expire_access_tokens()
            checked = await client.post("/plugins/notes/check")

    methods = [r["token_endpoint_auth_method"] for r in authorization.registered]
    assert methods == ["none", "client_secret_post"]
    assert authorization.token_requests[0]["client_secret"] == "secret-2"
    assert checked.json()["check_failure"] is None
    assert "secret-2" not in (await client.get("/plugins")).text


async def test_a_provider_refusing_to_register_surfsense_says_so(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Found at Connect, as only registering tells; told apart from a provider with no
    registration at all, and kept to set up."""
    caplog.set_level(logging.INFO)
    authorization = StandInAuthorizationServer(refuse_registration=True)
    with serving(authorization.app()) as issuer:
        authorization.issuer = issuer
        protected = ProtectedByStandIn(
            notes_server().streamable_http_app(), authorization
        )
        with serving(protected) as base:
            added = await client.post(
                "/plugins/custom", json={"url": f"{base}/mcp", "name": "Notes"}
            )
            refused = await client.post("/plugins/notes/sign-in")

    assert added.json()["needs_own_app"] is None
    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "plugin_oauth_refused"
    (plugin,) = (await client.get("/plugins")).json()
    assert plugin["needs_own_app"] == "refused"
    # An answer SurfSense handles: one line saying so, never the SDK's traceback.
    assert not [r for r in caplog.records if r.exc_info]
    assert "refused to register SurfSense" in caplog.text


async def test_the_list_says_which_plugins_sign_in_with_the_users_own_app(
    client: AsyncClient,
    registered_only: SignInServers,
    servers: SignInServers,
) -> None:
    """Only those offer to change it; one SurfSense registered itself offers nothing."""
    await _signed_in(client, registered_only.mcp_url, oauth_client=OWN_APP)
    await client.post("/plugins/custom", json={"url": servers.mcp_url, "name": "Wiki"})
    started = await client.post("/plugins/wiki/sign-in")
    await approve_in_browser(client, started.json()["authorization_url"])

    listed = {p["id"]: p["own_app"] for p in (await client.get("/plugins")).json()}

    assert listed == {"notes": True, "wiki": False}
