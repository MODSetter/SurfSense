"""Prompt loaders for the knowledge_base subagent."""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode
from app.agents.chat.multi_agent_chat.subagents.shared.md_file_reader import (
    read_md_file,
)


def load_system_prompt(filesystem_mode: FilesystemMode) -> str:
    stem = (
        "system_prompt_cloud"
        if filesystem_mode == FilesystemMode.CLOUD
        else "system_prompt_desktop"
    )
    return read_md_file(__package__, stem).strip()


def load_readonly_system_prompt(filesystem_mode: FilesystemMode) -> str:
    stem = (
        "system_prompt_readonly_cloud"
        if filesystem_mode == FilesystemMode.CLOUD
        else "system_prompt_readonly_desktop"
    )
    return read_md_file(__package__, stem).strip()


def load_description() -> str:
    return read_md_file(__package__, "description").strip() or (
        "Handles knowledge-base reads, writes, edits, and organisation."
    )


def load_readonly_description() -> str:
    return read_md_file(__package__, "description_readonly").strip()
