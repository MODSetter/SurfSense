"""Signing in with a ChatGPT account makes a connection that answers chat.

The test plays the browser: it opens the authorize URL the API hands back,
and the fake OpenAI redirects it to the API's loopback callback, as the real
one does once the person has agreed.
"""

import asyncio
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.llm.models import ProviderConnection
from modules.llm.providers.types import Message
from modules.llm.resolution import resolve_generation
from modules.llm.subscriptions.chatgpt.endpoints import get_endpoints
from shared.db import create_session_factory

from .fake_openai import EMAIL, ISSUED_CLIENT, FakeOpenAI

pytestmark = pytest.mark.integration


async def _browse(authorize_url: str) -> httpx.Response:
    async with httpx.AsyncClient(follow_redirects=True) as browser:
        return await browser.get(authorize_url)


async def _settled(client: AsyncClient, flow_id: str) -> dict:
    for _ in range(100):
        flow = (await client.get(f"/llm/connections/chatgpt/sign-in/{flow_id}")).json()
        if flow["status"] != "waiting":
            return flow
        await asyncio.sleep(0.05)
    raise AssertionError("the sign-in never settled")


async def _sign_in(client: AsyncClient, **body: object) -> dict:
    started = await client.post("/llm/connections/chatgpt/sign-in", json=body)
    assert started.status_code == 201, started.text
    await _browse(started.json()["authorize_url"])
    return await _settled(client, started.json()["flow_id"])


def _query(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


async def test_a_first_sign_in_registers_this_install_and_asks_for_plan_usage(
    client: AsyncClient, fake_openai: FakeOpenAI
) -> None:
    """OpenAI issues a client on first sign-in; the scopes ask for plan usage."""
    started = await client.post(
        "/llm/connections/chatgpt/sign-in", json={"label": "ChatGPT"}
    )

    asked = _query(started.json()["authorize_url"])
    assert asked["client_id"] == "dynamic_agent_client"
    assert asked["agent_name_hint"] == "SurfSense"
    assert asked["ext_agent_host_id"].startswith("urn:uuid:")
    assert "chatgpt.tokens.use.direct" in asked["scope"].split()
    assert asked["resource"] == "https://api.openai.com/v1"
    assert asked["code_challenge_method"] == "S256"
    redirect = urlsplit(asked["redirect_uri"])
    assert (redirect.scheme, redirect.hostname, redirect.path) == (
        "http",
        "127.0.0.1",
        "/callback",
    )


async def test_signing_in_makes_a_connection_that_lists_the_plans_models(
    client: AsyncClient, fake_openai: FakeOpenAI
) -> None:
    """The plan's list is the model list, and no token reaches the client."""
    flow = await _sign_in(client, label="ChatGPT")

    assert flow["status"] == "signed_in", flow
    listed = await client.get("/llm/connections")
    connection = listed.json()[0]
    assert connection["id"] == flow["connection_id"]
    assert (connection["auth_kind"], connection["signed_in"]) == ("chatgpt", True)
    assert connection["account_email"] == EMAIL
    assert "at-" not in listed.text and "rt-" not in listed.text
    models = (await client.get(f"/llm/connections/{connection['id']}/models")).json()
    assert [(m["name"], m["selectable_for"]) for m in models] == [
        ("gpt-5", ["text_gen"])
    ]


async def test_the_chosen_plan_model_answers_chat_through_responses(
    client: AsyncClient, fake_openai: FakeOpenAI
) -> None:
    """The chat check answers through /responses, not /chat/completions."""
    flow = await _sign_in(client, label="ChatGPT")
    choice = {
        "provider": "openai_compatible",
        "connection_id": flow["connection_id"],
        "name": "gpt-5",
    }

    chosen = await client.put("/llm/selection/text_gen", json=choice)
    tested = await client.post(
        f"/llm/connections/{flow['connection_id']}/chat-test", json={"model": "gpt-5"}
    )

    assert chosen.status_code == 200, chosen.text
    assert tested.json() == {"reply": "Hi"}
    assert fake_openai.answers[0]["model"] == "gpt-5"


async def test_a_plan_cannot_fill_a_slot_other_than_chat(
    client: AsyncClient, fake_openai: FakeOpenAI
) -> None:
    """Not even with the unlisted override: a plan only answers chat."""
    flow = await _sign_in(client, label="ChatGPT")
    choice = {
        "provider": "openai_compatible",
        "connection_id": flow["connection_id"],
        "name": "gpt-image-1",
        "allow_unlisted": True,
    }

    refused = await client.put("/llm/selection/image_gen", json=choice)

    assert refused.status_code == 422


async def test_a_callback_with_the_wrong_state_fails_the_sign_in(
    client: AsyncClient, fake_openai: FakeOpenAI
) -> None:
    """A forged redirect cannot finish someone else's sign-in."""
    started = (
        await client.post("/llm/connections/chatgpt/sign-in", json={"label": "ChatGPT"})
    ).json()
    redirect_uri = _query(started["authorize_url"])["redirect_uri"]

    async with httpx.AsyncClient() as browser:
        await browser.get(redirect_uri, params={"code": "x", "state": "forged"})
    flow = await _settled(client, started["flow_id"])

    assert flow["status"] == "failed"
    assert (await client.get("/llm/connections")).json() == []


async def test_signing_out_keeps_the_connection_and_signing_in_again_restores_it(
    client: AsyncClient, fake_openai: FakeOpenAI
) -> None:
    """The connection outlives a sign-out, so its selection does too."""
    first = await _sign_in(client, label="ChatGPT")
    connection_id = first["connection_id"]

    signed_out = await client.delete(f"/llm/connections/{connection_id}/sign-in")
    after = (await client.get("/llm/connections")).json()[0]
    again = await _sign_in(client, connection_id=connection_id)

    assert signed_out.status_code == 204
    assert after["signed_in"] is False
    assert again == {
        "status": "signed_in",
        "connection_id": connection_id,
        "message": None,
    }
    # Signing out dropped the issued client with the tokens, so this registers anew.
    assert fake_openai.authorized[-1]["client_id"] == "dynamic_agent_client"
    assert (await client.get("/llm/connections")).json()[0]["signed_in"] is True


async def test_signing_out_revokes_the_refresh_token_at_openai(
    client: AsyncClient, fake_openai: FakeOpenAI
) -> None:
    """Forgetting the tokens here is not enough: the grant must end at OpenAI too."""
    connection_id = (await _sign_in(client, label="ChatGPT"))["connection_id"]
    refresh_token = fake_openai.issued_refresh[-1]

    await client.delete(f"/llm/connections/{connection_id}/sign-in")

    assert fake_openai.revocations == [
        {
            "token": refresh_token,
            "token_type_hint": "refresh_token",
            "client_id": ISSUED_CLIENT,
        }
    ]


async def test_deleting_a_signed_in_connection_revokes_its_refresh_token(
    client: AsyncClient, fake_openai: FakeOpenAI
) -> None:
    """A delete signs out as well, so it ends the grant the same way."""
    connection_id = (await _sign_in(client, label="ChatGPT"))["connection_id"]
    refresh_token = fake_openai.issued_refresh[-1]

    deleted = await client.delete(f"/llm/connections/{connection_id}")

    assert deleted.status_code == 204
    assert [form["token"] for form in fake_openai.revocations] == [refresh_token]


async def test_a_failed_revocation_still_signs_out_here(
    client: AsyncClient, fake_openai: FakeOpenAI
) -> None:
    """The local sign-out is what the person asked for; OpenAI being down cannot undo it."""
    connection_id = (await _sign_in(client, label="ChatGPT"))["connection_id"]
    fake_openai.revocation_down = True

    signed_out = await client.delete(f"/llm/connections/{connection_id}/sign-in")

    assert signed_out.status_code == 204
    assert (await client.get("/llm/connections")).json()[0]["signed_in"] is False


async def test_a_malformed_sign_in_url_still_signs_out_here(
    client: AsyncClient, fake_openai: FakeOpenAI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A configured URL that does not parse costs the revocation, not the sign-out."""
    connection_id = (await _sign_in(client, label="ChatGPT"))["connection_id"]
    monkeypatch.setattr(get_endpoints(), "auth_url", "http://[::1")

    signed_out = await client.delete(f"/llm/connections/{connection_id}/sign-in")

    assert signed_out.status_code == 204
    assert (await client.get("/llm/connections")).json()[0]["signed_in"] is False
    assert fake_openai.revocations == []


def _scramble_tokens(engine: Engine, connection_id: int) -> None:
    """Tokens this install can no longer open, as after a keychain reset."""
    with create_session_factory(engine)() as session:
        session.get(ProviderConnection, connection_id).oauth_ciphertext = b"lost-key"
        session.commit()


async def test_tokens_that_cannot_be_decrypted_still_sign_out_and_delete(
    client: AsyncClient, engine: Engine, fake_openai: FakeOpenAI
) -> None:
    """Signing out and deleting are the ways out of a lost key, so neither can need it."""
    connection_id = (await _sign_in(client, label="ChatGPT"))["connection_id"]

    _scramble_tokens(engine, connection_id)
    signed_out = await client.delete(f"/llm/connections/{connection_id}/sign-in")
    _scramble_tokens(engine, connection_id)
    deleted = await client.delete(f"/llm/connections/{connection_id}")

    assert signed_out.status_code == 204
    assert deleted.status_code == 204
    assert fake_openai.revocations == []


async def test_a_sign_in_host_turned_off_is_not_called_to_sign_out(
    client: AsyncClient,
    fake_openai: FakeOpenAI,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The person's off switch holds even for a revocation."""
    connection_id = (await _sign_in(client, label="ChatGPT"))["connection_id"]
    monkeypatch.setattr(get_endpoints(), "auth_url", "https://auth.example")

    signed_out = await client.delete(f"/llm/connections/{connection_id}/sign-in")

    assert signed_out.status_code == 204
    assert (await client.get("/llm/connections")).json()[0]["signed_in"] is False
    assert "Could not revoke" not in caplog.text


async def test_a_label_already_taken_is_refused_before_the_browser_opens(
    client: AsyncClient, fake_openai: FakeOpenAI
) -> None:
    """Refused up front, not after the person has signed in."""
    await _sign_in(client, label="ChatGPT")

    again = await client.post(
        "/llm/connections/chatgpt/sign-in", json={"label": "chatgpt"}
    )

    assert again.status_code == 409


async def test_chat_titles_and_studio_reach_the_plan_through_the_selection(
    client: AsyncClient, engine: Engine, fake_openai: FakeOpenAI
) -> None:
    """Every caller of resolve_generation gets the Responses generator."""
    flow = await _sign_in(client, label="ChatGPT")
    await client.put(
        "/llm/selection/text_gen",
        json={
            "provider": "openai_compatible",
            "connection_id": flow["connection_id"],
            "name": "gpt-5",
        },
    )

    with create_session_factory(engine)() as session:
        resolved = resolve_generation(session)
    reply = "".join(
        [c async for c in resolved.generator.chat("gpt-5", [Message("user", "hi")])]
    )

    assert reply == "Hi"


async def test_the_sign_in_says_what_it_serves_and_names_hosts_until_allowed(
    client: AsyncClient, fake_openai: FakeOpenAI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asked up front, one host at a time, so a declined host is never asked twice."""
    endpoints = get_endpoints()
    monkeypatch.setattr(endpoints, "auth_url", "https://auth.example")
    monkeypatch.setattr(endpoints, "api_url", "https://api.example/v1")

    before = (await client.get("/llm/connections/chatgpt")).json()
    await client.put("/egress/host:auth.example", json={"enabled": True})
    after = (await client.get("/llm/connections/chatgpt")).json()

    assert before == {
        "serves": ["text_gen"],
        "hosts": [
            {"destination": "host:auth.example", "host": "auth.example"},
            {"destination": "host:api.example", "host": "api.example"},
        ],
    }
    assert after["hosts"] == [
        {"destination": "host:api.example", "host": "api.example"}
    ]


async def test_each_connection_says_which_model_types_it_can_fill(
    client: AsyncClient, fake_openai: FakeOpenAI, openai_server: str
) -> None:
    """Decided once, here: the pickers read it and never decide it themselves."""
    await _sign_in(client, label="ChatGPT")
    keyed = await client.post(
        "/llm/connections",
        json={"label": "Gateway", "base_url": openai_server, "api_key": "secret"},
    )
    assert keyed.status_code == 201, keyed.text

    serves = {
        c["label"]: c["serves"] for c in (await client.get("/llm/connections")).json()
    }

    assert serves == {
        "ChatGPT": ["text_gen"],
        "Gateway": ["text_gen", "image_gen", "image_edit", "video_gen", "audio_gen"],
    }
