"""Real-behavior tests for the LIVE knowledge-base filesystem middleware (B) in
cloud mode.

Cloud mode is the default production filesystem for web chat. Unlike desktop,
cloud writes/edits/moves/deletes are *staged* into LangGraph state during the
turn and committed to Postgres at end-of-turn by the persistence middleware.
These tests drive the production ``build_filesystem_mw`` cloud tools through a
real ``create_agent`` graph and assert the staging contract (namespace policy,
read-from-stage, mkdir staging, duplicate rejection) — all deterministic and
DB-free because cloud ``awrite`` is pure in-state staging.

The end-of-turn DB commit (``commit_staged_filesystem_state``) is covered
separately; here we lock the per-tool behavior that the reorg could break.
"""

from __future__ import annotations

import pytest
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import (
    FilesystemMode,
    FilesystemSelection,
)
from app.agents.chat.multi_agent_chat.shared.middleware.filesystem import (
    build_filesystem_mw,
)
from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.backends.resolver import (
    build_backend_resolver,
)
from tests.integration.harness import ScriptedTurn, build_scripted_harness

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_SEARCH_SPACE_ID = 1


def _build_cloud_fs_mw():
    """Build the production filesystem middleware in cloud mode.

    A non-None ``search_space_id`` makes the resolver hand out a
    ``KBPostgresBackend``, exactly as production does. Staging operations never
    touch the DB, so a dummy id is sufficient for these tests.
    """
    selection = FilesystemSelection(mode=FilesystemMode.CLOUD)
    resolver = build_backend_resolver(selection, search_space_id=_SEARCH_SPACE_ID)
    return build_filesystem_mw(
        backend_resolver=resolver,
        filesystem_mode=FilesystemMode.CLOUD,
        search_space_id=_SEARCH_SPACE_ID,
        user_id="00000000-0000-0000-0000-000000000001",
        thread_id=_SEARCH_SPACE_ID,
        read_only=False,
    )


async def _run(turns: list[ScriptedTurn], thread: str):
    harness = build_scripted_harness(turns=turns)
    agent = create_agent(
        harness.model,
        tools=[],
        middleware=[_build_cloud_fs_mw()],
        checkpointer=InMemorySaver(),
    )
    return await agent.ainvoke(
        {"messages": [HumanMessage(content="do kb work")]},
        config={"configurable": {"thread_id": thread}},
    )


def _tool_text(result, name: str) -> str:
    for m in result["messages"]:
        if isinstance(m, ToolMessage) and m.name == name:
            return str(m.content)
    raise AssertionError(f"no ToolMessage from {name!r}")


def _write(path: str, content: str, call_id: str) -> ScriptedTurn:
    return ScriptedTurn(
        tool_calls=[
            {
                "name": "write_file",
                "args": {"file_path": path, "content": content},
                "id": call_id,
            }
        ]
    )


async def test_cloud_write_then_read_returns_staged_content():
    """A cloud write stages into state and a later read returns that content."""
    result = await _run(
        [
            _write("/documents/note.md", "cloud CANARY-CLD-1", "c1"),
            ScriptedTurn(
                tool_calls=[
                    {
                        "name": "read_file",
                        "args": {"file_path": "/documents/note.md"},
                        "id": "c2",
                    }
                ]
            ),
            ScriptedTurn(text="done"),
        ],
        "fs-cloud-write-read",
    )

    assert "Updated file /documents/note.md" in _tool_text(result, "write_file")
    assert "CANARY-CLD-1" in _tool_text(result, "read_file")


async def test_cloud_write_outside_documents_is_rejected():
    """Cloud namespace policy: writes must target /documents (non-temp paths)."""
    result = await _run(
        [
            _write("/scratch/note.md", "nope", "c1"),
            ScriptedTurn(text="done"),
        ],
        "fs-cloud-namespace",
    )

    msg = _tool_text(result, "write_file")
    assert "must target /documents" in msg


async def test_cloud_temp_prefixed_write_is_allowed_anywhere():
    """A ``temp_`` basename escapes the /documents namespace restriction."""
    result = await _run(
        [
            _write("/temp_scratch.md", "ephemeral", "c1"),
            ScriptedTurn(text="done"),
        ],
        "fs-cloud-temp",
    )

    msg = _tool_text(result, "write_file")
    assert "must target /documents" not in msg
    assert "Updated file" in msg


async def test_cloud_mkdir_stages_directory():
    """Cloud mkdir stages the directory for end-of-turn creation (no immediate IO)."""
    result = await _run(
        [
            ScriptedTurn(
                tool_calls=[
                    {
                        "name": "mkdir",
                        "args": {"path": "/documents/projects"},
                        "id": "c1",
                    }
                ]
            ),
            ScriptedTurn(text="done"),
        ],
        "fs-cloud-mkdir",
    )

    msg = _tool_text(result, "mkdir")
    assert "Staged directory" in msg
    assert "/documents/projects" in msg


async def test_cloud_mkdir_outside_documents_is_rejected():
    """Cloud mkdir is also restricted to the /documents namespace."""
    result = await _run(
        [
            ScriptedTurn(
                tool_calls=[
                    {"name": "mkdir", "args": {"path": "/elsewhere"}, "id": "c1"}
                ]
            ),
            ScriptedTurn(text="done"),
        ],
        "fs-cloud-mkdir-bad",
    )

    assert "must target a path under /documents" in _tool_text(result, "mkdir")


async def test_cloud_duplicate_write_is_rejected():
    """Writing to a path already staged this turn is rejected (use edit instead)."""
    result = await _run(
        [
            _write("/documents/dup.md", "first", "c1"),
            _write("/documents/dup.md", "second", "c2"),
            ScriptedTurn(text="done"),
        ],
        "fs-cloud-dup",
    )

    # Two write ToolMessages: first succeeds, second is rejected.
    write_msgs = [
        str(m.content)
        for m in result["messages"]
        if isinstance(m, ToolMessage) and m.name == "write_file"
    ]
    assert len(write_msgs) == 2
    assert "Updated file" in write_msgs[0]
    assert "already exists" in write_msgs[1]
