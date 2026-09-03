"""Sandbox tools used to author and verify binary deliverables."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import shlex
import time
import uuid
from pathlib import PurePosixPath
from typing import Literal

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, tool

from app.agents.chat.multi_agent_chat.subagents.shared.hitl.questions import (
    StructuredQuestion,
    StructuredQuestionInterrupt,
    StructuredQuestionOption,
    StructuredQuestionOrigin,
    StructuredQuestionRespond,
    is_cancelled,
    request_structured_questions,
    selected_option_id,
)
from app.artifacts.infographic.generation import generate_infographic
from app.artifacts.infographic.presets import (
    AUTO_STYLE_ID,
    QUESTION_PRESET_ID,
    QUESTION_PRESET_VERSION,
    VISUAL_STYLE_PRESETS,
    get_visual_style,
    resolve_visual_style,
)
from app.artifacts.infographic.selection import (
    InfographicGenerationState,
    issue_selection_token,
    read_generation_state,
    read_selection_token,
    selection_digest,
    write_generation_state,
)
from app.capabilities.core import ActivityDescriptor
from app.config import config as app_config
from app.db import shielded_async_session
from app.observability.domains import media
from app.sandbox import ExecResult, SandboxSession, get_registry

from .thread_resolver import resolve_root_thread_id

_MAX_CONTEXT_CHARS = 16_000
_PROCESS_TERMINATION_GRACE_SECONDS = 5
_TRANSPORT_GRACE_SECONDS = 5
_VIDEO_RENDER_GATE = asyncio.Semaphore(
    max(1, app_config.VIDEO_SANDBOX_MAX_CONCURRENT_RENDERS)
)
_VIDEO_SEGMENTS_RE = re.compile(r"SURFSENSE_SEGMENT_COUNT=(\d+)")
_VIDEO_SEGMENT_SECONDS_RE = re.compile(r"SURFSENSE_SEGMENT_SECONDS=([0-9.]+)")
_video_render_waiters = 0

logger = logging.getLogger(__name__)


async def _get_session(
    workspace_id: int,
    runtime: ToolRuntime,
) -> SandboxSession:
    return await (await get_registry()).get_session(
        resolve_root_thread_id(runtime), workspace_id
    )


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
        ". /opt/code-interpreter/code-interpreter-env.sh python "
        '"${PYTHON_VERSION:-3.12}" >/dev/null 2>&1 && '
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


def _is_full_video_render(command: str) -> bool:
    return "render.mjs" in command and "--stills" not in command


async def _run_bash(session: SandboxSession, command: str) -> ExecResult:
    if "render.mjs" not in command:
        return await session.run_command(command)
    command = (
        f"export VIDEO_SANDBOX_MAX_FRAMES_PER_SEGMENT="
        f"{app_config.VIDEO_SANDBOX_MAX_FRAMES_PER_SEGMENT} "
        f"VIDEO_SANDBOX_RENDER_FRAME_TIMEOUT_MS="
        f"{app_config.VIDEO_SANDBOX_RENDER_FRAME_TIMEOUT_MS}; {command}"
    )
    if not _is_full_video_render(command):
        return await session.run_command(command)

    global _video_render_waiters
    queued_at = time.monotonic()
    _video_render_waiters += 1
    queue_depth = max(
        0,
        _video_render_waiters - app_config.VIDEO_SANDBOX_MAX_CONCURRENT_RENDERS,
    )
    try:
        await _VIDEO_RENDER_GATE.acquire()
    finally:
        _video_render_waiters -= 1
    media.record_video_admission_wait(
        time.monotonic() - queued_at,
        queue_depth=queue_depth,
    )
    started_at = time.monotonic()
    try:
        result = await session.run_command(command)
    finally:
        _VIDEO_RENDER_GATE.release()
        media.record_video_render_duration(time.monotonic() - started_at)
    match = _VIDEO_SEGMENTS_RE.search(result.output)
    for seconds in _VIDEO_SEGMENT_SECONDS_RE.findall(result.output):
        media.record_video_render_duration(float(seconds), scope="segment")
    media.record_video_segment_count(int(match.group(1)) if match else 1)
    return result


async def _generate_infographic_file(
    *,
    session: SandboxSession,
    workspace_id: int,
    thread_id: int,
    factual_markdown: str,
    output_path: str | None,
    selection_token: str | None,
    output_constraints: str | None,
    repair_findings: list[str] | None,
) -> str:
    if not selection_token:
        raise ValueError(
            "Load infographic instructions and complete the style question first"
        )
    if not output_path:
        raise ValueError("output_path is required for infographic generation")
    path = PurePosixPath(output_path)
    workspace = PurePosixPath("/workspace")
    if (
        path.suffix.lower() != ".png"
        or not path.is_absolute()
        or not path.is_relative_to(workspace)
    ):
        raise ValueError("Infographic output_path must be a .png file under /workspace")

    selection = read_selection_token(
        selection_token,
        workspace_id=workspace_id,
        thread_id=thread_id,
        secret_key=app_config.SECRET_KEY,
    )
    digest = selection_digest(selection_token)
    previous = await read_generation_state(
        session,
        output_path,
        workspace_id=workspace_id,
        secret_key=app_config.SECRET_KEY,
    )
    if previous is not None:
        if previous.selection_digest != digest:
            raise ValueError("Infographic repair must reuse the selected visual style")
        if previous.attempts >= 2:
            raise ValueError("Infographic generation permits only one repair attempt")
        if not repair_findings:
            raise ValueError("Infographic repair requires verification findings")
    attempts = 1 if previous is None else previous.attempts + 1

    style = get_visual_style(selection.resolved_style_id)
    async with shielded_async_session() as db_session:
        generated = await generate_infographic(
            db_session,
            workspace_id=workspace_id,
            factual_content=factual_markdown,
            style=style,
            output_constraints=output_constraints,
            repair_findings=tuple(repair_findings or ()),
        )

    markdown_path = str(path.with_suffix(".md"))
    markdown_bytes = factual_markdown.encode("utf-8")
    await session.write_file(output_path, generated.png)
    await session.write_file(markdown_path, markdown_bytes)
    state = InfographicGenerationState(
        workspace_id=workspace_id,
        session_id=session.session_id,
        output_path=output_path,
        selection_digest=digest,
        attempts=attempts,
        png_sha256=hashlib.sha256(generated.png).hexdigest(),
        markdown_sha256=hashlib.sha256(markdown_bytes).hexdigest(),
        requested_style_id=selection.requested_style_id,
        resolved_style_id=selection.resolved_style_id,
        preset_id=selection.preset_id,
        preset_version=selection.preset_version,
        image_gen_model_id=generated.image_gen_model_id,
        provider_model=generated.provider_model,
        width=generated.width,
        height=generated.height,
        issued_at=int(time.time()),
    )
    await write_generation_state(
        session,
        state,
        secret_key=app_config.SECRET_KEY,
    )
    return json.dumps(
        {
            "status": "generated",
            "path": output_path,
            "markdown_path": markdown_path,
            "format": "infographic",
            "attempt": attempts,
            "requested_style_id": selection.requested_style_id,
            "resolved_style_id": selection.resolved_style_id,
            "width": generated.width,
            "height": generated.height,
        },
        sort_keys=True,
    )


def create_sandbox_tools(*, workspace_id: int) -> list[BaseTool]:
    """Build the provider-agnostic authoring tools."""

    @tool
    async def execute(
        code_or_command: str,
        runtime: ToolRuntime,
        language: Literal["python", "bash", "infographic"] = "python",
        output_path: str | None = None,
        infographic_selection_token: str | None = None,
        output_constraints: str | None = None,
        repair_findings: list[str] | None = None,
    ) -> str:
        """Run Python or a Bash command in the sandbox.

        Each Python call runs as a fresh process; carry state between calls in
        files, not interpreter variables. For an infographic, pass canonical
        factual Markdown as code_or_command, the trusted selection token from
        load_artifact_instructions or load_artifact_for_revision, and a .png
        output_path. A second infographic call is allowed only with the
        verification findings for one repair.
        """
        session = await _get_session(workspace_id, runtime)
        if language == "infographic":
            return await _generate_infographic_file(
                session=session,
                workspace_id=workspace_id,
                thread_id=resolve_root_thread_id(runtime),
                factual_markdown=code_or_command,
                output_path=output_path,
                selection_token=infographic_selection_token,
                output_constraints=output_constraints,
                repair_findings=repair_findings,
            )
        result = (
            await _run_python_script(session, code_or_command)
            if language == "python"
            else await _run_bash(session, code_or_command)
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
        artifact_type: Literal[
            "pdf",
            "docx",
            "pptx",
            "xlsx",
            "html",
            "mindmap",
            "flashcards",
            "quiz",
            "video",
            "infographic",
        ],
        runtime: ToolRuntime,
        brief: str | None = None,
    ) -> str:
        """Load trusted creation instructions; infographics first ask for a style.

        For an infographic, provide a concise factual brief used only to resolve
        the Auto choice. The preset question runs before sandbox, billing, model
        calls, or file writes.
        """
        selection_token = None
        resolved = None
        if artifact_type == "infographic":
            question = StructuredQuestionInterrupt(
                title="Choose an infographic style",
                message="Select a visual direction before the infographic is generated.",
                origin=StructuredQuestionOrigin(
                    kind="preset",
                    preset_id=QUESTION_PRESET_ID,
                    preset_version=QUESTION_PRESET_VERSION,
                ),
                questions=(
                    StructuredQuestion(
                        id="visual-style",
                        prompt="Which visual style should be used?",
                        input_type="single_select",
                        presentation="visual_cards",
                        options=(
                            StructuredQuestionOption(
                                id=AUTO_STYLE_ID,
                                label="Auto",
                                description=(
                                    "Choose a style deterministically from the "
                                    "infographic brief."
                                ),
                                preview_asset="infographic-style/auto",
                            ),
                            *(
                                StructuredQuestionOption(
                                    id=preset.id,
                                    label=preset.label,
                                    description=preset.description,
                                    preview_asset=preset.preview_asset,
                                )
                                for preset in VISUAL_STYLE_PRESETS
                            ),
                        ),
                    ),
                ),
            )
            response = request_structured_questions(question)
            if is_cancelled(response):
                return "Infographic creation was cancelled by the user."
            if not isinstance(response, StructuredQuestionRespond):
                raise ValueError("Infographic style response is invalid")
            requested_style_id = selected_option_id(response, "visual-style")
            resolved = resolve_visual_style(requested_style_id, brief or "")
            selection_token = issue_selection_token(
                workspace_id=workspace_id,
                thread_id=resolve_root_thread_id(runtime),
                preset_id=QUESTION_PRESET_ID,
                preset_version=QUESTION_PRESET_VERSION,
                resolved=resolved,
                secret_key=app_config.SECRET_KEY,
            )
        session = await _get_session(workspace_id, runtime)
        result = await session.run_command(f"cat /opt/skills/{artifact_type}/SKILL.md")
        instructions = _result_text(
            result.output or "", result.exit_code, full_output_path=None
        )
        if selection_token is not None and resolved is not None:
            instructions += (
                "\n\nTrusted infographic selection:\n"
                f"- requested_style_id: {resolved.requested_id}\n"
                f"- resolved_style_id: {resolved.resolved_id}\n"
                f"- infographic_selection_token: {selection_token}\n"
                "Use execute(language=\"infographic\") with this token. Do not "
                "rewrite or substitute the selected style."
            )
        return instructions

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
