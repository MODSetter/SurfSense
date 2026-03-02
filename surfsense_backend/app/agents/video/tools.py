"""
LangChain tools for the video deep agent.

Each tool wraps a Daytona sandbox operation. The sandbox instance is
injected at build time via build_video_tools(sandbox).

Tools:
  write_file   — create or overwrite a file in the Remotion project
  read_file    — read a file's content
  delete_file  — delete a file
  list_files   — list files in a directory
  run_tsc      — run TypeScript validation (tsc --noEmit)
  render_video — render a Remotion composition to MP4
"""

from __future__ import annotations

import logging
from pathlib import PurePosixPath

from langchain_core.tools import tool

from app.agents.new_chat.sandbox import _TimeoutAwareSandbox

logger = logging.getLogger(__name__)

PROJECT_ROOT = "/home/daytona/remotion-project"
OUTPUT_DIR = "/home/daytona/out"


def build_video_tools(sandbox: _TimeoutAwareSandbox) -> list:
    """Return the 6 video agent tools bound to *sandbox*."""

    @tool
    def write_file(path: str, content: str) -> str:
        """Write content to a file in the Remotion project.

        Args:
            path: Path relative to the project root (e.g. 'src/MyComp.tsx').
            content: Full file content to write.
        """
        abs_path = str(PurePosixPath(PROJECT_ROOT) / path)
        try:
            sandbox._sandbox.fs.upload_file(content.encode("utf-8"), abs_path)
            logger.info("[video] write_file: %s", abs_path)
            return f"Written: {path}"
        except Exception as e:
            return f"Error writing {path}: {e}"

    @tool
    def read_file(path: str) -> str:
        """Read the content of a file in the Remotion project.

        Args:
            path: Path relative to the project root (e.g. 'src/MyComp.tsx').
        """
        abs_path = str(PurePosixPath(PROJECT_ROOT) / path)
        try:
            raw: bytes = sandbox._sandbox.fs.download_file(abs_path)
            return raw.decode("utf-8")
        except Exception as e:
            return f"Error reading {path}: {e}"

    @tool
    def delete_file(path: str) -> str:
        """Delete a file from the Remotion project.

        Args:
            path: Path relative to the project root (e.g. 'src/unused.tsx').
        """
        abs_path = str(PurePosixPath(PROJECT_ROOT) / path)
        try:
            sandbox._sandbox.fs.delete_file(abs_path)
            logger.info("[video] delete_file: %s", abs_path)
            return f"Deleted: {path}"
        except Exception as e:
            return f"Error deleting {path}: {e}"

    @tool
    def list_files(path: str = "src") -> str:
        """List files in a directory of the Remotion project.

        Args:
            path: Directory path relative to the project root. Defaults to 'src'.
        """
        abs_path = str(PurePosixPath(PROJECT_ROOT) / path)
        try:
            entries = sandbox._sandbox.fs.list_files(abs_path)
            names = [e.name for e in entries]
            return "\n".join(names) if names else "(empty)"
        except Exception as e:
            return f"Error listing {path}: {e}"

    @tool
    def run_tsc() -> str:
        """Run TypeScript validation on the Remotion project (tsc --noEmit).

        Returns an empty string if there are no errors, or the full error output.
        """
        result = sandbox.execute(
            f"cd {PROJECT_ROOT} && npx tsc --noEmit 2>&1",
            timeout=60,
        )
        output = result.output.strip()
        if result.exit_code == 0:
            logger.info("[video] tsc: clean")
            return "TypeScript validation passed. No errors."
        logger.info("[video] tsc errors:\n%s", output)
        return output

    @tool
    def render_video(composition_id: str = "MyComp") -> str:
        """Render a Remotion composition to MP4.

        Args:
            composition_id: The composition id defined in Root.tsx. Defaults to 'MyComp'.

        Returns the sandbox path to the rendered MP4 file.
        """
        out_path = f"{OUTPUT_DIR}/{composition_id}.mp4"
        result = sandbox.execute(
            f"cd {PROJECT_ROOT} && npx remotion render {composition_id} {out_path} 2>&1",
            timeout=300,
        )
        if result.exit_code != 0:
            logger.error("[video] render failed:\n%s", result.output)
            return f"Render failed:\n{result.output.strip()}"
        logger.info("[video] rendered: %s", out_path)
        return out_path

    return [write_file, read_file, delete_file, list_files, run_tsc, render_video]
