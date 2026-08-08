"""Sandbox tools used to author and verify binary deliverables."""

from __future__ import annotations

import asyncio
import base64
import shlex
import uuid
from pathlib import PurePosixPath
from typing import Literal

from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool, tool

from app.config import config as app_config
from app.db import shielded_async_session
from app.sandbox import SandboxSession, get_registry
from app.services.llm_service import get_vision_llm

from .thread_resolver import resolve_root_thread_id

_MAX_CONTEXT_CHARS = 16_000
_MAX_VISION_IMAGE_BYTES = 5 * 1024 * 1024
_MAX_VISION_IMAGES = 20


async def _get_session(
    workspace_id: int, thread_id: int | None, runtime: ToolRuntime
) -> SandboxSession:
    root_thread_id = resolve_root_thread_id(runtime, thread_id)
    return await (await get_registry()).get_session(root_thread_id, workspace_id)


def _result_text(output: str, exit_code: int, *, full_output_path: str | None) -> str:
    suffix = f"\n[Command exited with code {exit_code}]"
    if full_output_path:
        suffix += f"\n[Full output: {full_output_path}]"
    return output + suffix


def create_sandbox_tools(
    *, workspace_id: int, thread_id: int | None = None
) -> list[BaseTool]:
    """Build the three provider-agnostic sandbox tools."""

    @tool
    async def execute(
        code_or_command: str,
        runtime: ToolRuntime,
        language: Literal["python", "bash"] = "python",
    ) -> str:
        """Run Python or a Bash command in the sandbox.

        Write multi-step work to a source file and run that file: only some
        providers keep interpreter state between calls. Long output is
        truncated here and written in full to the returned sandbox path.
        """
        session = await _get_session(workspace_id, thread_id, runtime)
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

        Binary files must be persisted with save_artifact. Rendered JPEG pages
        must be reviewed with inspect_sandbox_images.
        """
        session = await _get_session(workspace_id, thread_id, runtime)
        size_result = await session.run_command(
            f"stat -c %s -- {shlex.quote(path)}"
        )
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
                "files or inspect_sandbox_images for rendered pages"
            )
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "read_sandbox_file accepts UTF-8 text only; use save_artifact for "
                "binary files"
            ) from exc

    @tool
    async def inspect_sandbox_images(
        paths: list[str],
        instructions: str,
        runtime: ToolRuntime,
    ) -> str:
        """Visually inspect rendered JPEG pages and return a text QA report."""
        if not paths or len(paths) > _MAX_VISION_IMAGES:
            raise ValueError(
                f"Provide between 1 and {_MAX_VISION_IMAGES} JPEG paths"
            )
        session = await _get_session(workspace_id, thread_id, runtime)
        content: list[dict] = [
            {
                "type": "text",
                "text": (
                    f"{instructions}\n\nInspect every attached page. Report layout, "
                    "overflow, clipping, illegible text, blank pages, alignment, "
                    "and factual inconsistencies. Identify pages by filename."
                ),
            }
        ]
        for path in paths:
            suffix = PurePosixPath(path).suffix.lower()
            if suffix not in {".jpg", ".jpeg"}:
                raise ValueError(f"Only JPEG page renders are supported: {path}")
            data = await session.read_file(path)
            if len(data) > _MAX_VISION_IMAGE_BYTES:
                raise ValueError(
                    f"Image {path} exceeds the {_MAX_VISION_IMAGE_BYTES}-byte limit"
                )
            encoded = base64.b64encode(data).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                }
            )

        async with shielded_async_session() as db_session:
            llm = await get_vision_llm(db_session, workspace_id)
        if llm is None:
            raise RuntimeError("No vision-capable model is configured for this workspace")
        response = await asyncio.wait_for(
            llm.ainvoke([HumanMessage(content=content)]), timeout=120
        )
        text = response.content if hasattr(response, "content") else str(response)
        if isinstance(text, list):
            text = "\n".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in text
            )
        if not str(text).strip():
            raise RuntimeError("Vision inspection returned no findings")
        return str(text).strip()

    return [execute, read_sandbox_file, inspect_sandbox_images]
