"""Sandbox tools used to author and verify binary deliverables."""

from __future__ import annotations

import asyncio
import logging
import shlex
import uuid
from typing import Literal

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, tool

from app.capabilities.core import ActivityDescriptor
from app.config import config as app_config
from app.sandbox import ExecResult, SandboxSession, get_registry

from .thread_resolver import resolve_root_thread_id

_MAX_CONTEXT_CHARS = 16_000
_PROCESS_TERMINATION_GRACE_SECONDS = 5
_TRANSPORT_GRACE_SECONDS = 5

logger = logging.getLogger(__name__)


async def _get_session(workspace_id: int, runtime: ToolRuntime) -> SandboxSession:
    root_thread_id = resolve_root_thread_id(runtime)
    return await (await get_registry()).get_session(root_thread_id, workspace_id)


def _result_text(output: str, exit_code: int, *, full_output_path: str | None) -> str:
    suffix = f"\n[Command exited with code {exit_code}]"
    if full_output_path:
        suffix += f"\n[Full output: {full_output_path}]"
    return output + suffix


async def _run_python_script(
    session: SandboxSession,
    code: str,
) -> ExecResult:
    """Materialize agent-authored code and run it as one bounded process."""
    script_path = f"/tmp/.surfsense-exec-{uuid.uuid4().hex}.py"
    quoted_script = shlex.quote(script_path)
    operation_timeout = app_config.SANDBOX_OPERATION_TIMEOUT_SECONDS
    process_timeout = max(
        1,
        operation_timeout
        - _PROCESS_TERMINATION_GRACE_SECONDS
        - _TRANSPORT_GRACE_SECONDS,
    )
    await session.write_file(script_path, code.encode())
    command = (
        f"script={quoted_script}; "
        """trap 'rm -f -- "$script"' EXIT; """
        "cd -- /workspace && "
        "timeout --signal=TERM "
        f"--kill-after={_PROCESS_TERMINATION_GRACE_SECONDS}s {process_timeout}s "
        'python3 "$script"'
    )
    try:
        async with asyncio.timeout(operation_timeout):
            result = await session.run_command(command)
    except TimeoutError:
        raise TimeoutError(
            f"Sandbox Python execution exceeded {operation_timeout} seconds"
        ) from None
    finally:
        # The shell trap handles normal completion and provider-stream failures
        # after process exit. This fallback covers failures before the shell starts.
        try:
            async with asyncio.timeout(
                min(_PROCESS_TERMINATION_GRACE_SECONDS, operation_timeout)
            ):
                await session.run_command(f"rm -f -- {quoted_script}")
        except Exception:
            logger.warning("Could not remove temporary sandbox script", exc_info=True)

    if result.exit_code == 124:
        detail = f"Python execution exceeded {process_timeout} seconds"
        return ExecResult(
            output=f"{result.output}\n{detail}".lstrip(),
            exit_code=result.exit_code,
            truncated=result.truncated,
        )
    return result


def create_sandbox_tools(*, workspace_id: int) -> list[BaseTool]:
    """Build the provider-agnostic authoring tools."""

    @tool
    async def execute(
        code_or_command: str,
        runtime: ToolRuntime,
        language: Literal["python", "bash"] = "python",
    ) -> str:
        """Run Python or a Bash command in the sandbox.

        Each Python call runs as a fresh process; carry state between calls in
        files, not interpreter variables. Long output is truncated here and
        written in full to the returned sandbox path.
        """
        session = await _get_session(workspace_id, runtime)
        result = (
            await _run_python_script(session, code_or_command)
            if language == "python"
            else await session.run_command(code_or_command)
        )
        output = result.output or ""
        full_output_path = None
        if len(output) > _MAX_CONTEXT_CHARS:
            full_output_path = f"/tmp/surfsense-output-{uuid.uuid4().hex}.txt"
            await session.write_file(full_output_path, output.encode())
            output = output[:_MAX_CONTEXT_CHARS] + "\n… [output truncated]"
        return _result_text(output, result.exit_code, full_output_path=full_output_path)

    @tool
    async def load_artifact_instructions(
        artifact_type: Literal["pdf", "docx", "pptx", "xlsx"],
        runtime: ToolRuntime,
    ) -> str:
        """Load the trusted creation instructions for one artifact format."""
        session = await _get_session(workspace_id, runtime)
        result = await session.run_command(f"cat /opt/skills/{artifact_type}/SKILL.md")
        return _result_text(
            result.output or "", result.exit_code, full_output_path=None
        )

    @tool
    async def read_sandbox_file(path: str, runtime: ToolRuntime) -> str:
        """Read a UTF-8 text file from the sandbox.

        Binary files must be persisted with save_artifact.
        """
        session = await _get_session(workspace_id, runtime)
        size_result = await session.run_command(f"stat -c %s -- {shlex.quote(path)}")
        if not size_result.ok:
            raise FileNotFoundError(f"Could not stat sandbox file: {path}")
        try:
            size = int(size_result.output.strip())
        except ValueError as exc:
            raise FileNotFoundError(f"Could not stat sandbox file: {path}") from exc
        if size > app_config.ARTIFACT_MAX_FILE_BYTES:
            raise ValueError(
                f"Sandbox file is {size} bytes; limit is "
                f"{app_config.ARTIFACT_MAX_FILE_BYTES} bytes"
            )
        data = await session.read_file(path)
        if b"\x00" in data:
            raise ValueError(
                "read_sandbox_file accepts text only; use save_artifact for binary "
                "files"
            )
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "read_sandbox_file accepts UTF-8 text only; use save_artifact for "
                "binary files"
            ) from exc

    execute.metadata = {
        "activity_descriptor": ActivityDescriptor(
            active_title="Running command",
            completed_title="Ran command",
            category="action",
            icon_key="terminal",
            kind="execute",
        ).as_metadata()
    }
    read_sandbox_file.metadata = {
        "activity_descriptor": ActivityDescriptor(
            active_title="Reviewing the artifact",
            completed_title="Reviewed the artifact",
            category="artifact",
            icon_key="file-text",
            kind="read_sandbox_file",
            lifecycle="phase",
        ).as_metadata()
    }
    return [execute, load_artifact_instructions, read_sandbox_file]
