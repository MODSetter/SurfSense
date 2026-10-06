"""The model endpoint's /responses relay, for a model that answers only there.

A ChatGPT plan is reached with its own token, refreshed once when refused; its
refusals keep the chat's kinds so the agent's screen offers the same fix.
"""

import json
import time

import pytest
from sqlalchemy.orm import Session, sessionmaker

from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from modules.llm.subscriptions.chatgpt.token_set import TokenSet
from modules.llm.subscriptions.chatgpt.tokens import write_tokens
from tests.integration.llm.chatgpt.fake_openai import ISSUED_CLIENT, FakeOpenAI

from .conftest import Endpoint, StubModel, select_remote

pytestmark = pytest.mark.integration

ROUTE = "/agent/model/v1/responses"


def select_plan(
    sessions: sessionmaker[Session], base_url: str, access: str, refresh: str
) -> None:
    """Choose a model of a signed-in ChatGPT plan."""
    with sessions() as session:
        connection = ProviderConnection(
            label="ChatGPT",
            provider="openai_compatible",
            base_url=base_url,
            catalog_provider="openai",
            auth_kind="chatgpt",
        )
        write_tokens(
            connection,
            TokenSet(
                client_id=ISSUED_CLIENT,
                access_token=access,
                refresh_token=refresh,
                id_token="id",
                expires_at=time.time() + 3600,
                account="acct",
            ),
        )
        session.add(connection)
        session.flush()
        session.add(
            SelectedModel(
                model_type=ModelType.TEXT_GEN,
                provider="openai_compatible",
                connection_id=connection.id,
                name="gpt-5",
            )
        )
        session.commit()


async def responses(endpoint: Endpoint, body: dict) -> tuple[int, str]:
    """Send one step as opencode's OpenAI provider does; the reply's status and text."""
    headers = {"Authorization": f"Bearer {endpoint.launch_key}"}
    reply = await endpoint.client.post(ROUTE, json=body, headers=headers)
    return reply.status_code, reply.text


def request(**extra: object) -> dict:
    """A step as opencode's own OpenAI provider sends it."""
    return {
        "model": "surfsense",
        "stream": True,
        "store": False,
        "input": [
            {"role": "system", "content": "You work on the user's sources."},
            {"role": "user", "content": [{"type": "input_text", "text": "Hi"}]},
        ],
        "tools": [
            {"type": "function", "name": "glob", "parameters": {"type": "object"}}
        ],
        "max_output_tokens": 32000,
        "temperature": 0.2,
        **extra,
    }


async def test_a_request_without_the_launch_key_is_refused(endpoint: Endpoint) -> None:
    """Only the opencode SurfSense started may spend a connection's key or plan."""
    reply = await endpoint.client.post(ROUTE, json=request())

    assert reply.status_code == 401


async def test_a_model_on_chat_completions_is_not_answered_here(
    endpoint: Endpoint, model_server: StubModel
) -> None:
    """opencode was configured for the other route; this one says so instead of guessing."""
    select_remote(endpoint.sessions, f"{model_server.url}/v1", api_key="remote-key")

    status, _ = await responses(endpoint, request())

    assert status == 409
    assert model_server.requests == []


async def test_a_plan_is_not_answered_on_chat_completions(
    endpoint: Endpoint,
    fake_openai: FakeOpenAI,
) -> None:
    """Its connection holds no key, so that route could only fail upstream."""
    select_plan(endpoint.sessions, f"{fake_openai.url}/v1", "at-live", "rt-1")

    status, _ = await endpoint.chat(
        {"model": "x", "stream": True, "messages": [{"role": "user", "content": "Hi"}]}
    )

    assert status == 409
    assert fake_openai.answers == []


async def test_a_plan_gets_its_token_and_only_what_it_takes(
    endpoint: Endpoint,
    fake_openai: FakeOpenAI,
) -> None:
    """Refused fields go, tools travel in one namespace, the system turn as the developer's."""
    fake_openai.live_access.add("at-live")
    select_plan(endpoint.sessions, f"{fake_openai.url}/v1", "at-live", "rt-1")

    status, text = await responses(endpoint, request())

    assert status == 200, text
    assert "response.completed" in text
    [sent] = fake_openai.answers
    assert sent["model"] == "gpt-5"
    assert not {"max_output_tokens", "temperature"} & sent.keys()
    assert (sent["store"], sent["stream"]) == (False, True)
    assert [item.get("role") for item in sent["input"]] == ["developer", "user"]
    [namespace] = sent["tools"]
    assert namespace["type"] == "namespace"
    assert [tool["name"] for tool in namespace["tools"]] == ["glob"]


async def test_a_refused_plan_token_is_refreshed_once_and_the_step_repeated(
    endpoint: Endpoint,
    fake_openai: FakeOpenAI,
) -> None:
    """The stored token can lapse between reads, as for the chat."""
    select_plan(endpoint.sessions, f"{fake_openai.url}/v1", "at-stale", "rt-1")

    status, _ = await responses(endpoint, request())

    assert status == 200
    assert fake_openai.refreshes == 1


async def test_a_plan_that_must_sign_in_again_says_so_in_the_chats_kind(
    endpoint: Endpoint,
    fake_openai: FakeOpenAI,
) -> None:
    """A refresh token OpenAI no longer takes: only signing in fixes it, so no retry."""
    fake_openai.revoked_refresh.add("rt-1")
    select_plan(endpoint.sessions, f"{fake_openai.url}/v1", "at-stale", "rt-1")

    status, text = await responses(endpoint, request())

    assert status == 401
    assert json.loads(text)["error"]["code"] == "subscription_sign_in"


async def test_a_used_up_plan_says_so_in_a_status_opencode_does_not_retry(
    endpoint: Endpoint,
    fake_openai: FakeOpenAI,
) -> None:
    """A 429 would have opencode retry a limit that resets on the plan's own schedule."""
    fake_openai.live_access.add("at-live")
    fake_openai.limit_reached = True
    select_plan(endpoint.sessions, f"{fake_openai.url}/v1", "at-live", "rt-1")

    status, text = await responses(endpoint, request())

    assert status == 403
    assert json.loads(text)["error"]["code"] == "subscription_limit"


def select_responses_model(sessions: sessionmaker[Session], base_url: str) -> None:
    """Choose Sakana's fugu, which the manifest records as served only on /responses."""
    with sessions() as session:
        connection = ProviderConnection(
            label="Sakana",
            provider="openai_compatible",
            base_url=base_url,
            catalog_provider="sakana",
        )
        connection.api_key = "sakana-key"
        session.add(connection)
        session.flush()
        session.add(
            SelectedModel(
                model_type=ModelType.TEXT_GEN,
                provider="openai_compatible",
                connection_id=connection.id,
                name="fugu",
            )
        )
        session.commit()


def _events(text: str) -> list[dict]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in text.splitlines()
        if line.startswith("data: ")
    ]


async def test_a_reply_cut_off_before_it_ends_reaches_opencode_as_a_failure(
    endpoint: Endpoint, model_server: StubModel
) -> None:
    """opencode's provider takes a stream that just stops as a finished step,
    so the relay says it broke, as the chat does for the same reply."""
    model_server.frames = [
        json.dumps({"type": "response.output_text.delta", "delta": "Half"})
    ]
    select_responses_model(endpoint.sessions, f"{model_server.url}/v1")

    status, text = await responses(endpoint, request())

    assert status == 200
    assert _events(text)[-1]["type"] == "error"


async def test_a_reply_that_ends_is_passed_on_with_nothing_added(
    endpoint: Endpoint, model_server: StubModel
) -> None:
    """A stream that reaches its own terminal event is the model's, unchanged."""
    completed = {"type": "response.completed", "response": {"status": "completed"}}
    model_server.frames = [
        json.dumps({"type": "response.output_text.delta", "delta": "Whole"}),
        json.dumps(completed),
    ]
    select_responses_model(endpoint.sessions, f"{model_server.url}/v1")

    status, text = await responses(endpoint, request())

    assert status == 200
    assert [event["type"] for event in _events(text)] == [
        "response.output_text.delta",
        "response.completed",
    ]
