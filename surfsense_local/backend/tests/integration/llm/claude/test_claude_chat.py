"""A Claude plan model answers the app's chat, its chat check, and every resolver."""

import json
import threading

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.llm.resolution import resolve_generation
from modules.llm.subscriptions.claude import plan_generator
from modules.llm.subscriptions.claude.chat import ClaudePlanProvider
from modules.llm.subscriptions.claude.proxy import serving_claude_proxy
from shared.db import create_session_factory
from tests.claude_run_stand_in import RESETS_AT, answer, plan_limits
from tests.claude_stand_in import SIGNED_OUT

from .conftest import ClaudeOnThisMachine, FakeClaude

pytestmark = pytest.mark.integration
SONNET = "claude-sonnet-5-5"


async def _choose_claude(client: AsyncClient, claude_on_this_machine) -> int:
    claude_on_this_machine()
    for host in ("api.anthropic.com", "platform.claude.com"):
        await client.put(
            "/egress", json={"destinations": [f"host:{host}"], "enabled": True}
        )
    connection = (
        await client.post("/llm/connections/claude", json={"label": "Claude"})
    ).json()
    chosen = await client.put(
        "/llm/selection/text_gen",
        json={
            "provider": "openai_compatible",
            "connection_id": connection["id"],
            "name": SONNET,
        },
    )
    assert chosen.status_code == 200, chosen.text
    return connection["id"]


async def _send(client: AsyncClient, thread_id: int, text: str) -> list[dict]:
    frames: list[dict] = []
    async with client.stream(
        "POST", f"/chat/threads/{thread_id}/messages", json={"text": text}
    ) as reply:
        assert reply.status_code == 200
        async for line in reply.aiter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                frames.append(json.loads(line[len("data: ") :]))
    return frames


async def _basic_thread(client: AsyncClient) -> int:
    workspace = (await client.post("/workspaces", json={"name": "w"})).json()
    reply = await client.post(
        f"/workspaces/{workspace['id']}/chat/threads", json={"mode": "basic"}
    )
    assert reply.status_code in (200, 201), reply.text
    return reply.json()["id"]


async def test_a_claude_plan_model_is_the_chat_models_generator(
    client: AsyncClient,
    engine: Engine,
    claude_on_this_machine: ClaudeOnThisMachine,
    fake_claude: FakeClaude,
) -> None:
    """Resolution hands chat, titles and Studio the Claude plan's own generator."""
    await _choose_claude(client, claude_on_this_machine)

    with create_session_factory(engine)() as session:
        resolved = resolve_generation(session)

    assert isinstance(resolved.generator, ClaudePlanProvider)
    assert resolved.selection.name == SONNET


async def test_a_claude_plan_model_cannot_fill_another_slot(
    client: AsyncClient,
    claude_on_this_machine: ClaudeOnThisMachine,
    fake_claude: FakeClaude,
) -> None:
    """Claude Code answers text only, whatever model is named."""
    connection_id = await _choose_claude(client, claude_on_this_machine)

    refused = await client.put(
        "/llm/selection/image_gen",
        json={
            "provider": "openai_compatible",
            "connection_id": connection_id,
            "name": SONNET,
            "allow_unlisted": True,
        },
    )

    assert refused.status_code == 422


async def test_the_chat_check_answers_through_claude_code(
    client: AsyncClient,
    claude_on_this_machine: ClaudeOnThisMachine,
    fake_claude: FakeClaude,
) -> None:
    """Trying a model before choosing it runs it the way chat will."""
    connection_id = await _choose_claude(client, claude_on_this_machine)
    fake_claude.replies.append(answer("Hi there."))

    tested = await client.post(
        f"/llm/connections/{connection_id}/chat-test", json={"model": SONNET}
    )

    assert tested.status_code == 200, tested.text
    assert tested.json()["reply"] == "Hi there."


@pytest.mark.usefixtures("real_model")
async def test_a_basic_chat_streams_claudes_answer(
    client: AsyncClient,
    claude_on_this_machine: ClaudeOnThisMachine,
    fake_claude: FakeClaude,
) -> None:
    """The answer arrives as deltas and is stored as the reply."""
    await _choose_claude(client, claude_on_this_machine)
    fake_claude.replies.append(answer("Paris is ", "the capital."))
    thread_id = await _basic_thread(client)

    frames = await _send(client, thread_id, "What is the capital of France?")

    streamed = "".join(f["text"] for f in frames if f.get("type") == "delta")
    assert streamed == "Paris is the capital."
    assert all(run.options.tools == [] for run in fake_claude.opened)
    stored = (await client.get(f"/chat/threads/{thread_id}/messages")).json()
    assert stored[-1]["content"]["text"] == "Paris is the capital."
    titled = [f for f in frames if f.get("type") == "thread-title-update"]
    assert titled and titled[0]["title"] == "A title"


@pytest.mark.usefixtures("real_model")
async def test_a_signed_out_claude_code_shows_the_sign_in_notice(
    client: AsyncClient,
    claude_on_this_machine: ClaudeOnThisMachine,
    fake_claude: FakeClaude,
) -> None:
    """Signed out after connecting: the chat offers the plan's own fix."""
    from claude_agent_sdk import AssistantMessage, TextBlock

    from tests.claude_run_stand_in import done

    await _choose_claude(client, claude_on_this_machine)
    signed_out = AssistantMessage(
        content=[TextBlock("Not logged in")], model="x", error="authentication_failed"
    )
    fake_claude.replies.append([signed_out, done(is_error=True)])
    claude_on_this_machine(auth=SIGNED_OUT)
    thread_id = await _basic_thread(client)

    frames = await _send(client, thread_id, "Hi")

    errors = [f for f in frames if f.get("type") == "error"]
    assert errors and errors[0]["kind"] == "claude_sign_in"


@pytest.mark.usefixtures("real_model")
async def test_closing_the_api_closes_every_warm_run(
    client: AsyncClient,
    claude_on_this_machine: ClaudeOnThisMachine,
    fake_claude: FakeClaude,
) -> None:
    """No Claude Code process outlives the API."""
    await _choose_claude(client, claude_on_this_machine)
    fake_claude.replies.append(answer("ok"))
    await _send(client, await _basic_thread(client), "Hi")

    await plan_generator.close_claude_runs()

    assert all(run.closed for run in fake_claude.opened)


@pytest.mark.usefixtures("real_model")
async def test_every_claude_code_run_goes_through_the_proxy(
    client: AsyncClient,
    engine: Engine,
    claude_on_this_machine: ClaudeOnThisMachine,
    fake_claude: FakeClaude,
) -> None:
    """The model list and the chat alike, so egress consent holds for Claude Code."""
    async with serving_claude_proxy(
        create_session_factory(engine), "127.0.0.1"
    ) as port:
        await _choose_claude(client, claude_on_this_machine)
        fake_claude.replies.append(answer("ok"))
        await _send(client, await _basic_thread(client), "Hi")

    proxy = f"http://127.0.0.1:{port}"
    assert fake_claude.opened
    assert all(run.options.env["HTTPS_PROXY"] == proxy for run in fake_claude.opened)


@pytest.mark.usefixtures("real_model")
async def test_a_chat_with_a_claude_host_off_is_refused_before_claude_code_runs(
    client: AsyncClient,
    claude_on_this_machine: ClaudeOnThisMachine,
    fake_claude: FakeClaude,
) -> None:
    """Checked with the chat's own egress check, like any remote model."""
    await _choose_claude(client, claude_on_this_machine)
    opened = len(fake_claude.opened)
    await client.put(
        "/egress", json={"destinations": ["host:platform.claude.com"], "enabled": False}
    )
    thread_id = await _basic_thread(client)

    reply = await client.post(
        f"/chat/threads/{thread_id}/messages", json={"text": "Hi"}
    )

    assert reply.status_code == 403
    assert reply.json()["detail"]["destination"] == "host:platform.claude.com"
    assert len(fake_claude.opened) == opened


@pytest.mark.usefixtures("real_model")
async def test_a_chat_on_a_claude_code_now_too_old_is_refused_before_it_runs(
    client: AsyncClient,
    claude_on_this_machine: ClaudeOnThisMachine,
    fake_claude: FakeClaude,
) -> None:
    """Replaced by an older one mid-session: the send is refused, so the composer can say why."""
    await _choose_claude(client, claude_on_this_machine)
    opened = len(fake_claude.opened)
    claude_on_this_machine(version="2.1.200 (Claude Code)")
    thread_id = await _basic_thread(client)

    reply = await client.post(
        f"/chat/threads/{thread_id}/messages", json={"text": "Hi"}
    )

    assert reply.status_code == 409
    assert reply.json()["detail"]["code"] == "claude_too_old"
    assert len(fake_claude.opened) == opened


@pytest.mark.usefixtures("real_model")
async def test_a_chat_after_claude_code_was_uninstalled_is_refused_before_it_runs(
    client: AsyncClient,
    claude_on_this_machine: ClaudeOnThisMachine,
    fake_claude: FakeClaude,
) -> None:
    """The composer's own reason, so it shows there as it does at startup."""
    installed = claude_on_this_machine()
    await _choose_claude(client, lambda: installed)
    installed.unlink()
    thread_id = await _basic_thread(client)

    reply = await client.post(
        f"/chat/threads/{thread_id}/messages", json={"text": "Hi"}
    )

    assert reply.status_code == 409
    assert reply.json()["detail"]["code"] == "claude_sign_in_required"


@pytest.mark.usefixtures("real_model")
async def test_no_claude_code_runs_without_the_proxy(
    client: AsyncClient,
    claude_on_this_machine: ClaudeOnThisMachine,
    fake_claude: FakeClaude,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fails closed: a Claude Code run that skipped the proxy would skip egress consent."""
    from modules.llm.subscriptions.claude import proxy as claude_proxy

    await _choose_claude(client, claude_on_this_machine)
    monkeypatch.setattr(claude_proxy, "_url", None)
    opened = len(fake_claude.opened)

    frames = await _send(client, await _basic_thread(client), "Hi")

    assert [f["type"] for f in frames if f.get("type") == "error"] == ["error"]
    assert len(fake_claude.opened) == opened


@pytest.mark.usefixtures("real_model")
async def test_a_host_turned_off_during_a_reply_says_so(
    client: AsyncClient,
    engine: Engine,
    claude_on_this_machine: ClaudeOnThisMachine,
    fake_claude: FakeClaude,
) -> None:
    """Checked before the reply and passed; switched off while Claude Code runs."""
    from claude_agent_sdk import SystemMessage

    from modules.egress.service import set_enabled

    await _choose_claude(client, claude_on_this_machine)

    def switch_off() -> None:
        with create_session_factory(engine)() as session:
            set_enabled(session, "host:api.anthropic.com", False)
            session.commit()

    def switched_off_mid_run() -> list:
        # Off the event loop, as Settings > Network's own request would be.
        flip = threading.Thread(target=switch_off)
        flip.start()
        flip.join()
        return [SystemMessage(subtype="api_retry", data={"attempt": 1}), *answer("x")]

    fake_claude.replies.append(switched_off_mid_run)

    frames = await _send(client, await _basic_thread(client), "Hi")

    errors = [f for f in frames if f.get("type") == "error"]
    assert [e["kind"] for e in errors] == ["egress_disabled"]


@pytest.mark.usefixtures("real_model")
async def test_a_basic_chat_says_whether_the_plan_is_on_extra_usage(
    client: AsyncClient,
    claude_on_this_machine: ClaudeOnThisMachine,
    fake_claude: FakeClaude,
) -> None:
    """As an agent turn does: once per reply, beside an answer that goes on."""
    await _choose_claude(client, claude_on_this_machine)
    past = plan_limits(using_extra=True)
    fake_claude.replies.append([past, *answer("Paris."), past])
    thread_id = await _basic_thread(client)

    frames = await _send(client, thread_id, "What is the capital of France?")

    assert [f for f in frames if f["type"] == "plan-extra-usage"] == [
        {"type": "plan-extra-usage", "using": True, "resets_at": RESETS_AT}
    ]
    assert "".join(f["text"] for f in frames if f["type"] == "delta") == "Paris."
