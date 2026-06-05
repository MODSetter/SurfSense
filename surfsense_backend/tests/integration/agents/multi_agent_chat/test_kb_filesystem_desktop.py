"""Real-behavior tests for the LIVE knowledge-base filesystem middleware (B).

These exercise ``app.agents.multi_agent_chat.shared.middleware.filesystem`` —
the decomposed middleware + tools that production actually mounts on the
knowledge_base subagent (via ``build_filesystem_mw``). The previous
``tests/unit/middleware/test_filesystem_*.py`` suite asserts a *dead twin*
(``app.agents.shared.middleware.filesystem``) that is never instantiated, so the
live tool path had no real coverage.

Strategy: mount the production ``build_filesystem_mw`` on a minimal
``create_agent`` graph and drive its tools with the scripted harness. Desktop
mode binds a ``MultiRootLocalFolderBackend`` to a real ``tmp_path`` directory,
so every write/edit/move/rm is asserted against the real on-disk filesystem —
no mocks, only the LLM is scripted.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agents.multi_agent_chat.shared.middleware.filesystem import (
    build_filesystem_mw,
)
from app.agents.multi_agent_chat.shared.middleware.filesystem.backends.resolver import (
    build_backend_resolver,
)
from app.agents.shared.filesystem_selection import (
    FilesystemMode,
    FilesystemSelection,
    LocalFilesystemMount,
)
from tests.integration.harness import ScriptedTurn, build_scripted_harness

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_MOUNT_ID = "workspace"


def _build_desktop_fs_mw(root: Path):
    """Build the production filesystem middleware bound to a real local folder."""
    selection = FilesystemSelection(
        mode=FilesystemMode.DESKTOP_LOCAL_FOLDER,
        local_mounts=(
            LocalFilesystemMount(mount_id=_MOUNT_ID, root_path=str(root)),
        ),
    )
    resolver = build_backend_resolver(selection)
    return build_filesystem_mw(
        backend_resolver=resolver,
        filesystem_mode=FilesystemMode.DESKTOP_LOCAL_FOLDER,
        search_space_id=1,
        user_id="00000000-0000-0000-0000-000000000001",
        thread_id=1,
        read_only=False,
    )


async def _run(root: Path, turns: list[ScriptedTurn], thread: str):
    """Assemble a 1-middleware agent and drive the scripted turns to completion."""
    harness = build_scripted_harness(turns=turns)
    fs_mw = _build_desktop_fs_mw(root)
    agent = create_agent(
        harness.model,
        tools=[],
        middleware=[fs_mw],
        checkpointer=InMemorySaver(),
    )
    return await agent.ainvoke(
        {"messages": [HumanMessage(content="do filesystem work")]},
        config={"configurable": {"thread_id": thread}},
    )


def _tool_messages(result) -> list[ToolMessage]:
    return [m for m in result["messages"] if isinstance(m, ToolMessage)]


def _tool_text(result, name: str) -> str:
    for m in _tool_messages(result):
        if m.name == name:
            return str(m.content)
    raise AssertionError(f"no ToolMessage from {name!r} in {_tool_messages(result)}")


async def test_write_then_read_round_trip(tmp_path: Path):
    """write_file persists to the real folder and read_file returns the content."""
    result = await _run(
        tmp_path,
        [
            ScriptedTurn(
                tool_calls=[
                    {
                        "name": "write_file",
                        "args": {
                            "file_path": f"/{_MOUNT_ID}/notes.md",
                            "content": "hello FS-CANARY-001",
                        },
                        "id": "c1",
                    }
                ]
            ),
            ScriptedTurn(
                tool_calls=[
                    {
                        "name": "read_file",
                        "args": {"file_path": f"/{_MOUNT_ID}/notes.md"},
                        "id": "c2",
                    }
                ]
            ),
            ScriptedTurn(text="done"),
        ],
        "fs-desktop-write-read",
    )

    # Real on-disk effect, not a mock.
    assert (tmp_path / "notes.md").read_text() == "hello FS-CANARY-001"
    # The tool actually returned the file content.
    assert "FS-CANARY-001" in _tool_text(result, "read_file")


async def test_write_then_ls_lists_file(tmp_path: Path):
    """ls reflects a freshly written file in the real folder."""
    result = await _run(
        tmp_path,
        [
            ScriptedTurn(
                tool_calls=[
                    {
                        "name": "write_file",
                        "args": {
                            "file_path": f"/{_MOUNT_ID}/report.md",
                            "content": "x",
                        },
                        "id": "c1",
                    }
                ]
            ),
            ScriptedTurn(
                tool_calls=[
                    {"name": "ls", "args": {"path": f"/{_MOUNT_ID}"}, "id": "c2"}
                ]
            ),
            ScriptedTurn(text="done"),
        ],
        "fs-desktop-ls",
    )

    assert (tmp_path / "report.md").exists()
    assert "report.md" in _tool_text(result, "ls")


async def test_edit_file_rewrites_on_disk(tmp_path: Path):
    """edit_file applies a real string replacement to the on-disk file."""
    result = await _run(
        tmp_path,
        [
            ScriptedTurn(
                tool_calls=[
                    {
                        "name": "write_file",
                        "args": {
                            "file_path": f"/{_MOUNT_ID}/doc.md",
                            "content": "the quick brown fox",
                        },
                        "id": "c1",
                    }
                ]
            ),
            ScriptedTurn(
                tool_calls=[
                    {
                        "name": "edit_file",
                        "args": {
                            "file_path": f"/{_MOUNT_ID}/doc.md",
                            "old_string": "brown",
                            "new_string": "red",
                        },
                        "id": "c2",
                    }
                ]
            ),
            ScriptedTurn(text="done"),
        ],
        "fs-desktop-edit",
    )

    assert (tmp_path / "doc.md").read_text() == "the quick red fox"


async def test_write_into_existing_subdir(tmp_path: Path):
    """A write into an EXISTING subdirectory lands on disk under that folder."""
    (tmp_path / "sub").mkdir()
    result = await _run(
        tmp_path,
        [
            ScriptedTurn(
                tool_calls=[
                    {
                        "name": "write_file",
                        "args": {
                            "file_path": f"/{_MOUNT_ID}/sub/inner.md",
                            "content": "nested",
                        },
                        "id": "c1",
                    }
                ]
            ),
            ScriptedTurn(text="done"),
        ],
        "fs-desktop-subdir",
    )

    assert "Error" not in _tool_text(result, "write_file")
    assert (tmp_path / "sub" / "inner.md").read_text() == "nested"


async def test_write_to_missing_parent_dir_is_rejected(tmp_path: Path):
    """Desktop write refuses to create a file under a non-existent directory.

    Real current behavior: the local-folder backend requires the parent to
    exist (and ``mkdir`` is a no-op for this backend), so the agent cannot
    fabricate new nested folders via ``write_file``. Locking this guards against
    a silent behavior change during the agents-module reorg.
    """
    result = await _run(
        tmp_path,
        [
            ScriptedTurn(
                tool_calls=[
                    {
                        "name": "write_file",
                        "args": {
                            "file_path": f"/{_MOUNT_ID}/missing/inner.md",
                            "content": "nested",
                        },
                        "id": "c1",
                    }
                ]
            ),
            ScriptedTurn(text="done"),
        ],
        "fs-desktop-missing-parent",
    )

    write_msg = _tool_text(result, "write_file")
    assert "parent directory" in write_msg.lower()
    assert not (tmp_path / "missing").exists()


async def test_move_file_relocates_on_disk(tmp_path: Path):
    """move_file relocates the real file from source to destination."""
    await _run(
        tmp_path,
        [
            ScriptedTurn(
                tool_calls=[
                    {
                        "name": "write_file",
                        "args": {
                            "file_path": f"/{_MOUNT_ID}/src.md",
                            "content": "movable",
                        },
                        "id": "c1",
                    }
                ]
            ),
            ScriptedTurn(
                tool_calls=[
                    {
                        "name": "move_file",
                        "args": {
                            "source_path": f"/{_MOUNT_ID}/src.md",
                            "destination_path": f"/{_MOUNT_ID}/dst.md",
                        },
                        "id": "c2",
                    }
                ]
            ),
            ScriptedTurn(text="done"),
        ],
        "fs-desktop-move",
    )

    assert not (tmp_path / "src.md").exists()
    assert (tmp_path / "dst.md").read_text() == "movable"


async def test_rm_deletes_file_on_disk(tmp_path: Path):
    """rm removes the real file (desktop deletes are immediate)."""
    await _run(
        tmp_path,
        [
            ScriptedTurn(
                tool_calls=[
                    {
                        "name": "write_file",
                        "args": {
                            "file_path": f"/{_MOUNT_ID}/trash.md",
                            "content": "bye",
                        },
                        "id": "c1",
                    }
                ]
            ),
            ScriptedTurn(
                tool_calls=[
                    {
                        "name": "rm",
                        "args": {"path": f"/{_MOUNT_ID}/trash.md"},
                        "id": "c2",
                    }
                ]
            ),
            ScriptedTurn(text="done"),
        ],
        "fs-desktop-rm",
    )

    assert not (tmp_path / "trash.md").exists()


async def test_rmdir_removes_empty_dir_on_disk(tmp_path: Path):
    """rmdir removes a real empty directory."""
    (tmp_path / "gone").mkdir()
    assert (tmp_path / "gone").is_dir()

    result = await _run(
        tmp_path,
        [
            ScriptedTurn(
                tool_calls=[
                    {
                        "name": "rmdir",
                        "args": {"path": f"/{_MOUNT_ID}/gone"},
                        "id": "c1",
                    }
                ]
            ),
            ScriptedTurn(text="done"),
        ],
        "fs-desktop-rmdir",
    )

    assert "Error" not in _tool_text(result, "rmdir")
    assert not (tmp_path / "gone").exists()
