from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools import (
    load_artifact_source as load_source_tool,
    sandbox as sandbox_tools,
    save_artifact as save_tool,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools.verification import (
    LEDGER_PATH,
)
from app.sandbox import ExecResult


class FakeSession:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.writes: dict[str, bytes] = {}
        self.verification_status: str | None = None

    async def read_file(self, path: str) -> bytes:
        return self.files[path]

    async def write_file(self, path: str, data: bytes) -> None:
        self.writes[path] = data
        self.files[path] = data

    async def run_command(self, command: str) -> ExecResult:
        if command.startswith("if [ ! -e"):
            status = self.verification_status or (
                "CURRENT" if LEDGER_PATH in self.files else "MISSING"
            )
            return ExecResult(status, 0)
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
            "/workspace/source.py": b"print('pdf')",
            "/workspace/preview.pdf": b"%PDF-1.4\n%%EOF",
            LEDGER_PATH: b'{"reason":null}',
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
        source_path="/workspace/source.py",
        preview_path="/workspace/preview.pdf",
        runtime=_runtime(),
    )

    assert [file.role for file in captured["files"]] == [
        "primary",
        "source",
        "preview",
    ]
    assert [file.mime_type for file in captured["files"]] == [
        "application/pdf",
        "text/x-python",
        "application/pdf",
    ]
    assert captured["extra_metadata"] == {
        "verification": {"verified": True, "reason": None}
    }


async def test_binary_save_rejects_stale_verification(monkeypatch):
    session = FakeSession(
        {
            "/workspace/out.pdf": b"%PDF-1.4\n%%EOF",
            "/workspace/source.py": b"print('pdf')",
            LEDGER_PATH: b'{"reason":null}',
        }
    )
    session.verification_status = "STALE"

    async def get_registry():
        return FakeRegistry(session)

    monkeypatch.setattr(save_tool, "get_registry", get_registry)
    monkeypatch.setattr(save_tool, "resolve_root_thread_id", lambda *_: 4)
    tool = save_tool.create_save_artifact_tool(3, 4)

    result = await tool.coroutine(
        title="Facts",
        markdown_representation="# Facts",
        path="/workspace/out.pdf",
        source_path="/workspace/source.py",
        runtime=_runtime(),
    )

    assert "changed after its last verification" in str(result)


async def test_binary_save_accepts_unavailable_verification_reason(monkeypatch):
    reason = "No vision-capable model is configured"
    session = FakeSession(
        {
            "/workspace/out.pdf": b"%PDF-1.4\n%%EOF",
            "/workspace/source.py": b"print('pdf')",
            LEDGER_PATH: ('{"reason":"' + reason + '"}').encode(),
        }
    )
    captured = {}

    async def get_registry():
        return FakeRegistry(session)

    @asynccontextmanager
    async def db_session():
        yield object()

    @dataclass
    class Saved:
        status: str = "saved"
        document_id: int = 9
        title: str = "Facts"
        files: list = None

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
        markdown_representation="# Facts",
        path="/workspace/out.pdf",
        source_path="/workspace/source.py",
        runtime=_runtime(),
    )

    assert captured["extra_metadata"] == {
        "verification": {"verified": False, "reason": reason}
    }


async def test_binary_save_enforces_file_cap(monkeypatch):
    monkeypatch.setattr(save_tool.app_config, "ARTIFACT_MAX_FILE_BYTES", 3)

    with pytest.raises(ValueError, match="limit"):
        await save_tool._read_artifact_file(
            FakeSession({"/workspace/out.pdf": b"%PDF"}),  # type: ignore[arg-type]
            "/workspace/out.pdf",
            "primary",
        )


def test_javascript_source_accepts_plain_text_sniff():
    assert save_tool._mime_types_compatible(
        "application/javascript", "text/plain"
    )
    assert save_tool._mime_types_compatible("text/javascript", "text/plain")


async def test_generated_file_requires_source_and_has_no_content_alias():
    tool = save_tool.create_save_artifact_tool(3, 4)

    assert "content" not in tool.args
    result = await tool.coroutine(
        title="Facts",
        markdown_representation="# Facts",
        path="/workspace/out.pdf",
        runtime=_runtime(),
    )

    assert "source_path is required" in str(result)


async def test_load_artifact_source_writes_stored_bytes_to_sandbox(monkeypatch):
    document = SimpleNamespace(document_metadata={"generated": True})
    source = SimpleNamespace(
        size_bytes=16,
        storage_key="source-key",
        original_filename="out.py",
    )

    class DbSession:
        calls = 0

        async def scalar(self, _statement):
            self.calls += 1
            return document if self.calls == 1 else source

    @asynccontextmanager
    async def db_session():
        yield DbSession()

    class Backend:
        async def open_stream(self, _key):
            yield b"print('stored')"

    sandbox = FakeSession({})

    async def get_registry():
        return FakeRegistry(sandbox)

    monkeypatch.setattr(load_source_tool, "shielded_async_session", db_session)
    monkeypatch.setattr(load_source_tool, "get_storage_backend", Backend)
    monkeypatch.setattr(load_source_tool, "get_registry", get_registry)
    monkeypatch.setattr(load_source_tool, "resolve_root_thread_id", lambda *_: 4)

    tool = load_source_tool.create_load_artifact_source_tool(
        workspace_id=3, thread_id=4
    )
    path = await tool.coroutine(document_id=9, runtime=_runtime())

    assert path == "/workspace/artifact-9-out.py"
    assert sandbox.writes[path] == b"print('stored')"


async def test_inspect_images_reviews_each_page_and_resolves_llm_once(monkeypatch):
    jpeg = b"\xff\xd8\xff\xd9"
    paths = [f"/tmp/page-{number}.jpg" for number in range(25)]
    session = FakeSession(dict.fromkeys(paths, jpeg))
    calls: list[int] = []

    async def get_session(*_args):
        return session

    @asynccontextmanager
    async def db_session():
        yield object()

    class Vision:
        async def ainvoke(self, messages):
            calls.append(
                sum(
                    part.get("type") == "image_url"
                    for part in messages[0].content
                )
            )
            return SimpleNamespace(content="Page is legible.")

    get_llm = AsyncMock(return_value=Vision())
    monkeypatch.setattr(sandbox_tools, "_get_session", get_session)
    monkeypatch.setattr(sandbox_tools, "shielded_async_session", db_session)
    monkeypatch.setattr(sandbox_tools, "get_vision_llm", get_llm)

    tool = next(
        tool
        for tool in sandbox_tools.create_sandbox_tools(workspace_id=3, thread_id=4)
        if tool.name == "inspect_sandbox_images"
    )
    result = await tool.coroutine(
        paths=paths,
        instructions="Review the layout.",
        runtime=_runtime(),
    )

    assert result.count("Page is legible.") == 25
    assert calls == [1] * 25
    get_llm.assert_awaited_once()

    together = await tool.coroutine(
        paths=paths,
        instructions="Compare the pages.",
        mode="together",
        runtime=_runtime(),
    )
    assert len(together.split("\n\n")) == 2
    assert calls[-2:] == [20, 6]
    get_llm.assert_awaited_once()

    before = len(calls)
    single = await tool.coroutine(
        paths=[paths[0]],
        instructions="Compare the pages.",
        mode="together",
        runtime=_runtime(),
    )
    assert "nothing to compare" in single
    assert len(calls) == before


async def test_inspect_images_isolates_page_failures(monkeypatch):
    paths = ["/tmp/page-1.jpg", "/tmp/page-2.jpg"]
    session = FakeSession(dict.fromkeys(paths, b"\xff\xd8\xff\xd9"))

    async def get_session(*_args):
        return session

    @asynccontextmanager
    async def db_session():
        yield object()

    class Vision:
        calls = 0

        async def ainvoke(self, _messages):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("provider failed")
            return SimpleNamespace(content="Page is clean.")

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
        paths=paths, instructions="Review.", runtime=_runtime()
    )

    assert "Inspection failed: provider failed" in result
    assert "Page is clean." in result


async def test_inspect_images_records_unavailable_vision(monkeypatch):
    session = FakeSession({"/tmp/page.jpg": b"\xff\xd8\xff\xd9"})

    async def get_session(*_args):
        return session

    @asynccontextmanager
    async def db_session():
        yield object()

    monkeypatch.setattr(sandbox_tools, "_get_session", get_session)
    monkeypatch.setattr(sandbox_tools, "shielded_async_session", db_session)
    monkeypatch.setattr(
        sandbox_tools, "get_vision_llm", AsyncMock(return_value=None)
    )
    tool = next(
        tool
        for tool in sandbox_tools.create_sandbox_tools(workspace_id=3, thread_id=4)
        if tool.name == "inspect_sandbox_images"
    )

    result = await tool.coroutine(
        paths=["/tmp/page.jpg"], instructions="Review.", runtime=_runtime()
    )

    assert "could not run" in result
    assert b"No vision-capable model" in session.files[LEDGER_PATH]


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


async def test_execute_records_clean_verification_sentinel(monkeypatch):
    session = FakeSession({})

    async def execute(_code: str, language: str = "python") -> ExecResult:
        return ExecResult("ok\nSURFSENSE_VERIFIED: /workspace/out.pdf", 0)

    session.execute = execute  # type: ignore[attr-defined]

    async def get_session(*_args):
        return session

    monkeypatch.setattr(sandbox_tools, "_get_session", get_session)
    tool = next(
        tool
        for tool in sandbox_tools.create_sandbox_tools(workspace_id=3, thread_id=4)
        if tool.name == "execute"
    )

    await tool.coroutine(
        code_or_command="check_pdf.py out.pdf",
        language="python",
        runtime=_runtime(),
    )

    assert session.files[LEDGER_PATH] == b'{"reason":null}'
