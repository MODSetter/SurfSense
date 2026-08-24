from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools import (
    load_artifact_for_revision as load_revision_tool,
    load_source_document as load_source_tool,
    sandbox as sandbox_tools,
    save_artifact as save_tool,
    verify_artifact as verify_tool,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools.thread_resolver import (
    root_thread_id_from_config,
)
from app.artifacts.persistence import ArtifactFileRole
from app.artifacts.verification.receipt import (
    VerificationReceipt,
    receipt_path,
    sha256_bytes,
    write_receipt,
)
from app.file_storage.persistence.enums import DocumentFileKind
from app.sandbox import ExecResult
from tests.utils.fake_sandbox import FakeSandboxSession

SECRET = "test-secret"
WORKSPACE_ID = 3


def _sandbox(files: dict[str, bytes]) -> FakeSandboxSession:
    session: FakeSandboxSession

    def command_handler(command: str) -> ExecResult:
        if command.startswith(("rm -f --", "mkdir -p --")):
            return ExecResult("", 0)
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
    artifact_id: int = 9
    generation: int = 1
    title: str = "Facts"
    files: list | None = None


def _runtime():
    return SimpleNamespace(
        tool_call_id="call-1",
        state={},
        config={"configurable": {"thread_id": "4::task:call-1"}},
    )


async def test_verify_tool_keeps_receipt_preview_path_backend_owned(monkeypatch):
    session = FakeSandboxSession({"/workspace/report.docx": b"docx"})

    async def get_registry():
        return FakeRegistry(session)

    @asynccontextmanager
    async def db_session():
        yield object()

    async def get_vision_llm(*_args, **_kwargs):
        return object()

    async def verify(*_args, **_kwargs):
        return SimpleNamespace(
            verified=True,
            findings=(),
            notes=(),
            preview_path="/tmp/backend-owned-preview.pdf",
            page_count=1,
            unavailable_reason=None,
        )

    monkeypatch.setattr(verify_tool, "get_registry", get_registry)
    monkeypatch.setattr(verify_tool, "shielded_async_session", db_session)
    monkeypatch.setattr(verify_tool, "get_vision_llm", get_vision_llm)
    monkeypatch.setattr(verify_tool, "verify", verify)
    monkeypatch.setattr(verify_tool, "resolve_root_thread_id", lambda *_args: 4)
    tool = verify_tool.create_verify_artifact_tool(workspace_id=WORKSPACE_ID)

    assert tool.coroutine is not None
    result = await tool.coroutine(
        path="/workspace/report.docx",
        runtime=_runtime(),
    )

    assert result["status"] == "verified"
    assert "preview_path" not in result


async def test_full_video_render_uses_gate_config_and_records_segments(monkeypatch):
    session = FakeSandboxSession(
        command_handler=lambda _command: ExecResult(
            "SURFSENSE_SEGMENT_SECONDS=1.25\nSURFSENSE_SEGMENT_COUNT=2",
            0,
        )
    )
    render_duration = []
    segment_counts = []
    monkeypatch.setattr(
        sandbox_tools.ot_metrics,
        "record_video_admission_wait",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        sandbox_tools.ot_metrics,
        "record_video_render_duration",
        lambda seconds, **kwargs: render_duration.append((seconds, kwargs)),
    )
    monkeypatch.setattr(
        sandbox_tools.ot_metrics,
        "record_video_segment_count",
        segment_counts.append,
    )

    result = await sandbox_tools._run_bash(
        session, "node render.mjs props.json /workspace/out.mp4"
    )

    assert result.ok
    assert "VIDEO_SANDBOX_MAX_FRAMES_PER_SEGMENT=" in session.commands[0]
    assert "VIDEO_SANDBOX_RENDER_FRAME_TIMEOUT_MS=" in session.commands[0]
    assert (1.25, {"scope": "segment"}) in render_duration
    assert segment_counts == [2]


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
    format_name: str | None = None,
) -> None:
    await write_receipt(
        session,
        VerificationReceipt(
            workspace_id=WORKSPACE_ID,
            session_id=session.session_id,
            format=format_name or primary_path.rsplit(".", 1)[-1],
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
        runtime=_runtime(),
    )

    assert [file.role for file in captured["files"]] == [
        "primary",
        "preview",
    ]
    assert [file.mime_type for file in captured["files"]] == [
        "application/pdf",
        "application/pdf",
    ]
    assert captured["extra_metadata"] == {
        "verification": {"verified": True, "reason": None}
    }
    assert captured["format"] == "pdf"


async def test_video_save_passes_a_stream_bound_to_receipt(monkeypatch):
    path = "/workspace/out.mp4"
    session = _sandbox(
        {
            path: b"large-video-bytes",
            f"{path}.segments.json": (
                b'{"render_workdir":"/workspace/video-render-1"}'
            ),
        }
    )
    await _add_receipt(session, path, format_name="video")
    captured = _patch_save_tool(monkeypatch, session)

    tool = save_tool.create_save_artifact_tool(WORKSPACE_ID)
    await tool.coroutine(
        title="Video",
        markdown_representation="# Video",
        path=path,
        runtime=_runtime(),
    )

    primary = captured["files"][0]
    assert primary.mime_type == "video/mp4"
    assert primary.expected_sha256 == sha256_bytes(b"large-video-bytes")
    assert b"".join([chunk async for chunk in primary.chunks]) == b"large-video-bytes"
    assert captured["format"] == "video"
    assert any(
        "/workspace/video-render-1" in command and path in command
        for command in session.commands
    )


async def test_binary_save_uses_receipt_for_its_own_artifact(monkeypatch):
    session = _sandbox(
        {
            "/workspace/report.pdf": b"%PDF-1.4\n%%EOF",
            "/workspace/report.docx": b"PK\x03\x04",
        }
    )
    await _add_receipt(session, "/workspace/report.pdf")
    await _add_receipt(session, "/workspace/report.docx")
    captured = _patch_save_tool(monkeypatch, session)

    tool = save_tool.create_save_artifact_tool(WORKSPACE_ID)
    result = await tool.coroutine(
        title="PDF report",
        markdown_representation="# Report",
        path="/workspace/report.pdf",
        runtime=_runtime(),
    )

    assert "another artifact format" not in str(result)
    assert captured["files"][0].filename == "report.pdf"


async def test_binary_save_rejects_bytes_changed_after_verification(monkeypatch):
    session = _sandbox(
        {
            "/workspace/out.pdf": b"%PDF-1.4\n%%EOF",
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
        runtime=_runtime(),
    )

    assert "changed after verification" in str(result)


async def test_binary_save_requires_a_signed_receipt(monkeypatch):
    session = _sandbox(
        {
            "/workspace/out.docx": b"PK\x03\x04",
        }
    )
    _patch_save_tool(monkeypatch, session)
    tool = save_tool.create_save_artifact_tool(3)

    result = await tool.coroutine(
        title="Facts",
        markdown_representation="# Facts",
        path="/workspace/out.docx",
        runtime=_runtime(),
    )

    assert "Verify this file again before presenting it" in str(result)


async def test_same_path_concurrent_saves_consume_one_receipt(monkeypatch):
    path = "/workspace/out.pdf"
    session = _sandbox({path: b"%PDF-1.4\n%%EOF"})
    await _add_receipt(session, path)
    _patch_save_tool(monkeypatch, session)
    calls = 0

    async def save_artifact(_session, **_kwargs):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return Saved(files=[])

    monkeypatch.setattr(save_tool, "save_artifact", save_artifact)
    tool = save_tool.create_save_artifact_tool(WORKSPACE_ID)

    results = await asyncio.gather(
        *(
            tool.coroutine(
                title="Facts",
                markdown_representation="# Facts",
                path=path,
                runtime=_runtime(),
            )
            for _ in range(2)
        )
    )

    assert calls == 1
    assert sum("Verify this file again" in str(result) for result in results) == 1


async def test_distinct_paths_save_independently(monkeypatch):
    paths = ("/workspace/a.pdf", "/workspace/b.pdf")
    session = _sandbox(dict.fromkeys(paths, b"%PDF-1.4\n%%EOF"))
    for path in paths:
        await _add_receipt(session, path)
    _patch_save_tool(monkeypatch, session)
    entered = 0
    both_entered = asyncio.Event()

    async def save_artifact(_session, **_kwargs):
        nonlocal entered
        entered += 1
        if entered == 2:
            both_entered.set()
        await asyncio.wait_for(both_entered.wait(), timeout=0.2)
        return Saved(files=[])

    monkeypatch.setattr(save_tool, "save_artifact", save_artifact)
    tool = save_tool.create_save_artifact_tool(WORKSPACE_ID)

    await asyncio.gather(
        *(
            tool.coroutine(
                title=path,
                markdown_representation=f"# {path}",
                path=path,
                runtime=_runtime(),
            )
            for path in paths
        )
    )

    assert entered == 2


async def test_receipt_must_name_the_saved_file(monkeypatch):
    session = _sandbox(
        {
            "/workspace/data.pdf": b"%PDF-1.4\n%%EOF",
        }
    )
    await _add_receipt(session, "/workspace/data.pdf")
    envelope = session.files[receipt_path("/workspace/data.pdf")]
    session.files["/workspace/copy.pdf"] = session.files["/workspace/data.pdf"]
    session.files[receipt_path("/workspace/copy.pdf")] = envelope
    _patch_save_tool(monkeypatch, session)
    tool = save_tool.create_save_artifact_tool(3)

    rejected = await tool.coroutine(
        title="Numbers",
        markdown_representation="# Numbers",
        path="/workspace/copy.pdf",
        runtime=_runtime(),
    )
    assert "changed after verification" in str(rejected)


async def test_receipt_must_name_the_saved_format(monkeypatch):
    session = _sandbox(
        {
            "/workspace/data.pdf": b"%PDF-1.4\n%%EOF",
        }
    )
    await _add_receipt(session, "/workspace/data.pdf", format_name="docx")
    _patch_save_tool(monkeypatch, session)
    tool = save_tool.create_save_artifact_tool(3)

    rejected = await tool.coroutine(
        title="Numbers",
        markdown_representation="# Numbers",
        path="/workspace/data.pdf",
        runtime=_runtime(),
    )

    assert "Verify this file again before presenting it" in str(rejected)


async def test_binary_save_accepts_unavailable_verification_reason(monkeypatch):
    reason = "No vision-capable model is configured"
    session = _sandbox(
        {
            "/workspace/out.pdf": b"%PDF-1.4\n%%EOF",
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


async def test_generated_file_schema_has_no_source_or_preview_paths():
    tool = save_tool.create_save_artifact_tool(3)

    assert "content" not in tool.args
    assert "source_path" not in tool.args
    assert "preview_path" not in tool.args


async def test_load_artifact_for_revision_writes_primary_and_markdown(monkeypatch):
    primary = SimpleNamespace(
        role=ArtifactFileRole.PRIMARY,
        size_bytes=16,
        storage_backend="azure",
        storage_key="primary-key",
        original_filename="out.pdf",
    )
    artifact = SimpleNamespace(
        generation=3,
        format="pdf",
        files=[primary],
        document=SimpleNamespace(
            source_markdown="# Current",
            content="# Current",
        ),
    )

    class DbSession:
        async def scalar(self, _statement):
            return artifact

    @asynccontextmanager
    async def db_session():
        yield DbSession()

    class Backend:
        async def open_stream(self, _key):
            yield b"%PDF stored"

    resolved_backends = []

    def get_storage_backend(name):
        resolved_backends.append(name)
        return Backend()

    sandbox = _sandbox({})

    async def get_registry():
        return FakeRegistry(sandbox)

    monkeypatch.setattr(load_revision_tool, "shielded_async_session", db_session)
    monkeypatch.setattr(load_revision_tool, "get_storage_backend", get_storage_backend)
    monkeypatch.setattr(load_revision_tool, "get_registry", get_registry)
    monkeypatch.setattr(load_revision_tool, "resolve_root_thread_id", lambda *_: 4)
    monkeypatch.setattr(
        load_revision_tool,
        "uuid4",
        lambda: SimpleNamespace(hex="invocation"),
    )

    tool = load_revision_tool.create_load_artifact_for_revision_tool(workspace_id=3)
    loaded = await tool.coroutine(artifact_id=9, runtime=_runtime())
    working_dir = "/workspace/artifact-revisions/9/invocation"

    assert loaded == {
        "artifact_id": 9,
        "format": "pdf",
        "primary_path": f"{working_dir}/current.pdf",
        "markdown_path": f"{working_dir}/context.md",
        "expected_output_path": f"{working_dir}/revised.pdf",
        "expected_generation": 3,
        "revision_instruction": load_revision_tool._REVISION_INSTRUCTIONS["pdf"],
        "save_instruction": (
            "Pass artifact_id=9 and expected_generation=3 to save_artifact so "
            "this revision replaces the existing artifact."
        ),
    }
    assert sandbox.writes[f"{working_dir}/current.pdf"] == b"%PDF stored"
    assert sandbox.writes[f"{working_dir}/context.md"] == b"# Current"
    assert resolved_backends == ["azure"]


def _patch_load_source_tool(monkeypatch, *, document, record, sandbox=None):
    """Point the source loader at a fake knowledge base, store, and sandbox."""

    @asynccontextmanager
    async def db_session():
        yield object()

    async def virtual_path_to_doc(_session, *, workspace_id, virtual_path):
        return document

    async def get_document_file(_session, *, document_id, kind):
        assert kind is DocumentFileKind.ORIGINAL
        return record

    def open_document_file_stream(_record):
        async def stream():
            yield b"PK\x03\x04"
            yield b"pptx-bytes"

        return stream()

    async def get_registry():
        return FakeRegistry(sandbox)

    monkeypatch.setattr(load_source_tool, "shielded_async_session", db_session)
    monkeypatch.setattr(load_source_tool, "virtual_path_to_doc", virtual_path_to_doc)
    monkeypatch.setattr(load_source_tool, "get_document_file", get_document_file)
    monkeypatch.setattr(
        load_source_tool, "open_document_file_stream", open_document_file_stream
    )
    monkeypatch.setattr(load_source_tool, "get_registry", get_registry)
    monkeypatch.setattr(load_source_tool, "resolve_root_thread_id", lambda *_: 4)


async def test_load_source_document_lands_the_upload_under_its_real_extension(
    monkeypatch,
):
    sandbox = _sandbox({})
    _patch_load_source_tool(
        monkeypatch,
        document=SimpleNamespace(id=7),
        record=SimpleNamespace(
            size_bytes=14,
            original_filename="rohan-verma-resume.pptx",
            mime_type="application/vnd.openxmlformats-officedocument."
            "presentationml.presentation",
        ),
        sandbox=sandbox,
    )

    tool = load_source_tool.create_load_source_document_tool(workspace_id=3)
    loaded = await tool.coroutine(
        path="/documents/rohan-verma-resume.pptx.xml",
        runtime=_runtime(),
    )

    # LibreOffice and python-pptx dispatch on the extension, so the `.xml` the
    # knowledge base appends to the title must not reach the sandbox path.
    assert loaded["source_path"] == "/workspace/sources/7/source.pptx"
    assert loaded["filename"] == "rohan-verma-resume.pptx"
    assert sandbox.writes["/workspace/sources/7/source.pptx"] == b"PK\x03\x04pptx-bytes"


async def test_load_source_document_keeps_a_hostile_filename_out_of_the_path(
    monkeypatch,
):
    sandbox = _sandbox({})
    _patch_load_source_tool(
        monkeypatch,
        document=SimpleNamespace(id=7),
        record=SimpleNamespace(
            size_bytes=14,
            original_filename="../../etc/passwd.pptx",
            mime_type=None,
        ),
        sandbox=sandbox,
    )

    tool = load_source_tool.create_load_source_document_tool(workspace_id=3)
    loaded = await tool.coroutine(path="/documents/x.pptx.xml", runtime=_runtime())

    assert loaded["source_path"] == "/workspace/sources/7/source.pptx"
    assert list(sandbox.writes) == ["/workspace/sources/7/source.pptx"]


async def test_load_source_document_sends_authored_content_to_the_text_route(
    monkeypatch,
):
    _patch_load_source_tool(monkeypatch, document=SimpleNamespace(id=9), record=None)

    tool = load_source_tool.create_load_source_document_tool(workspace_id=3)

    with pytest.raises(ValueError, match="knowledge_base"):
        await tool.coroutine(path="/documents/Notes.md", runtime=_runtime())


async def test_execute_python_uses_unique_one_shot_scripts_and_cleans_up(monkeypatch):
    commands: list[str] = []
    session = FakeSandboxSession({})

    async def run_command(command: str) -> ExecResult:
        commands.append(command)
        return ExecResult("created", 0)

    session.run_command = run_command  # type: ignore[method-assign]
    ids = iter(("first", "second"))
    monkeypatch.setattr(
        sandbox_tools.uuid,
        "uuid4",
        lambda: SimpleNamespace(hex=next(ids)),
    )

    async def get_session(*_args):
        return session

    monkeypatch.setattr(sandbox_tools, "_get_session", get_session)
    tool = next(
        tool
        for tool in sandbox_tools.create_sandbox_tools(workspace_id=3)
        if tool.name == "execute"
    )

    first = await tool.coroutine(
        code_or_command="print('first')", language="python", runtime=_runtime()
    )
    second = await tool.coroutine(
        code_or_command="print('second')", language="python", runtime=_runtime()
    )

    assert "created" in first
    assert "created" in second
    assert session.writes == {
        "/tmp/.surfsense-exec-first.py": b"print('first')",
        "/tmp/.surfsense-exec-second.py": b"print('second')",
    }
    execution_commands = [
        command for command in commands if command.startswith("script=")
    ]
    assert len(execution_commands) == 2
    assert "/tmp/.surfsense-exec-first.py" in execution_commands[0]
    assert "/tmp/.surfsense-exec-second.py" in execution_commands[1]
    assert all("cd -- /workspace" in command for command in execution_commands)
    assert all("code-interpreter-env.sh" in command for command in execution_commands)
    assert all(
        "timeout --signal=TERM --kill-after=5s" in command
        for command in execution_commands
    )
    assert [command for command in commands if command.startswith("rm -f --")] == [
        "rm -f -- /tmp/.surfsense-exec-first.py",
        "rm -f -- /tmp/.surfsense-exec-second.py",
    ]


async def test_execute_python_cleans_up_when_command_fails(monkeypatch):
    commands: list[str] = []
    session = FakeSandboxSession({})

    async def run_command(command: str) -> ExecResult:
        commands.append(command)
        if command.startswith("script="):
            raise RuntimeError("provider failed")
        return ExecResult("", 0)

    session.run_command = run_command  # type: ignore[method-assign]
    monkeypatch.setattr(
        sandbox_tools.uuid,
        "uuid4",
        lambda: SimpleNamespace(hex="failed"),
    )

    with pytest.raises(RuntimeError, match="provider failed"):
        await sandbox_tools._run_python_script(session, "raise RuntimeError")

    assert commands[-1] == "rm -f -- /tmp/.surfsense-exec-failed.py"


async def test_execute_python_returns_before_provider_stream_can_wedge(monkeypatch):
    session = FakeSandboxSession({})

    async def run_command(command: str) -> ExecResult:
        if command.startswith("rm -f --"):
            return ExecResult("", 0)
        await asyncio.sleep(1)
        return ExecResult("", 0)

    session.run_command = run_command  # type: ignore[method-assign]
    monkeypatch.setattr(
        sandbox_tools.app_config, "SANDBOX_OPERATION_TIMEOUT_SECONDS", 0.01
    )

    with pytest.raises(TimeoutError, match="exceeded"):
        await sandbox_tools._run_python_script(session, "print('never returned')")


async def test_execute_python_reports_process_timeout(monkeypatch):
    session = FakeSandboxSession({})

    async def run_command(command: str) -> ExecResult:
        return (
            ExecResult("partial output", 124)
            if command.startswith("script=")
            else ExecResult("", 0)
        )

    session.run_command = run_command  # type: ignore[method-assign]
    monkeypatch.setattr(
        sandbox_tools.app_config, "SANDBOX_OPERATION_TIMEOUT_SECONDS", 27
    )

    result = await sandbox_tools._run_python_script(session, "while True: pass")

    assert result.exit_code == 124
    assert result.output == "partial output\nPython execution exceeded 17 seconds"


async def test_execute_truncates_and_preserves_full_output(monkeypatch):
    session = FakeSandboxSession({})

    async def run_command(command: str) -> ExecResult:
        if command.startswith("script="):
            return ExecResult("x" * (sandbox_tools._MAX_CONTEXT_CHARS + 1), 0)
        return ExecResult("", 0)

    session.run_command = run_command  # type: ignore[method-assign]

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
    output = next(
        data
        for path, data in session.writes.items()
        if path.startswith("/tmp/surfsense-output-")
    )
    assert output.endswith(b"x")


async def test_execute_bash_remains_a_direct_command(monkeypatch):
    session = FakeSandboxSession(
        {}, command_handler=lambda command: ExecResult(command, 0)
    )

    async def get_session(*_args):
        return session

    monkeypatch.setattr(sandbox_tools, "_get_session", get_session)
    tool = next(
        tool
        for tool in sandbox_tools.create_sandbox_tools(workspace_id=3)
        if tool.name == "execute"
    )

    result = await tool.coroutine(
        code_or_command="printf done", language="bash", runtime=_runtime()
    )

    assert session.commands == ["printf done"]
    assert result.startswith("printf done")


async def test_load_artifact_instructions_uses_the_structured_format(monkeypatch):
    commands: list[str] = []

    def command_handler(command: str) -> ExecResult:
        commands.append(command)
        return ExecResult("trusted instructions", 0)

    session = FakeSandboxSession({}, command_handler=command_handler)

    async def get_session(*_args):
        return session

    monkeypatch.setattr(sandbox_tools, "_get_session", get_session)
    tool = next(
        tool
        for tool in sandbox_tools.create_sandbox_tools(workspace_id=3)
        if tool.name == "load_artifact_instructions"
    )

    result = await tool.coroutine(artifact_type="pdf", runtime=_runtime())

    assert commands == ["cat /opt/skills/pdf/SKILL.md"]
    assert result.startswith("trusted instructions")
