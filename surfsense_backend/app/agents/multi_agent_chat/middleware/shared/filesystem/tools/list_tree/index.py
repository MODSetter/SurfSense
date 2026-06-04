"""``list_tree`` factory: bounded recursive listing across cloud / desktop backends."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated

from deepagents.backends.utils import validate_path
from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, StructuredTool

from app.agents.shared.filesystem_state import SurfSenseFilesystemState
from app.agents.new_chat.middleware.kb_postgres_backend import KBPostgresBackend

from ...middleware.async_dispatch import run_async_blocking
from ...middleware.path_resolution import resolve_list_target_path
from .description import select_description

if TYPE_CHECKING:
    from ...middleware import SurfSenseFilesystemMiddleware


def create_list_tree_tool(mw: SurfSenseFilesystemMiddleware) -> BaseTool:
    description = select_description(mw._filesystem_mode)

    async def async_list_tree(
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
        path: Annotated[
            str,
            "Absolute path to start from. Defaults to /documents in cloud mode.",
        ] = "",
        max_depth: Annotated[int, "Recursion depth limit. Default 8."] = 8,
        page_size: Annotated[int, "Maximum entries returned. Max 1000."] = 500,
        include_files: Annotated[bool, "Include file entries."] = True,
        include_dirs: Annotated[bool, "Include directory entries."] = True,
    ) -> str:
        if max_depth < 0:
            return "Error: max_depth must be >= 0."
        if page_size < 1:
            return "Error: page_size must be >= 1."
        if not include_files and not include_dirs:
            return "Error: include_files and include_dirs cannot both be false."

        target = resolve_list_target_path(mw, path, runtime)
        try:
            validated = validate_path(target)
        except ValueError as exc:
            return f"Error: {exc}"

        backend = mw._get_backend(runtime)
        if isinstance(backend, KBPostgresBackend):
            result = await backend.alist_tree_listing(
                validated,
                max_depth=max_depth,
                page_size=page_size,
                include_files=include_files,
                include_dirs=include_dirs,
            )
        elif hasattr(backend, "alist_tree"):
            result = await backend.alist_tree(
                validated,
                max_depth=max_depth,
                page_size=page_size,
                include_files=include_files,
                include_dirs=include_dirs,
            )
        else:
            return "Error: list_tree is not supported by the active backend."

        if isinstance(result, dict) and isinstance(result.get("error"), str):
            return result["error"]
        return json.dumps(result, ensure_ascii=True)

    def sync_list_tree(
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
        path: Annotated[
            str,
            "Absolute path to start from. Defaults to /documents in cloud mode.",
        ] = "",
        max_depth: Annotated[int, "Recursion depth limit. Default 8."] = 8,
        page_size: Annotated[int, "Maximum entries returned. Max 1000."] = 500,
        include_files: Annotated[bool, "Include file entries."] = True,
        include_dirs: Annotated[bool, "Include directory entries."] = True,
    ) -> str:
        return run_async_blocking(
            async_list_tree(
                runtime,
                path=path,
                max_depth=max_depth,
                page_size=page_size,
                include_files=include_files,
                include_dirs=include_dirs,
            )
        )

    return StructuredTool.from_function(
        name="list_tree",
        description=description,
        func=sync_list_tree,
        coroutine=async_list_tree,
    )
