"""An Agentic thread on a Claude plan model runs on the user's Claude Code, as opencode's do."""

import asyncio
import json
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.chat.models import AgentEngineKind, ChatThread
from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.custom_plugin import store_custom_plugin
from modules.plugins.installed.models import InstalledPlugin, PluginTool
from modules.plugins.installed.third_party import set_third_party_on
from modules.plugins.remote.sign_in.headers.header_rules import SignInHeader
from modules.plugins.remote.sign_in.headers.headers_credential import write_headers
from shared.config import get_agent_settings, get_storage_settings
from shared.db import create_session_factory
from tests.claude_agent_stand_in import Call, Fail, Hang, Limits, Say
from tests.claude_run_stand_in import RESETS_AT
from tests.integration.agent.claude_code.conftest import ClaudeAgent
from tests.integration.agent.test_runtime_proxy import connect_plugin

pytestmark = pytest.mark.integration
SONNET = "claude-sonnet-5-5"


async def _agentic_thread(client: AsyncClient, claude_on_this_machine) -> dict:
    """A Claude plan model chosen, both its hosts allowed, and an Agentic thread opened."""
    claude_on_this_machine()
    await client.put(
        "/egress",
        json={
            "destinations": ["host:api.anthropic.com", "host:platform.claude.com"],
            "enabled": True,
        },
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
    workspace = (await client.post("/workspaces", json={"name": "w"})).json()
    opened = await client.post(
        f"/workspaces/{workspace['id']}/chat/threads", json={"mode": "agentic"}
    )
    assert opened.status_code == 201, opened.text
    return opened.json()


async def _send(client: AsyncClient, thread_id: int, text: str, on_frame=None) -> list:
    frames: list[dict] = []
    async with client.stream(
        "POST", f"/chat/threads/{thread_id}/messages", json={"text": text}
    ) as reply:
        assert reply.status_code == 200, await reply.aread()
        async for line in reply.aiter_lines():
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            frame = json.loads(line.removeprefix("data: "))
            frames.append(frame)
            if on_frame is not None:
                await on_frame(frame)
    return frames


def _of(frames: list[dict], kind: str) -> list[dict]:
    return [frame for frame in frames if frame["type"] == kind]


async def test_an_agentic_thread_on_a_claude_plan_model_runs_on_claude_code(
    client: AsyncClient,
    engine: Engine,
    claude_on_this_machine,
    claude_agent: ClaudeAgent,
) -> None:
    """No opencode is needed: the user's Claude Code is the agent."""
    thread = await _agentic_thread(client, claude_on_this_machine)

    assert thread["uses_agent"] is True
    with create_session_factory(engine)() as session:
        stored = session.get(ChatThread, thread["id"])
        assert stored.agent_engine is AgentEngineKind.CLAUDE_CODE
        assert stored.claude_session_id is not None


async def test_a_turn_streams_its_steps_and_reply_as_an_opencode_turn_does(
    client: AsyncClient, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """The same frames the thread already shows: accepted, steps, words, completed."""
    claude_agent.turns = [
        [
            Call("mcp__surfsense__search_sources", {"query": "Q3"}, "No passages."),
            Call("Write", {"file_path": "outputs/q3.md", "content": "x"}),
            Say("Revenue grew 12%."),
        ]
    ]
    thread = await _agentic_thread(client, claude_on_this_machine)

    frames = await _send(client, thread["id"], "What grew in Q3?")

    assert frames[0]["type"] == "agent-preparing"
    assert _of(frames, "accepted")[0]["user_message_id"]
    ended = [s for s in _of(frames, "agent-step") if s["status"] == "completed"]
    assert [s["tool"] for s in ended] == ["surfsense_search_sources", "write"]
    assert ended[1]["input"]["path"] == "outputs/q3.md"
    assert _of(frames, "completed")[0]["text"] == "Revenue grew 12%."


async def test_claude_code_works_in_the_threads_folder_with_surfsenses_tools(
    client: AsyncClient, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """The tool endpoint is given with the launch key in a file, never on the command line."""
    claude_agent.turns = [[Say("Hi.")]]
    thread = await _agentic_thread(client, claude_on_this_machine)

    await _send(client, thread["id"], "Hello")

    (run,) = claude_agent.started
    folder = get_storage_settings().thread_working_dir(
        thread["workspace_id"], thread["id"]
    )
    assert run.options.cwd == str(folder)
    assert run.options.model == SONNET
    servers = json.loads(Path(run.options.mcp_servers).read_text())["mcpServers"]
    assert servers["surfsense"]["url"].endswith(
        f"/agent/tools/workspaces/{thread['workspace_id']}/threads/{thread['id']}"
    )
    assert servers["surfsense"]["headers"]["Authorization"].startswith("Bearer ")


async def test_a_plugin_still_on_the_older_sse_transport_is_not_given(
    client: AsyncClient,
    engine: Engine,
    claude_on_this_machine,
    claude_agent: ClaudeAgent,
) -> None:
    """Claude Code still speaks SSE, but opencode does not: a thread behaves alike on either."""
    connect_plugin(engine, "https://localhost:1/sse", transport="sse")
    claude_agent.turns = [[Say("Hi.")]]
    thread = await _agentic_thread(client, claude_on_this_machine)

    await _send(client, thread["id"], "Hello")

    (run,) = claude_agent.started
    servers = json.loads(Path(run.options.mcp_servers).read_text())["mcpServers"]
    assert "notes" not in servers


async def test_claude_code_is_given_the_gateway_and_never_a_plugins_key(
    client: AsyncClient,
    engine: Engine,
    claude_on_this_machine,
    claude_agent: ClaudeAgent,
) -> None:
    """Its MCP file names the gateway and the thread's key; the plugin's key stays SurfSense's."""
    connect_plugin(engine, "https://localhost:1/mcp")
    with create_session_factory(engine)() as session:
        plugin = session.get_one(InstalledPlugin, "notes")
        write_headers(plugin, [SignInHeader(name="x-api-key", value="k-secret-1")])
        session.commit()
    claude_agent.turns = [[Say("Hi.")]]
    thread = await _agentic_thread(client, claude_on_this_machine)

    await _send(client, thread["id"], "Hello")

    (run,) = claude_agent.started
    written = Path(run.options.mcp_servers).read_text()
    servers = json.loads(written)["mcpServers"]
    assert "/agent/plugins/" in servers["notes"]["url"]
    assert "localhost:1" not in written
    assert "k-secret-1" not in written


async def test_claude_code_is_given_every_ready_tool_and_finds_them_by_search(
    client: AsyncClient,
    engine: Engine,
    claude_on_this_machine,
    claude_agent: ClaudeAgent,
) -> None:
    """No count limits a Claude Code turn: its own tool search defers what it need not load."""
    many = [
        SourceTool(
            name=f"tool_{n}",
            title=None,
            description=f"Tool number {n}.",
            input_schema={},
            annotations={"readOnlyHint": True},
        )
        for n in range(40)
    ]
    with create_session_factory(engine)() as session:
        store_custom_plugin(
            session, "notes", "Notes", "https://localhost:1/mcp", None, many
        )
        set_third_party_on(session, True)
        session.commit()
    claude_agent.turns = [[Say("Hi.")]]
    thread = await _agentic_thread(client, claude_on_this_machine)

    await _send(client, thread["id"], "Hello")

    (run,) = claude_agent.started
    servers = json.loads(Path(run.options.mcp_servers).read_text())["mcpServers"]
    assert not [t for t in run.options.disallowed_tools if "tool_" in t]
    assert run.options.env["ENABLE_TOOL_SEARCH"] == "auto"
    assert servers["surfsense"]["alwaysLoad"] is True
    assert "alwaysLoad" not in servers["notes"]


async def test_the_thread_reads_back_as_it_streamed(
    client: AsyncClient, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """From SurfSense's copy of the session, under the ids the live frames used."""
    claude_agent.turns = [
        [Call("Glob", {"pattern": "sources/*"}, "a.md"), Say("Found a.md.")]
    ]
    thread = await _agentic_thread(client, claude_on_this_machine)
    frames = await _send(client, thread["id"], "List the sources")

    listed = (await client.get(f"/chat/threads/{thread['id']}/messages")).json()

    accepted = _of(frames, "accepted")[0]
    assert [turn["id"] for turn in listed] == [
        accepted["user_message_id"],
        accepted["assistant_message_id"],
    ]
    assert listed[0]["content"]["text"] == "List the sources"
    assert listed[1]["content"]["text"] == "Found a.md."
    assert [step["tool"] for step in listed[1]["content"]["steps"]] == ["glob"]


async def test_the_next_turn_resumes_the_same_claude_code(
    client: AsyncClient, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """Set up alike, the second turn reuses the running Claude Code and its session."""
    claude_agent.turns = [[Say("One.")], [Say("Two.")]]
    thread = await _agentic_thread(client, claude_on_this_machine)

    await _send(client, thread["id"], "First")
    await _send(client, thread["id"], "Second")

    (run,) = claude_agent.started
    assert len(run.sent) == 2
    listed = (await client.get(f"/chat/threads/{thread['id']}/messages")).json()
    assert [turn["content"]["text"] for turn in listed] == [
        "First",
        "One.",
        "Second",
        "Two.",
    ]


async def test_a_refused_call_is_an_error_step_and_the_turn_goes_on(
    client: AsyncClient, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """The gate refuses outside the folder, as opencode's rules do, and says why."""
    claude_agent.turns = [
        [Call("Read", {"file_path": "/etc/hosts"}), Say("I can't read that.")]
    ]
    thread = await _agentic_thread(client, claude_on_this_machine)

    frames = await _send(client, thread["id"], "Read /etc/hosts")

    step = _of(frames, "agent-step")[-1]
    assert step["status"] == "error"
    assert "thread's folder" in step["error"]
    assert _of(frames, "completed")[0]["text"] == "I can't read that."


async def test_a_signed_out_claude_code_shows_the_sign_in_notice(
    client: AsyncClient, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """The same notice a chat on the plan shows, and the reply reads back failed."""
    claude_agent.turns = [[Fail("authentication_failed")]]
    thread = await _agentic_thread(client, claude_on_this_machine)

    frames = await _send(client, thread["id"], "Hello")

    (error,) = _of(frames, "error")
    assert error["kind"] == "claude_sign_in"


async def test_stop_interrupts_claude_code_and_the_reply_reads_back_stopped(
    client: AsyncClient, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """After a reload the thread still says the user cut this reply short."""
    claude_agent.turns = [[Hang("Thinking about")]]
    thread = await _agentic_thread(client, claude_on_this_machine)

    sending = asyncio.create_task(_send(client, thread["id"], "Go"))
    while not claude_agent.started:
        await asyncio.sleep(0.01)
    await asyncio.wait_for(claude_agent.started[0].hanging.wait(), 5)
    stopped = await client.post(f"/chat/threads/{thread['id']}/run/stop")
    await asyncio.wait_for(sending, 5)

    assert stopped.status_code == 204
    assert claude_agent.started[0].interrupted
    reply = (await client.get(f"/chat/threads/{thread['id']}/messages")).json()[-1]
    assert reply["content"]["text"] == "Thinking about"
    assert reply["content"]["ending"] == {"type": "stopped"}


async def test_deleting_the_thread_ends_its_claude_code(
    client: AsyncClient,
    engine: Engine,
    claude_on_this_machine,
    claude_agent: ClaudeAgent,
) -> None:
    """Its running Claude Code, its config file and SurfSense's copy all go."""
    claude_agent.turns = [[Say("Hi.")]]
    thread = await _agentic_thread(client, claude_on_this_machine)
    await _send(client, thread["id"], "Hello")
    (run,) = claude_agent.started
    config = Path(run.options.mcp_servers)

    deleted = await client.delete(f"/chat/threads/{thread['id']}")

    assert deleted.status_code == 204
    assert run.closed
    assert not config.exists()


async def test_a_plugin_call_waits_for_the_users_yes(
    base_url: str, engine: Engine, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """A tool the gateway asks about holds Claude Code's call until Allow once arrives."""
    connect_plugin(engine, "https://localhost:1/mcp")
    claude_agent.turns = [
        [Call("mcp__notes__search", {"query": "Q3"}, "Q3 notes."), Say("Found them.")]
    ]
    asked: list[dict] = []
    async with AsyncClient(base_url=base_url, timeout=30) as live:
        thread = await _agentic_thread(live, claude_on_this_machine)

        async def approve(frame: dict) -> None:
            if frame["type"] == "permission-request":
                asked.append(frame)
                reply = await live.post(
                    f"/chat/threads/{thread['id']}/permissions/{frame['id']}",
                    json={"reply": "once"},
                )
                assert reply.status_code == 204

        frames = await _send(live, thread["id"], "Search my notes", approve)

    (request,) = asked
    assert request["permission"] == "notes_search"
    step = [s for s in _of(frames, "agent-step") if s["call_id"] == request["call_id"]]
    assert step[-1]["status"] == "completed"
    assert step[-1]["output"] == "Q3 notes."
    assert _of(frames, "completed")[0]["text"] == "Found them."


async def test_a_rejected_plugin_call_never_runs(
    base_url: str, engine: Engine, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """Reject reaches Claude Code as a refusal, and the step fails with it."""
    connect_plugin(engine, "https://localhost:1/mcp")
    claude_agent.turns = [[Call("mcp__notes__search", {"query": "Q3"}), Say("Okay.")]]
    async with AsyncClient(base_url=base_url, timeout=30) as live:
        thread = await _agentic_thread(live, claude_on_this_machine)

        async def reject(frame: dict) -> None:
            if frame["type"] == "permission-request":
                await live.post(
                    f"/chat/threads/{thread['id']}/permissions/{frame['id']}",
                    json={"reply": "reject"},
                )

        frames = await _send(live, thread["id"], "Search my notes", reject)

    assert _of(frames, "permission-replied")[0]["reply"] == "reject"
    assert _of(frames, "agent-step")[-1]["error"] == "The user rejected this action."


async def test_a_steps_whole_result_is_read_from_surfsenses_copy(
    client: AsyncClient, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """Show full result reads the step as stored, past what its frame carried."""
    long = "x" * 5000
    claude_agent.turns = [
        [Call("Read", {"file_path": "sources/a.md"}, long), Say("Read.")]
    ]
    thread = await _agentic_thread(client, claude_on_this_machine)
    frames = await _send(client, thread["id"], "Read a.md")
    step = _of(frames, "agent-step")[-1]

    whole = await client.get(f"/chat/threads/{thread['id']}/steps/{step['id']}/result")

    assert len(step["output"]) < len(long)
    assert whole.status_code == 200
    assert whole.json() == {"output": long, "error": None}


async def test_after_stop_the_next_message_is_answered(
    client: AsyncClient, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """The stopped turn's end is read, so it never stands in for the next turn's reply."""
    claude_agent.turns = [[Hang("Thinking about")], [Say("Fresh answer.")]]
    thread = await _agentic_thread(client, claude_on_this_machine)
    sending = asyncio.create_task(_send(client, thread["id"], "Go"))
    while not claude_agent.started:
        await asyncio.sleep(0.01)
    await asyncio.wait_for(claude_agent.started[0].hanging.wait(), 5)
    await client.post(f"/chat/threads/{thread['id']}/run/stop")
    await asyncio.wait_for(sending, 5)

    frames = await _send(client, thread["id"], "Try again")

    assert _of(frames, "completed")[0]["text"] == "Fresh answer."


async def test_a_plugin_still_connecting_at_start_is_not_called_unreachable(
    client: AsyncClient,
    engine: Engine,
    claude_on_this_machine,
    claude_agent: ClaudeAgent,
) -> None:
    """Claude Code connects plugins in the background; its turn's init says how they ended."""
    connect_plugin(engine, "https://localhost:1/mcp")
    claude_agent.turns = [[Say("Done.")]]
    thread = await _agentic_thread(client, claude_on_this_machine)

    frames = await _send(client, thread["id"], "Search my notes")

    assert _of(frames, "agent-plugins-unavailable") == []


async def test_a_plugin_that_failed_to_connect_is_named(
    client: AsyncClient,
    engine: Engine,
    claude_on_this_machine,
    claude_agent: ClaudeAgent,
) -> None:
    """As opencode's turn names one: the plugin, and why it cannot be used."""
    connect_plugin(engine, "https://localhost:1/mcp")
    claude_agent.statuses = {"notes": "failed"}
    claude_agent.turns = [[Say("Done.")]]
    thread = await _agentic_thread(client, claude_on_this_machine)

    frames = await _send(client, thread["id"], "Search my notes")

    (notice,) = _of(frames, "agent-plugins-unavailable")
    assert notice["plugins"] == [{"title": "Notes", "reason": "unreachable"}]


async def test_the_model_reads_a_long_result_claude_code_saved_for_it(
    client: AsyncClient,
    engine: Engine,
    claude_on_this_machine,
    claude_agent: ClaudeAgent,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A large plugin result is saved under the session; reading it is not refused."""
    home = tmp_path / "claude-home"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    thread = await _agentic_thread(client, claude_on_this_machine)
    with create_session_factory(engine)() as session:
        session_id = session.get(ChatThread, thread["id"]).claude_session_id
    saved = home / "projects" / "-threads" / session_id / "tool-results" / "toolu_9.txt"
    claude_agent.turns = [
        [
            Call("Grep", {"pattern": "title", "path": str(saved)}, "title: Q3"),
            Say("Q3."),
        ]
    ]

    frames = await _send(client, thread["id"], "Search the web")

    (step,) = _of(frames, "agent-step")[-1:]
    assert step["status"] == "completed"
    assert step["output"] == "title: Q3"


async def test_a_plugin_whose_tools_changed_is_reconnected_in_the_running_claude_code(
    client: AsyncClient,
    engine: Engine,
    claude_on_this_machine,
    claude_agent: ClaudeAgent,
) -> None:
    """Claude Code lists a plugin's tools once it connects: a new input schema needs a new connection."""
    connect_plugin(engine, "https://localhost:1/mcp")
    claude_agent.turns = [[Say("One.")], [Say("Two.")], [Say("Three.")]]
    thread = await _agentic_thread(client, claude_on_this_machine)
    await _send(client, thread["id"], "First")
    await _send(client, thread["id"], "Second")
    with create_session_factory(engine)() as session:
        search = session.get_one(PluginTool, ("notes", "search"))
        search.input_schema = {
            "type": "object",
            "properties": {"q": {"type": "string"}},
        }
        session.commit()

    await _send(client, thread["id"], "Third")

    (run,) = claude_agent.started
    assert run.reconnected == ["notes"]


def _claude_codes_files(home: Path, session_id: str) -> tuple[Path, Path]:
    """A session's transcript and a saved result, where Claude Code writes them."""
    project = home / "projects" / "-threads-1"
    saved = project / session_id / "tool-results" / "toolu_1.txt"
    saved.parent.mkdir(parents=True)
    saved.write_text("ledger")
    transcript = project / f"{session_id}.jsonl"
    transcript.write_text('{"type": "user"}\n')
    return transcript, saved


async def test_after_a_turn_claude_codes_transcript_is_deleted_and_saved_results_kept(
    client: AsyncClient,
    engine: Engine,
    claude_on_this_machine,
    claude_agent: ClaudeAgent,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SurfSense's copy is the thread; a later turn may still read an earlier saved result."""
    home = tmp_path / "claude-home"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    claude_agent.turns = [[Say("Hi.")]]
    thread = await _agentic_thread(client, claude_on_this_machine)
    with create_session_factory(engine)() as session:
        session_id = session.get_one(ChatThread, thread["id"]).claude_session_id
    transcript, saved = _claude_codes_files(home, session_id)

    await _send(client, thread["id"], "Hello")

    assert not transcript.exists()
    assert saved.read_text() == "ledger"


async def test_deleting_the_thread_deletes_claude_codes_saved_results(
    client: AsyncClient,
    engine: Engine,
    claude_on_this_machine,
    claude_agent: ClaudeAgent,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the transcript gone after each turn, the session's folder still goes with the thread."""
    home = tmp_path / "claude-home"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    claude_agent.turns = [[Say("Hi.")]]
    thread = await _agentic_thread(client, claude_on_this_machine)
    with create_session_factory(engine)() as session:
        session_id = session.get_one(ChatThread, thread["id"]).claude_session_id
    _, saved = _claude_codes_files(home, session_id)
    await _send(client, thread["id"], "Hello")

    deleted = await client.delete(f"/chat/threads/{thread['id']}")

    assert deleted.status_code == 204
    assert not saved.parent.parent.exists()


async def test_each_reply_says_whether_the_plan_is_on_extra_usage(
    client: AsyncClient, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """Once per reply, so the composer can say so before the next one, and stop once back within the plan."""
    claude_agent.turns = [
        [Limits(using_extra=True), Say("Q3 grew."), Limits(using_extra=True)],
        [Limits(using_extra=False), Say("Two.")],
    ]
    thread = await _agentic_thread(client, claude_on_this_machine)

    past = await _send(client, thread["id"], "What grew?")
    within = await _send(client, thread["id"], "And then?")

    assert _of(past, "plan-extra-usage") == [
        {"type": "plan-extra-usage", "using": True, "resets_at": RESETS_AT}
    ]
    assert _of(past, "completed")[0]["text"] == "Q3 grew."
    assert _of(within, "plan-extra-usage") == [
        {"type": "plan-extra-usage", "using": False, "resets_at": RESETS_AT}
    ]


async def test_a_turn_on_a_claude_code_now_too_old_is_refused_before_it_runs(
    client: AsyncClient, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """As a chat is: refused before anything starts, so the composer says why."""
    thread = await _agentic_thread(client, claude_on_this_machine)
    claude_on_this_machine(version="2.1.200 (Claude Code)")

    reply = await client.post(
        f"/chat/threads/{thread['id']}/messages", json={"text": "Hello"}
    )

    assert reply.status_code == 409
    assert reply.json()["detail"]["code"] == "claude_too_old"
    assert claude_agent.started == []


async def test_a_thread_that_left_opencode_reads_back_while_opencode_cannot_answer(
    client: AsyncClient,
    engine: Engine,
    claude_on_this_machine,
    claude_agent: ClaudeAgent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Its opencode session is from before; opencode gone from this install must not keep it from opening."""
    claude_agent.turns = [
        [Call("Glob", {"pattern": "sources/*.md"}, "a.md"), Say("One.")]
    ]
    thread = await _agentic_thread(client, claude_on_this_machine)
    frames = await _send(client, thread["id"], "List my sources")
    (step,) = _of(frames, "agent-step")[-1:]
    with create_session_factory(engine)() as session:
        row = session.get_one(ChatThread, thread["id"])
        row.opencode_session_id = "ses_from_before"
        session.commit()
    # As on a machine without the agent installed: opencode refuses at once.
    monkeypatch.setattr(get_agent_settings(), "opencode_url", None)

    listed = await client.get(f"/chat/threads/{thread['id']}/messages")
    whole = await client.get(f"/chat/threads/{thread['id']}/steps/{step['id']}/result")

    assert listed.status_code == 200, listed.text
    assert [turn["content"]["text"] for turn in listed.json()] == [
        "List my sources",
        "One.",
    ]
    assert whole.status_code == 200, whole.text
    assert whole.json()["output"] == "a.md"
