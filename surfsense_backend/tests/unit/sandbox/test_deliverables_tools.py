from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools import (
    sandbox as sandbox_tools,
    save_artifact as save_tool,
)
from app.sandbox import ExecResult


class FakeSession:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.writes: dict[str, bytes] = {}

    async def read_file(self, path: str) -> bytes:
        return self.files[path]

    async def write_file(self, path: str, data: bytes) -> None:
        self.writes[path] = data

    async def run_command(self, command: str) -> ExecResult:
        path = command.split("-- ", 1)[1].strip("'")
        return ExecResult(str(len(self.files[path])), 0)


class FakeRegistry:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def get_session(self, thread_id, workspace_id):
        return self.session


def _runtime():
    return SimpleNamespace(tool_call_id="call-1", state={})


async def test_binary_save_reads_primary_and_preview_with_sniffed_roles(monkeypatch):
    session = FakeSession(
        {
            "/workspace/out.pdf": b"%PDF-1.4\n%%EOF",
            "/workspace/preview.pdf": b"%PDF-1.4\n%%EOF",
        }
    )
    registry = FakeRegistry(session)

    async def get_registry():
        return registry

    @asynccontextmanager
    async def db_session():
        yield object()

    @dataclass
    class Saved:
        status: str = "saved"
        document_id: int = 9
        title: str = "Facts"
        files: list = None

    captured = {}

    async def save_artifact(_session, **kwargs):
        captured.update(kwargs)
        return Saved(files=[])

    monkeypatch.setattr(save_tool, "get_registry", get_registry)
    monkeypatch.setattr(save_tool, "shielded_async_session", db_session)
    monkeypatch.setattr(save_tool, "save_artifact", save_artifact)
    monkeypatch.setattr(save_tool, "resolve_root_thread_id", lambda *_: 4)

    tool = save_tool.create_save_artifact_tool(3, 4)
    await tool.coroutine(
        title="Facts",
        markdown_representation="# Three facts",
        path="/workspace/out.pdf",
        preview_path="/workspace/preview.pdf",
        runtime=_runtime(),
    )

    assert [file.role for file in captured["files"]] == ["primary", "preview"]
    assert [file.mime_type for file in captured["files"]] == [
        "application/pdf",
        "application/pdf",
    ]


async def test_binary_save_enforces_file_cap(monkeypatch):
    monkeypatch.setattr(save_tool.app_config, "ARTIFACT_MAX_FILE_BYTES", 3)

    with pytest.raises(ValueError, match="limit"):
        await save_tool._read_artifact_file(
            FakeSession({"/workspace/out.pdf": b"%PDF"}),  # type: ignore[arg-type]
            "/workspace/out.pdf",
            "primary",
        )


async def test_inspect_images_batches_one_stubbed_vision_call(monkeypatch):
    jpeg = b"\xff\xd8\xff\xd9"
    session = FakeSession({"/tmp/page-1.jpg": jpeg, "/tmp/page-2.jpg": jpeg})
    captured = {}

    async def get_session(*_args):
        return session

    @asynccontextmanager
    async def db_session():
        yield object()

    class Vision:
        async def ainvoke(self, messages):
            captured["messages"] = messages
            return SimpleNamespace(content="Both pages are legible.")

    monkeypatch.setattr(sandbox_tools, "_get_session", get_session)
    monkeypatch.setattr(sandbox_tools, "shielded_async_session", db_session)
    monkeypatch.setattr(
        sandbox_tools, "get_vision_llm", AsyncMock(return_value=Vision())
    )

    tool = next(
        tool
        for tool in sandbox_tools.create_sandbox_tools(workspace_id=3, thread_id=4)
        if tool.name == "inspect_sandbox_images"
    )
    result = await tool.coroutine(
        paths=["/tmp/page-1.jpg", "/tmp/page-2.jpg"],
        instructions="Review the layout.",
        runtime=_runtime(),
    )

    assert result == "Both pages are legible."
    assert len(captured["messages"]) == 1
    assert len(captured["messages"][0].content) == 3


async def test_execute_truncates_and_preserves_full_output(monkeypatch):
    session = FakeSession({})

    async def execute(code: str, language: str = "python") -> ExecResult:
        return ExecResult("x" * (sandbox_tools._MAX_CONTEXT_CHARS + 1), 0)

    session.execute = execute  # type: ignore[attr-defined]

    async def get_session(*_args):
        return session

    monkeypatch.setattr(sandbox_tools, "_get_session", get_session)
    tool = next(
        tool
        for tool in sandbox_tools.create_sandbox_tools(workspace_id=3, thread_id=4)
        if tool.name == "execute"
    )

    result = await tool.coroutine(
        code_or_command="print('x')", language="python", runtime=_runtime()
    )

    assert "output truncated" in result
    assert "Full output:" in result
    assert next(iter(session.writes.values())).endswith(b"x")
