"""``SurfSenseFilesystemMiddleware``: per-session state + tool registration."""

from __future__ import annotations

from typing import Any

from deepagents import FilesystemMiddleware
from langchain_core.tools import BaseTool

from app.agents.shared.filesystem_selection import FilesystemMode
from app.agents.shared.filesystem_state import SurfSenseFilesystemState
from app.agents.shared.sandbox import is_sandbox_enabled

from ..system_prompt import build_system_prompt
from ..tools import (
    create_cd_tool,
    create_edit_file_tool,
    create_execute_code_tool,
    create_list_tree_tool,
    create_ls_tool,
    create_mkdir_tool,
    create_move_file_tool,
    create_pwd_tool,
    create_read_file_tool,
    create_rm_tool,
    create_rmdir_tool,
    create_write_file_tool,
)
from ..tools.glob.description import select_description as glob_description
from ..tools.grep.description import select_description as grep_description
from .read_only_policy import READ_ONLY_TOOL_NAMES


class SurfSenseFilesystemMiddleware(FilesystemMiddleware):
    """SurfSense-specific filesystem middleware (cloud + desktop)."""

    state_schema = SurfSenseFilesystemState

    def __init__(
        self,
        *,
        backend: Any = None,
        filesystem_mode: FilesystemMode = FilesystemMode.CLOUD,
        search_space_id: int | None = None,
        created_by_id: str | None = None,
        thread_id: int | str | None = None,
        tool_token_limit_before_evict: int | None = 20000,
        read_only: bool = False,
    ) -> None:
        self._filesystem_mode = filesystem_mode
        self._search_space_id = search_space_id
        self._created_by_id = created_by_id
        self._thread_id = thread_id
        self._read_only = read_only
        self._sandbox_available = (
            is_sandbox_enabled() and thread_id is not None and not read_only
        )

        system_prompt = build_system_prompt(
            filesystem_mode,
            sandbox_available=self._sandbox_available,
        )

        super().__init__(
            backend=backend,
            system_prompt=system_prompt,
            tool_token_limit_before_evict=tool_token_limit_before_evict,
        )
        self.tools = [t for t in self.tools if t.name != "execute"]
        self.tools.append(create_mkdir_tool(self))
        self.tools.append(create_cd_tool(self))
        self.tools.append(create_pwd_tool(self))
        self.tools.append(create_move_file_tool(self))
        self.tools.append(create_rm_tool(self))
        self.tools.append(create_rmdir_tool(self))
        self.tools.append(create_list_tree_tool(self))
        if self._sandbox_available:
            self.tools.append(create_execute_code_tool(self))

        if read_only:
            self.tools = [t for t in self.tools if t.name in READ_ONLY_TOOL_NAMES]

    # ----------------------------------------- base-class tool overrides

    def _create_ls_tool(self) -> BaseTool:
        return create_ls_tool(self)

    def _create_read_file_tool(self) -> BaseTool:
        return create_read_file_tool(self)

    def _create_write_file_tool(self) -> BaseTool:
        return create_write_file_tool(self)

    def _create_edit_file_tool(self) -> BaseTool:
        return create_edit_file_tool(self)

    def _create_glob_tool(self) -> BaseTool:
        tool = super()._create_glob_tool()
        tool.description = glob_description(self._filesystem_mode).rstrip()
        return tool

    def _create_grep_tool(self) -> BaseTool:
        tool = super()._create_grep_tool()
        tool.description = grep_description(self._filesystem_mode).rstrip()
        return tool
