"""Sandbox tools used to author and verify binary deliverables."""

from __future__ import annotations

import shlex
import uuid
from typing import Literal

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, tool

from app.config import config as app_config
from app.sandbox import SandboxSession, get_registry

from .thread_resolver import resolve_root_thread_id

_MAX_CONTEXT_CHARS = 16_000


async def _get_session(workspace_id: int, runtime: ToolRuntime) -> SandboxSession:
    root_thread_id = resolve_root_thread_id(runtime)
    return await (await get_registry()).get_session(root_thread_id, workspace_id)


def _result_text(output: str, exit_code: int, *, full_output_path: str | None) -> str:
    suffix = f"\n[Command exited with code {exit_code}]"
    if full_output_path:
        suffix += f"\n[Full output: {full_output_path}]"
    return output + suffix


def create_sandbox_tools(*, workspace_id: int) -> list[BaseTool]:
    """Build the provider-agnostic authoring tools."""

    @tool
    async def execute(
        code_or_command: str,
        runtime: ToolRuntime,
        language: Literal["python", "bash"] = "python",
        description: str | None = None,
    ) -> str:
        """Run Python or a Bash command in the sandbox.

        Write multi-step work to a source file and run that file: only some
        providers keep interpreter state between calls. Long output is
        truncated here and written in full to the returned sandbox path. Use
        description for a short user-facing step title.
        """
        del description
        session = await _get_session(workspace_id, runtime)
        result = (
            await session.execute(code_or_command, language="python")
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

    return [execute, read_sandbox_file]
