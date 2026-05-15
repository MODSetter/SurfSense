"""Public assembly of the FS system prompt for a given session."""

from __future__ import annotations

from app.agents.new_chat.filesystem_selection import FilesystemMode

from .cloud import BODY as CLOUD_BODY
from .common import HEADER, SANDBOX_ADDENDUM
from .desktop import BODY as DESKTOP_BODY


def build_system_prompt(mode: FilesystemMode, *, sandbox_available: bool) -> str:
    """Assemble the FS prompt: common header + mode body + optional sandbox section."""
    body = CLOUD_BODY if mode == FilesystemMode.CLOUD else DESKTOP_BODY
    base = HEADER + body
    if sandbox_available:
        base += SANDBOX_ADDENDUM
    return base
