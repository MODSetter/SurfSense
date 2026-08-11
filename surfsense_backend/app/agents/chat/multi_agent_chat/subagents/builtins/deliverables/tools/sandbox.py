"""Sandbox tools used to author and verify binary deliverables."""

from __future__ import annotations

import asyncio
import base64
import shlex
import time
import uuid
from pathlib import PurePosixPath
from typing import Any, Literal

from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool, tool

from app.config import config as app_config
from app.db import shielded_async_session
from app.sandbox import SandboxSession, get_registry
from app.services.billable_calls import QuotaInsufficientError
from app.services.llm_service import get_vision_llm
from app.utils.perf import get_perf_logger

from .thread_resolver import resolve_root_thread_id
from .verification import record_verification

_MAX_CONTEXT_CHARS = 16_000
_MAX_VISION_IMAGE_BYTES = 5 * 1024 * 1024
_MAX_VISION_IMAGES = 20
_VISION_CONCURRENCY = 4
_VISION_TIMEOUT_SECONDS = 120
_VERIFIED_SENTINEL = "SURFSENSE_VERIFIED:"


async def _get_session(workspace_id: int, runtime: ToolRuntime) -> SandboxSession:
    root_thread_id = resolve_root_thread_id(runtime)
    return await (await get_registry()).get_session(root_thread_id, workspace_id)


def _sentinel_path(output: str) -> str | None:
    """Return the file a verification sentinel line names, if any.

    The token has to open a line and name a path: a run that merely prints the
    sentinel — a skill file being read out, say — must not be able to claim a
    verification it never performed.
    """
    for line in output.splitlines():
        if line.startswith(_VERIFIED_SENTINEL):
            path = line[len(_VERIFIED_SENTINEL) :].strip()
            if path:
                return path
    return None


def _result_text(output: str, exit_code: int, *, full_output_path: str | None) -> str:
    suffix = f"\n[Command exited with code {exit_code}]"
    if full_output_path:
        suffix += f"\n[Full output: {full_output_path}]"
    return output + suffix


def create_sandbox_tools(*, workspace_id: int) -> list[BaseTool]:
    """Build the three provider-agnostic sandbox tools."""

    vision_llm: Any = None
    vision_llm_resolved = False
    vision_llm_lock = asyncio.Lock()

    async def resolve_vision_llm() -> Any:
        nonlocal vision_llm, vision_llm_resolved
        if vision_llm_resolved:
            return vision_llm
        async with vision_llm_lock:
            if not vision_llm_resolved:
                async with shielded_async_session() as db_session:
                    vision_llm = await get_vision_llm(
                        db_session,
                        workspace_id,
                        usage_type="artifact_verification",
                    )
                vision_llm_resolved = True
        return vision_llm

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
        verified_path = _sentinel_path(result.output or "") if result.ok else None
        if verified_path is not None:
            await record_verification(session, "structural", path=verified_path)
        return _result_text(output, result.exit_code, full_output_path=full_output_path)

    @tool
    async def read_sandbox_file(path: str, runtime: ToolRuntime) -> str:
        """Read a UTF-8 text file from the sandbox.

        Binary files must be persisted with save_artifact. Rendered JPEG pages
        must be reviewed with inspect_sandbox_images.
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
        mode: Literal["each", "together"] = "each",
        description: str | None = None,
    ) -> str:
        """Visually inspect every rendered JPEG and return a text QA report.

        Use description for a short user-facing step title.
        """
        del description
        tool_started = time.perf_counter()
        if not paths:
            raise ValueError("Provide at least one JPEG path")
        for path in paths:
            if PurePosixPath(path).suffix.lower() not in {".jpg", ".jpeg"}:
                raise ValueError(f"Only JPEG page renders are supported: {path}")
        if mode == "together" and len(paths) == 1:
            return f"## {PurePosixPath(paths[0]).name}\nOnly one image; nothing to compare."

        session = await _get_session(workspace_id, runtime)
        llm = await resolve_vision_llm()
        if llm is None:
            reason = "No vision-capable model is configured for this workspace"
            await record_verification(session, "visual", reason=reason)
            return f"Visual verification could not run: {reason}."

        semaphore = asyncio.Semaphore(_VISION_CONCURRENCY)

        async def invoke(image_paths: list[str]) -> str:
            content: list[dict[str, Any]] = [
                {
                    "type": "text",
                    "text": (
                        f"{instructions}\n\nInspect every attached page. Report layout, "
                        "overflow, clipping, illegible text, blank pages, alignment, "
                        "and factual inconsistencies. Identify pages by filename."
                    ),
                }
            ]
            read_started = time.perf_counter()
            for path in image_paths:
                data = await session.read_file(path)
                if len(data) > _MAX_VISION_IMAGE_BYTES:
                    raise ValueError(
                        f"Image {path} exceeds the {_MAX_VISION_IMAGE_BYTES}-byte limit"
                    )
                content.append({"type": "text", "text": f"Filename: {path}"})
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                "data:image/jpeg;base64,"
                                + base64.b64encode(data).decode("ascii")
                            )
                        },
                    }
                )
            read_seconds = time.perf_counter() - read_started
            queued_at = time.perf_counter()
            async with semaphore:
                model_started = time.perf_counter()
                response = await asyncio.wait_for(
                    llm.ainvoke([HumanMessage(content=content)]),
                    timeout=_VISION_TIMEOUT_SECONDS,
                )
                model_seconds = time.perf_counter() - model_started
            # Splits the per-call cost into fetching pages out of the sandbox,
            # waiting on the concurrency gate, and the model itself, so a slow
            # verification round can be attributed rather than guessed at.
            get_perf_logger().info(
                "[inspect_sandbox_images] call images=%d read=%.1fs wait=%.1fs model=%.1fs",
                len(image_paths),
                read_seconds,
                model_started - queued_at,
                model_seconds,
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

        if mode == "each":
            groups = [[path] for path in paths]
        else:
            groups = []
            start = 0
            while start < len(paths):
                groups.append(paths[start : start + _MAX_VISION_IMAGES])
                if start + _MAX_VISION_IMAGES >= len(paths):
                    break
                # Retain one boundary page so adjacent pages are always compared.
                start += _MAX_VISION_IMAGES - 1

        results = await asyncio.gather(
            *(invoke(group) for group in groups),
            return_exceptions=True,
        )
        get_perf_logger().info(
            "[inspect_sandbox_images] mode=%s pages=%d calls=%d failed=%d in %.1fs",
            mode,
            len(paths),
            len(groups),
            sum(1 for result in results if isinstance(result, Exception)),
            time.perf_counter() - tool_started,
        )
        quota_failure = next(
            (
                result
                for result in results
                if isinstance(result, QuotaInsufficientError)
            ),
            None,
        )
        if quota_failure is not None:
            reason = f"Visual verification stopped because credit is insufficient: {quota_failure}"
            await record_verification(session, "visual", reason=reason)
        elif any(not isinstance(result, Exception) for result in results):
            await record_verification(session, "visual")

        reports = []
        for group, result in zip(groups, results, strict=True):
            label = (
                PurePosixPath(group[0]).name
                if len(group) == 1
                else f"{PurePosixPath(group[0]).name}-{PurePosixPath(group[-1]).name}"
            )
            if isinstance(result, Exception):
                reports.append(f"## {label}\nInspection failed: {result}")
            else:
                reports.append(f"## {label}\n{result}")
        return "\n\n".join(reports)

    return [execute, read_sandbox_file, inspect_sandbox_images]
