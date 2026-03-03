"""Shared constants for the video generation package."""

from __future__ import annotations

import os
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Sandbox paths (Daytona remote filesystem)
# ---------------------------------------------------------------------------
SANDBOX_PROJECT_DIR = "/home/daytona/remotion-project"
SANDBOX_OUTPUT_DIR = "/home/daytona/out"

# ---------------------------------------------------------------------------
# Local storage for downloaded rendered videos
# ---------------------------------------------------------------------------
LOCAL_VIDEO_STORAGE_DIR = Path(os.environ.get("SANDBOX_FILES_DIR", "sandbox_files")) / "video"

# ---------------------------------------------------------------------------
# Remotion skill files (.md) bundled in the repo
# ---------------------------------------------------------------------------
REMOTION_SKILLS_DIR = Path(__file__).resolve().parent / "skills"

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
MAX_TYPESCRIPT_FIX_ATTEMPTS = 1

# ---------------------------------------------------------------------------
# Sandbox lifecycle
# ---------------------------------------------------------------------------
SANDBOX_THREAD_LABEL_KEY = "surfsense_video_thread"

# ---------------------------------------------------------------------------
# TypeScript validation
# ---------------------------------------------------------------------------
TYPESCRIPT_CHECK_TIMEOUT_SECONDS = 60
IGNORABLE_TYPESCRIPT_DIAGNOSTICS = frozenset({"TS6133", "TS6196"})

# ---------------------------------------------------------------------------
# Remotion rendering
# ---------------------------------------------------------------------------
REMOTION_RENDER_TIMEOUT_SECONDS = 300
DEFAULT_VIDEO_FPS = 30
DEFAULT_VIDEO_WIDTH = 1920
DEFAULT_VIDEO_HEIGHT = 1080

# ---------------------------------------------------------------------------
# LLM response parsing
# ---------------------------------------------------------------------------
COMPONENT_EXPORT_PATTERN = re.compile(r"export\s+(?:const|function)\s+(\w+)")
DEFAULT_COMPOSITION_ID = "MyComp"
DEFAULT_DURATION_IN_FRAMES = 300
DEFAULT_COMPONENT_NAME = "MyAnimation"
