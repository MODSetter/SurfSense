from __future__ import annotations

import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools import (
    load_artifact_source as load_source_tool,
    sandbox as sandbox_tools,
    save_artifact as save_tool,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools.thread_resolver import (
    root_thread_id_from_config,
)
from app.artifacts.verification.receipt import (
    VerificationReceipt,
    sha256_bytes,
    write_receipt,
)
from app.sandbox import ExecResult
from tests.utils.fake_sandbox import FakeSandboxSession

SECRET = "test-secret"
WORKSPACE_ID = 3


def _sandbox(files: dict[str, bytes]) -> FakeSandboxSession:
    session: FakeSandboxSession

    def command_handler(command: str) -> ExecResult:
        path = command.split("-- ", 1)[1].strip("'")
        return ExecResult(str(len(session.files[path])), 0)

    session = FakeSandboxSession(files, command_handler=command_handler)
    return session


class FakeRegistry:
    def __init__(self, session: FakeSandboxSession) -> None:
        self.session = session

    async def get_session(self, thread_id, workspace_id):
        return self.session


@dataclass
class Saved:
    status: str = "saved"
    document_id: int = 9
    title: str = "Facts"
    files: list | None = None


def _runtime():
    return SimpleNamespace(
        tool_call_id="call-1",
        state={},
        config={"configurable": {"thread_id": "4::task:call-1"}},
    )


def _patch_save_tool(monkeypatch, session: FakeSandboxSession) -> dict:
    """Point the save tool at a fake sandbox and capture what it persists."""
    captured: dict = {}

    async def get_registry():
        return FakeRegistry(session)

    @asynccontextmanager
    async def db_session():
        yield object()

    async def save_artifact(_session, **kwargs):
        captured.update(kwargs)
        return Saved(files=[])

    monkeypatch.setattr(save_tool, "get_registry", get_registry)
    monkeypatch.setattr(save_tool, "shielded_async_session", db_session)
    monkeypatch.setattr(save_tool, "save_artifact", save_artifact)
    monkeypatch.setattr(save_tool, "resolve_root_thread_id", lambda *_: 4)
    monkeypatch.setattr(save_tool.app_config, "SECRET_KEY", SECRET)
    return captured


async def _add_receipt(
    session: FakeSandboxSession,
    primary_path: str,
    *,
    preview_path: str | None = None,
    unavailable_reason: str | None = None,
) -> None:
    await write_receipt(
        session,
        VerificationReceipt(
            workspace_id=WORKSPACE_ID,
            session_id=session.session_id,
            format=primary_path.rsplit(".", 1)[-1],
            primary_path=primary_path,
            primary_sha256=sha256_bytes(session.files[primary_path]),
            preview_path=preview_path,
            preview_sha256=(
                sha256_bytes(session.files[preview_path]) if preview_path else None
            ),
            page_count=1,
            visual="unavailable" if unavailable_reason else "clean",
            unavailable_reason=unavailable_reason,
            issued_at=int(time.time()),
        ),
        SECRET,
    )


def test_thread_resolution_requires_live_runtime_identity():
    assert (
        root_thread_id_from_config({"configurable": {"thread_id": "77::task:call-1"}})
        == 77
    )
    with pytest.raises(RuntimeError, match="unavailable"):
        root_thread_id_from_config({})


async def test_binary_save_reads_primary_and_preview_with_sniffed_roles(monkeypatch):
    session = _sandbox(
        {
            "/workspace/out.pdf": b"%PDF-1.4\n%%EOF",
            "/workspace/source.py": b"print('pdf')",
            "/workspace/preview.pdf": b"%PDF-1.4\n%%EOF",
        }
    )
    await _add_receipt(
        session,
        "/workspace/out.pdf",
        preview_path="/workspace/preview.pdf",
    )
    captured = _patch_save_tool(monkeypatch, session)

    tool = save_tool.create_save_artifact_tool(3)
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


async def test_binary_save_rejects_bytes_changed_after_verification(monkeypatch):
    session = _sandbox(
        {
            "/workspace/out.pdf": b"%PDF-1.4\n%%EOF",
            "/workspace/source.py": b"print('pdf')",
        }
    )
    await _add_receipt(session, "/workspace/out.pdf")
    session.files["/workspace/out.pdf"] = b"%PDF-1.4\nchanged\n%%EOF"
    _patch_save_tool(monkeypatch, session)
    tool = save_tool.create_save_artifact_tool(3)

    result = await tool.coroutine(
        title="Facts",
        markdown_representation="# Facts",
        path="/workspace/out.pdf",
        source_path="/workspace/source.py",
        runtime=_runtime(),
    )

    assert "changed after verification" in str(result)


async def test_binary_save_requires_a_signed_receipt(monkeypatch):
    session = _sandbox(
        {
            "/workspace/out.docx": b"PK\x03\x04",
            "/workspace/source.js": b"require('docx')",
        }
    )
    _patch_save_tool(monkeypatch, session)
    tool = save_tool.create_save_artifact_tool(3)

    result = await tool.coroutine(
        title="Facts",
        markdown_representation="# Facts",
        path="/workspace/out.docx",
        source_path="/workspace/source.js",
        runtime=_runtime(),
    )

    assert "has not been verified" in str(result)


async def test_receipt_must_name_the_saved_file(monkeypatch):
    session = _sandbox(
        {
            "/workspace/data.xlsx": b"PK\x03\x04",
            "/workspace/source.py": b"print('xlsx')",
        }
    )
    await _add_receipt(session, "/workspace/data.xlsx")
    envelope = session.files.pop("/tmp/.surfsense-artifact-verification.json")
    session.files["/workspace/copy.xlsx"] = session.files["/workspace/data.xlsx"]
    session.files["/tmp/.surfsense-artifact-verification.json"] = envelope
    _patch_save_tool(monkeypatch, session)
    tool = save_tool.create_save_artifact_tool(3)

    rejected = await tool.coroutine(
        title="Numbers",
        markdown_representation="# Numbers",
        path="/workspace/copy.xlsx",
        source_path="/workspace/source.py",
        runtime=_runtime(),
    )
    assert "changed after verification" in str(rejected)


async def test_binary_save_accepts_unavailable_verification_reason(monkeypatch):
    reason = "No vision-capable model is configured"
    session = _sandbox(
        {
            "/workspace/out.pdf": b"%PDF-1.4\n%%EOF",
            "/workspace/source.py": b"print('pdf')",
        }
    )
    await _add_receipt(
        session,
        "/workspace/out.pdf",
        unavailable_reason=reason,
    )
    captured = _patch_save_tool(monkeypatch, session)
    tool = save_tool.create_save_artifact_tool(3)

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
            _sandbox({"/workspace/out.pdf": b"%PDF"}),  # type: ignore[arg-type]
            "/workspace/out.pdf",
            "primary",
        )


def test_javascript_source_accepts_plain_text_sniff():
    assert save_tool._mime_types_compatible("application/javascript", "text/plain")
    assert save_tool._mime_types_compatible("text/javascript", "text/plain")


async def test_generated_file_requires_source_and_has_no_content_alias():
    tool = save_tool.create_save_artifact_tool(3)

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
        storage_backend="azure",
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

    resolved_backends = []

    def get_storage_backend(name):
        resolved_backends.append(name)
        return Backend()

    sandbox = _sandbox({})

    async def get_registry():
        return FakeRegistry(sandbox)

    monkeypatch.setattr(load_source_tool, "shielded_async_session", db_session)
    monkeypatch.setattr(load_source_tool, "get_storage_backend", get_storage_backend)
    monkeypatch.setattr(load_source_tool, "get_registry", get_registry)
    monkeypatch.setattr(load_source_tool, "resolve_root_thread_id", lambda *_: 4)

    tool = load_source_tool.create_load_artifact_source_tool(workspace_id=3)
    path = await tool.coroutine(document_id=9, runtime=_runtime())

    assert path == "/workspace/artifact-9-out.py"
    assert sandbox.writes[path] == b"print('stored')"
    assert resolved_backends == ["azure"]


async def test_execute_truncates_and_preserves_full_output(monkeypatch):
    session = _sandbox({})

    async def execute(code: str, language: str = "python") -> ExecResult:
        return ExecResult("x" * (sandbox_tools._MAX_CONTEXT_CHARS + 1), 0)

    session.execute = execute  # type: ignore[attr-defined]

    async def get_session(*_args):
        return session

    monkeypatch.setattr(sandbox_tools, "_get_session", get_session)
    tool = next(
        tool
        for tool in sandbox_tools.create_sandbox_tools(workspace_id=3)
        if tool.name == "execute"
    )

    result = await tool.coroutine(
        code_or_command="print('x')", language="python", runtime=_runtime()
    )

    assert "output truncated" in result
    assert "Full output:" in result
    assert next(iter(session.writes.values())).endswith(b"x")
