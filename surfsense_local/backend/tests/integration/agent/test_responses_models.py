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
from tests.integration.worker.conftest import stub_model  # noqa: F401

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


# Every tool this branch adds, as opencode names SurfSense's tools.
FILE_TOOLS = (
    "surfsense_source_pages",
    "surfsense_convert_document",
    "surfsense_revise_document",
    "surfsense_analyze_data",
    "surfsense_pdf_pages",
    "surfsense_pdf_stamp",
    "surfsense_pdf_form",
)
SKILLS = (
    "surfsense-documents",
    "surfsense-revisions",
    "surfsense-data",
    "surfsense-pdf",
)
ONE_PAGE_PDF = """\
import os
from reportlab.pdfgen import canvas

page = canvas.Canvas(os.environ["OUTPUT_PATH"])
page.drawString(72, 720, "Client proposal")
page.save()
"""


@pytest.mark.usefixtures("stub_model", "studio_worker")
async def test_on_a_plan_the_agent_keeps_its_file_tools_and_sees_the_pages_it_makes(
    agent_api: AgentAPI,
) -> None:
    """A plan's model reads images, so its tools, skills and page previews all
    reach it: opencode's OpenAI provider puts a tool's images in the call's
    output, and the relay passes that output on as it came."""
    _select("gpt-5.5", auth_kind="chatgpt", catalog_provider="openai")
    render = {
        "name": "surfsense_render_document",
        "arguments": {
            "title": "Client proposal",
            "format": "pdf",
            "script": ONE_PAGE_PDF,
        },
    }
    agent_api.model.replies = [("call", json.dumps(render)), ("text", "Made it.")]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "Draft the proposal as a PDF")

    assert of_type(frames, "completed")[0]["text"] == "Made it."
    offered, answered = agent_api.model.requests[:2]
    [namespace] = offered["tools"]
    names = [tool["name"] for tool in namespace["tools"]]
    for tool in (*FILE_TOOLS, "skill"):
        assert tool in names, tool
    for skill in SKILLS:
        assert f"<name>{skill}</name>" in json.dumps(offered["input"]), skill
    [output] = [
        item for item in answered["input"] if item.get("type") == "function_call_output"
    ]
    parts = output["output"]
    assert isinstance(parts, list), output
    assert "Rendered artifact" in json.dumps(parts)
    images = [part for part in parts if part.get("type") == "input_image"]
    assert images, parts
    assert all(part["image_url"].startswith("data:image/") for part in images)


@pytest.mark.usefixtures("stub_model", "studio_worker")
async def test_on_a_plan_model_not_known_to_read_images_the_agent_is_told_why_none_come(
    agent_api: AgentAPI,
) -> None:
    """A plan model the catalog does not record is shown no images: the page
    tool is not offered and a made PDF's result says its previews were left out."""
    _select(
        "plan-model-not-in-the-catalog", auth_kind="chatgpt", catalog_provider="openai"
    )
    render = {
        "name": "surfsense_render_document",
        "arguments": {
            "title": "Client proposal",
            "format": "pdf",
            "script": ONE_PAGE_PDF,
        },
    }
    agent_api.model.replies = [("call", json.dumps(render)), ("text", "Made it.")]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "Draft the proposal as a PDF")

    assert of_type(frames, "completed")[0]["text"] == "Made it."
    offered, answered = agent_api.model.requests[:2]
    [namespace] = offered["tools"]
    names = [tool["name"] for tool in namespace["tools"]]
    assert "surfsense_source_pages" not in names
    for tool in FILE_TOOLS[1:]:
        assert tool in names, tool
    [output] = [
        item for item in answered["input"] if item.get("type") == "function_call_output"
    ]
    told = json.dumps(output["output"])
    assert "Rendered artifact" in told
    assert "No page previews: the selected model cannot read images." in told
    assert "input_image" not in told


async def test_a_plan_reply_cut_off_is_retried_and_the_thread_settles_on_the_retry(
    agent_api: AgentAPI,
) -> None:
    """The relay tells opencode a stream that stopped early broke, so opencode
    tries the step again rather than keeping half a reply: the turn completes
    on the retried answer, as stored, and the breaks the cut-off words ended
    on are never streamed.

    The cut-off words themselves were streamed before the retry, and no frame
    takes them back; only `completed` replaces the shown text.
    """
    _select("gpt-5.5", auth_kind="chatgpt", catalog_provider="openai")
    agent_api.model.replies = [("cut-off", "Half done.\n\n"), ("text", "Whole.")]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "Summarise my sources")
    stored = await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")

    assert len(agent_api.model.requests) == 2
    assert not of_type(frames, "error")
    # The cut-off part's own breaks were held, never streamed.
    assert of_type(frames, "delta")[0]["text"] == "Half done."
    [completed] = of_type(frames, "completed")
    reply = stored.json()[-1]["content"]
    assert completed["text"] == reply["text"] == "Whole."
    assert "ending" not in reply
