"""``ls`` factory: resolve target, page through backend listing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from deepagents.backends.utils import validate_path
from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, StructuredTool

from app.agents.shared.filesystem_state import SurfSenseFilesystemState
from app.agents.new_chat.middleware.kb_postgres_backend import paginate_listing

from ...middleware.async_dispatch import run_async_blocking
from ...middleware.path_resolution import resolve_list_target_path
from .description import select_description

if TYPE_CHECKING:
    from ...middleware import SurfSenseFilesystemMiddleware


def create_ls_tool(mw: SurfSenseFilesystemMiddleware) -> BaseTool:
    description = select_description(mw._filesystem_mode)

    async def async_ls(
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
        path: Annotated[
            str,
            "Absolute path to the directory to list. Relative paths resolve against the current cwd.",
        ] = "",
        offset: Annotated[
            int,
            "Number of entries to skip. Use for paginating large folders. Defaults to 0.",
        ] = 0,
        limit: Annotated[
            int,
            "Maximum number of entries to return. Defaults to 200.",
        ] = 200,
    ) -> str:
        target = resolve_list_target_path(mw, path, runtime)
        try:
            validated = validate_path(target)
        except ValueError as exc:
            return f"Error: {exc}"
        if offset < 0:
            offset = 0
        if limit < 1:
            limit = 1
        backend = mw._get_backend(runtime)
        infos = await backend.als_info(validated)
        page = paginate_listing(infos, offset=offset, limit=limit)
        paths = [
            f"{fi.get('path', '')}/" if fi.get("is_dir") else fi.get("path", "")
            for fi in page
        ]
        total = len(infos)
        shown = len(page)
        header = (
            f"{validated} ({shown} of {total} entries"
            f"{f', offset={offset}' if offset else ''})"
        )
        if not paths:
            return f"{header}\n(empty)"
        body = "\n".join(paths)
        if total > offset + shown:
            body += (
                f"\n... {total - offset - shown} more — call ls("
                f"'{validated}', offset={offset + shown}, limit={limit})"
            )
        return f"{header}\n{body}"

    def sync_ls(
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
        path: Annotated[
            str,
            "Absolute path to the directory to list. Relative paths resolve against the current cwd.",
        ] = "",
        offset: Annotated[
            int,
            "Number of entries to skip. Use for paginating large folders. Defaults to 0.",
        ] = 0,
        limit: Annotated[
            int,
            "Maximum number of entries to return. Defaults to 200.",
        ] = 200,
    ) -> str:
        return run_async_blocking(
            async_ls(runtime, path=path, offset=offset, limit=limit)
        )

    return StructuredTool.from_function(
        name="ls",
        description=description,
        func=sync_ls,
        coroutine=async_ls,
    )
