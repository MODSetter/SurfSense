"""Sandbox rendering operations for the video pipeline.

All mechanical steps that run in the Daytona sandbox:
  - Uploading generated component files
  - Generating the Remotion Root.tsx configuration
  - Running TypeScript validation
  - Rendering the composition to MP4
  - Downloading the rendered video to local storage
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path, PurePosixPath

from app.agents.new_chat.sandbox import _TimeoutAwareSandbox
from app.agents.video.constants import (
    DEFAULT_VIDEO_FPS,
    DEFAULT_VIDEO_HEIGHT,
    DEFAULT_VIDEO_WIDTH,
    IGNORABLE_TYPESCRIPT_DIAGNOSTICS,
    LOCAL_VIDEO_STORAGE_DIR,
    REMOTION_RENDER_TIMEOUT_SECONDS,
    SANDBOX_OUTPUT_DIR,
    SANDBOX_PROJECT_DIR,
    TYPESCRIPT_CHECK_TIMEOUT_SECONDS,
)
from app.agents.video.llm import extract_component_name

logger = logging.getLogger(__name__)


async def upload_component_files(sandbox: _TimeoutAwareSandbox, component_files: list[dict]) -> None:
    """Upload all LLM-generated component files to the sandbox project."""
    for file_entry in component_files:
        sandbox_file_path = str(PurePosixPath(SANDBOX_PROJECT_DIR) / file_entry["path"])
        await asyncio.to_thread(
            sandbox._sandbox.fs.upload_file,
            file_entry["content"].encode("utf-8"),
            sandbox_file_path,
        )
        logger.info("[video/renderer] Uploaded: %s", sandbox_file_path)


async def upload_remotion_root_config(
    sandbox: _TimeoutAwareSandbox,
    component_files: list[dict],
    composition_id: str,
    duration_in_frames: int,
) -> None:
    """Generate and upload Root.tsx that registers the composition with Remotion."""
    component_file_path = component_files[0]["path"]
    component_import_path = "./" + component_file_path.replace("src/", "").replace(".tsx", "").replace(".ts", "")
    component_name = extract_component_name(component_files[0]["content"])

    root_component_code = f"""\
import {{ Composition }} from "remotion";
import {{ {component_name} }} from "{component_import_path}";

export const RemotionRoot: React.FC = () => {{
  return (
    <Composition
      id="{composition_id}"
      component={{{component_name}}}
      durationInFrames={{{duration_in_frames}}}
      fps={{{DEFAULT_VIDEO_FPS}}}
      width={{{DEFAULT_VIDEO_WIDTH}}}
      height={{{DEFAULT_VIDEO_HEIGHT}}}
    />
  );
}};
"""
    sandbox_root_path = f"{SANDBOX_PROJECT_DIR}/src/Root.tsx"
    await asyncio.to_thread(
        sandbox._sandbox.fs.upload_file,
        root_component_code.encode("utf-8"),
        sandbox_root_path,
    )
    logger.info(
        "[video/renderer] Uploaded Root.tsx (composition=%s, duration=%d frames)",
        composition_id,
        duration_in_frames,
    )


async def validate_typescript(sandbox: _TimeoutAwareSandbox) -> str | None:
    """Run TypeScript compiler to check for errors. Returns error text or None if clean."""
    result = await sandbox.aexecute(
        f"cd {SANDBOX_PROJECT_DIR} && npx tsc --noEmit 2>&1",
        timeout=TYPESCRIPT_CHECK_TIMEOUT_SECONDS,
    )
    if result.exit_code == 0:
        logger.info("[video/renderer] TypeScript validation: clean")
        return None

    diagnostic_lines = result.output.strip().splitlines()
    actual_errors = [
        line for line in diagnostic_lines
        if not any(code in line for code in IGNORABLE_TYPESCRIPT_DIAGNOSTICS)
    ]
    if not actual_errors:
        logger.info("[video/renderer] TypeScript validation: only ignorable warnings")
        return None

    error_output = "\n".join(actual_errors)
    logger.warning("[video/renderer] TypeScript errors:\n%s", error_output[:1000])
    return error_output


async def render_composition_to_mp4(sandbox: _TimeoutAwareSandbox, composition_id: str) -> str:
    """Render the Remotion composition to an MP4 file in the sandbox. Returns the sandbox file path."""
    output_video_path = f"{SANDBOX_OUTPUT_DIR}/{composition_id}.mp4"
    result = await sandbox.aexecute(
        f"cd {SANDBOX_PROJECT_DIR} && npx remotion render {composition_id} {output_video_path} 2>&1",
        timeout=REMOTION_RENDER_TIMEOUT_SECONDS,
    )
    if result.exit_code != 0:
        raise ValueError(f"Remotion render failed:\n{result.output.strip()[:2000]}")
    logger.info("[video/renderer] Rendered video: %s", output_video_path)
    return output_video_path


async def download_rendered_video(
    sandbox: _TimeoutAwareSandbox,
    sandbox_video_path: str,
    thread_id: int | str,
) -> Path:
    """Download the rendered MP4 from the sandbox to local storage."""
    video_bytes: bytes = await asyncio.to_thread(
        sandbox._sandbox.fs.download_file, sandbox_video_path
    )
    thread_video_dir = LOCAL_VIDEO_STORAGE_DIR / str(thread_id)
    thread_video_dir.mkdir(parents=True, exist_ok=True)
    local_video_path = thread_video_dir / Path(sandbox_video_path).name
    local_video_path.write_bytes(video_bytes)
    return local_video_path
