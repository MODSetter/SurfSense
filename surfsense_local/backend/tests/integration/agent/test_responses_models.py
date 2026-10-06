"""The agent on a model that answers on /responses: an API key's, or a ChatGPT plan's.

opencode reaches either through SurfSense's own /responses relay, which adds
the connection's credential; for a plan it also keeps the request within what
the plan takes.
"""

import json
import time

import pytest

from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from modules.llm.subscriptions.chatgpt.token_set import TokenSet
from modules.llm.subscriptions.chatgpt.tokens import write_tokens
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory
from tests.integration.agent.conftest import AgentAPI
from tests.integration.agent.test_agent_threads import of_type, open_thread, send

pytestmark = pytest.mark.integration

GLOB = {"name": "glob", "arguments": {"pattern": "sources/*.md"}}
PLAN_REFUSES = {"max_output_tokens", "temperature", "top_p", "truncation", "user"}


def _select(name: str, **connection_fields: object) -> None:
    """Point the agent API's one remote connection at another kind of model."""
    with create_session_factory(
        create_db_engine(get_storage_settings().database_path)
    )() as session:
        selected = session.get(SelectedModel, ModelType.TEXT_GEN)
        assert selected is not None
        connection = session.get(ProviderConnection, selected.connection_id)
        assert connection is not None
        for field, value in connection_fields.items():
            setattr(connection, field, value)
        if connection.auth_kind == "chatgpt":
            connection.api_key = None
            write_tokens(
                connection,
                TokenSet(
                    client_id="app_issued_1",
                    access_token="plan-access",
                    refresh_token="rt-1",
                    id_token="id-1",
                    expires_at=time.time() + 3600,
                    account="acct",
                ),
            )
        selected.name = name
        session.commit()


async def test_an_api_keys_responses_model_runs_the_agent_with_its_key(
    agent_api: AgentAPI,
) -> None:
    """Sakana serves fugu only on /responses: opencode is pointed there, under the key."""
    _select("fugu", catalog_provider="sakana")
    agent_api.model.replies = [("call", json.dumps(GLOB)), ("text", "Listed.")]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "What do I have?")

    assert of_type(frames, "completed")[0]["text"] == "Listed."
    assert set(agent_api.model.paths) == {"/v1/responses"}
    assert set(agent_api.model.bearers) == {"Bearer remote-key"}
    offered = agent_api.model.requests[0]["tools"]
    assert "glob" in [tool.get("name") for tool in offered]


async def test_a_chatgpt_plan_runs_the_agent_within_what_the_plan_takes(
    agent_api: AgentAPI,
) -> None:
    """The plan's token, tools in one namespace, no refused field, no system item."""
    _select("gpt-5.6-sol", auth_kind="chatgpt", catalog_provider="openai")
    agent_api.model.replies = [("call", json.dumps(GLOB)), ("text", "Listed.")]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "What do I have?")

    assert of_type(frames, "completed")[0]["text"] == "Listed."
    assert set(agent_api.model.paths) == {"/v1/responses"}
    assert set(agent_api.model.bearers) == {"Bearer plan-access"}
    offered, answered = agent_api.model.requests[:2]
    for request in (offered, answered):
        assert not PLAN_REFUSES & request.keys()
        assert (request["store"], request["stream"]) == (False, True)
        assert "system" not in [item.get("role") for item in request["input"]]
    [namespace] = offered["tools"]
    assert namespace["type"] == "namespace"
    assert "glob" in [tool["name"] for tool in namespace["tools"]]
    replayed = [i for i in answered["input"] if i.get("type") == "function_call"]
    assert [(i["name"], i.get("namespace")) for i in replayed] == [
        ("glob", namespace["name"])
    ]
