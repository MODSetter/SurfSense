"""Custom filesystem middleware for the SurfSense agent.

This middleware fully overrides every deepagents filesystem tool so that the
``Command(update=...)`` payload can carry SurfSense-specific state fields
(``cwd``, ``staged_dirs``, ``pending_moves``, ``doc_id_by_path``,
``dirty_paths``) atomically alongside the standard ``files`` update.

In CLOUD mode the backend is :class:`KBPostgresBackend` (lazy DB reads, no DB
writes). End-of-turn persistence is handled by
:class:`KnowledgeBasePersistenceMiddleware`. In DESKTOP_LOCAL_FOLDER mode the
backend is :class:`MultiRootLocalFolderBackend` and writes go straight to disk.

New tools introduced here:

* ``mkdir`` — cloud-only stages folder paths to ``state['staged_dirs']``;
  desktop creates real directories.
* ``cd`` / ``pwd`` — manage ``state['cwd']`` (per-thread).
* ``move_file`` — staged commit in cloud, real disk move in desktop.
* ``list_tree`` — works in both modes (cloud uses
  :func:`KBPostgresBackend.alist_tree_listing`).

The middleware no longer ships ``save_document``; persistence is inferred
from ``write_file`` / ``edit_file`` against ``/documents/*`` paths.
"""

from __future__ import annotations

import asyncio
import json
import logging
import posixpath
import re
import secrets
from typing import Annotated, Any

from daytona.common.errors import DaytonaError
from deepagents import FilesystemMiddleware
from deepagents.backends.protocol import EditResult, WriteResult
from deepagents.backends.utils import (
    create_file_data,
    format_read_response,
    validate_path,
)
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command

from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.filesystem_state import SurfSenseFilesystemState
from app.agents.new_chat.middleware.kb_postgres_backend import (
    KBPostgresBackend,
    paginate_listing,
)
from app.agents.new_chat.middleware.multi_root_local_folder_backend import (
    MultiRootLocalFolderBackend,
)
from app.agents.new_chat.path_resolver import DOCUMENTS_ROOT
from app.agents.new_chat.sandbox import (
    _evict_sandbox_cache,
    delete_sandbox,
    get_or_create_sandbox,
    is_sandbox_enabled,
)
from app.agents.new_chat.state_reducers import _CLEAR

logger = logging.getLogger(__name__)


# =============================================================================
# System Prompt (built per-session based on filesystem_mode)
# =============================================================================
#
# Each chat session runs in exactly one filesystem mode. Including rules for
# the OTHER mode just wastes tokens and confuses the model, so we build the
# prompt + tool descriptions for the active mode only.

_COMMON_PROMPT_HEADER = """## Following Conventions

- Read files before editing — understand existing content before making changes.
- Mimic existing style, naming conventions, and patterns.
- Never claim a file was created/updated unless filesystem tool output confirms success.
- If a file write/edit fails, explicitly report the failure.
"""

_CLOUD_SYSTEM_PROMPT = (
    _COMMON_PROMPT_HEADER
    + """
## Filesystem Tools

All file paths must start with `/`. Relative paths resolve against the
current working directory (`cwd`, default `/documents`).

- ls(path, offset=0, limit=200): list files and directories at the given path.
- read_file(path, offset, limit): read a file (paginated) from the filesystem.
- write_file(path, content): create a new text file in the workspace.
- edit_file(path, old, new): exact string-replacement edit (lazy-loads KB
  documents on first edit).
- glob(pattern, path): find files matching a glob pattern.
- grep(pattern, path, glob): substring search across files.
- mkdir(path): create a folder under `/documents/` (committed at end of turn).
- cd(path): change the current working directory.
- pwd(): print the current working directory.
- move_file(source, dest): move/rename a file under `/documents/`.
- list_tree(path, max_depth, page_size): recursively list files/folders.

## Persistence Rules

- Files written under `/documents/<...>` are **persisted** at end of turn as
  Documents in the user's knowledge base.
- Files whose **basename** starts with `temp_` (e.g. `temp_plan.md` or
  `/documents/temp_scratch.md`) are **discarded** at end of turn — use this
  prefix for any scratch/working content you do NOT want saved.
- All other paths (outside `/documents/` and not `temp_*`) are rejected.
- mkdir/move_file are staged this turn and committed at end of turn alongside
  any new/edited documents.

## Reading Documents Efficiently

Documents are formatted as XML. Each document contains:
- `<document_metadata>` — title, type, URL, etc.
- `<chunk_index>` — a table of every chunk with its **line range** and a
  `matched="true"` flag for chunks that matched the search query.
- `<document_content>` — the actual chunks in original document order.

**Workflow**: when reading a large document, read the first ~20 lines to see
the `<chunk_index>`, identify chunks marked `matched="true"`, then use
`read_file(path, offset=<start_line>, limit=<lines>)` to jump directly to
those sections instead of reading the entire file sequentially.

Use `<chunk id='...'>` values as citation IDs in your answers.

## Priority List

You receive a `<priority_documents>` system message each turn listing the
top-K paths most relevant to the user's query (by hybrid search). Read those
first — matched sections are flagged inside each document's `<chunk_index>`.

## Workspace Tree

You receive a `<workspace_tree>` system message each turn with the current
folder/document layout. The tree may be truncated past a hard cap; in that
case, drill into specific folders with `ls(...)` or `list_tree(...)`.

## grep Line Numbers

`grep` searches across both your in-memory edits and the indexed chunks in
Postgres. State-cached files return real line numbers; database hits return
`line=0` because their position depends on per-document XML layout — call
`read_file(path)` to find the exact line.
"""
)

_DESKTOP_SYSTEM_PROMPT = (
    _COMMON_PROMPT_HEADER
    + """
## Local Folder Mode

This chat operates directly on the user's local folders. Writes and edits
hit disk immediately — there is no end-of-turn staging, no `/documents/`
namespace, and no `temp_` semantics.

## Filesystem Tools

All file paths must start with `/` and use mount-prefixed absolute paths
like `/<mount>/file.ext`. Relative paths resolve against the current working
directory (`cwd`).

- ls(path, offset=0, limit=200): list files and directories at the given path.
- read_file(path, offset, limit): read a file (paginated) from disk.
- write_file(path, content): write a file to disk.
- edit_file(path, old, new): exact string-replacement edit on disk.
- glob(pattern, path): find files matching a glob pattern.
- grep(pattern, path, glob): substring search across files.
- mkdir(path): create a directory on disk.
- cd(path): change the current working directory.
- pwd(): print the current working directory.
- move_file(source, dest): move/rename a file.
- list_tree(path, max_depth, page_size): recursively list files/folders.

## Workflow Tips

- If you are unsure which mounts are available, call `ls('/')` first.
- For large trees, prefer `list_tree` then `grep` then `read_file` over
  brute-force directory traversal.
- Cross-mount moves are not supported.
"""
)

_SANDBOX_PROMPT_ADDENDUM = (
    "\n- execute_code: run Python code in an isolated sandbox."
    "\n\n## Code Execution"
    "\n\nUse execute_code whenever a task benefits from running code."
    " Never perform arithmetic manually."
    "\n\nDocuments here are XML-wrapped markdown, not raw data files."
    " To work with them programmatically, read the document first,"
    " extract the data, write it as a clean file (CSV, JSON, etc.),"
    " and then run your code against it."
)


def _build_filesystem_system_prompt(
    filesystem_mode: FilesystemMode,
    *,
    sandbox_available: bool,
) -> str:
    """Build the filesystem system prompt for a given session mode.

    The prompt only describes rules and tools that actually apply in the
    chosen mode — there is no cross-mode noise.
    """
    base = (
        _CLOUD_SYSTEM_PROMPT
        if filesystem_mode == FilesystemMode.CLOUD
        else _DESKTOP_SYSTEM_PROMPT
    )
    if sandbox_available:
        base += _SANDBOX_PROMPT_ADDENDUM
    return base


# Backwards-compatible alias retained for any external imports.
SURFSENSE_FILESYSTEM_SYSTEM_PROMPT = _CLOUD_SYSTEM_PROMPT

# =============================================================================
# Per-Tool Descriptions (shown to the LLM as the tool's docstring)
# =============================================================================

# =============================================================================
# Per-Tool Descriptions (mode-specific; injected as the tool's docstring)
# =============================================================================

# --- mode-agnostic ---------------------------------------------------------

SURFSENSE_READ_FILE_TOOL_DESCRIPTION = """Reads a file from the filesystem.

Usage:
- By default, reads up to 100 lines from the beginning.
- Use `offset` and `limit` for pagination when files are large.
- Results include line numbers.
- Documents contain a `<chunk_index>` near the top listing every chunk with
  its line range and a `matched="true"` flag for search-relevant chunks.
  Read the index first, then jump to matched chunks with
  `read_file(path, offset=<start_line>, limit=<num_lines>)`.
- Use chunk IDs (`<chunk id='...'>`) as citations in answers.
"""

SURFSENSE_GLOB_TOOL_DESCRIPTION = """Find files matching a glob pattern.

Supports standard glob patterns: `*`, `**`, `?`.
Returns absolute file paths.
"""

SURFSENSE_CD_TOOL_DESCRIPTION = """Changes the current working directory (cwd).

Args:
- path: absolute or relative directory path. Relative paths resolve against
  the current cwd.

The new cwd is used by other filesystem tools whenever a relative path is
given. Returns the resolved cwd.
"""

SURFSENSE_PWD_TOOL_DESCRIPTION = """Prints the current working directory."""

SURFSENSE_EXECUTE_CODE_TOOL_DESCRIPTION = """Executes Python code in an isolated sandbox environment.

Common data-science packages are pre-installed (pandas, numpy, matplotlib,
scipy, scikit-learn).

Usage notes:
- No outbound network access.
- Returns combined stdout/stderr with exit code.
- Use print() to produce output.
- Use the optional timeout parameter to override the default timeout.
"""

# --- cloud-only ------------------------------------------------------------

_CLOUD_LIST_FILES_TOOL_DESCRIPTION = """Lists files and directories at the given path.

Usage:
- Provide an absolute path under `/documents` (relative paths resolve under
  the current cwd, which defaults to `/documents`).
- For very large folders, use `offset` and `limit` to paginate the listing.
- Returns one entry per line; directories end with a trailing `/`.
"""

_CLOUD_WRITE_FILE_TOOL_DESCRIPTION = """Writes a new text file to the workspace.

Usage:
- Files written under `/documents/<...>` are persisted as Documents at end
  of turn.
- Use a `temp_` filename prefix (e.g. `temp_plan.md` or `/documents/temp_x.md`)
  for scratch/working files; they are automatically discarded at end of turn.
- Writes outside `/documents/` are rejected unless the basename starts with
  `temp_`.
- Supported outputs include common LLM-friendly text formats like markdown,
  json, yaml, csv, xml, html, css, sql, and code files.
- Avoid placeholders; produce concrete and useful text.
"""

_CLOUD_EDIT_FILE_TOOL_DESCRIPTION = """Performs exact string replacements in files.

IMPORTANT:
- Read the file before editing.
- Preserve exact indentation and formatting.
- Edits to documents under `/documents/` are persisted at end of turn.
- Edits to `temp_*` files are discarded at end of turn.
"""

_CLOUD_MOVE_FILE_TOOL_DESCRIPTION = """Moves or renames a file or folder.

Use absolute paths for both source and destination.

Notes:
- `move_file` is staged this turn and committed at end of turn.
- The agent cannot overwrite an existing destination — pass a fresh dest
  path or move the existing destination away first.
- The anonymous uploaded document is read-only and cannot be moved.
- Rename is a special case of move (same folder, different filename).
"""

_CLOUD_LIST_TREE_TOOL_DESCRIPTION = """Lists files/folders recursively in a single bounded call.

Args:
- path: absolute path to start from. Defaults to `/documents`.
- max_depth: recursion depth limit (default 8).
- page_size: maximum number of entries returned (max 1000).
- include_files / include_dirs: filter returned entry types.

Returns JSON with:
- entries: [{path, is_dir, size, modified_at, depth}]
- truncated: true when additional entries were omitted due to page_size.
"""

_CLOUD_GREP_TOOL_DESCRIPTION = """Search for a literal text pattern across files.

Searches both your in-memory edits and the indexed chunks in Postgres.
State-cached file matches include real line numbers; database hits return
`line=0` because their position depends on per-document XML layout — call
`read_file(path)` afterwards to find the exact line.
"""

_CLOUD_MKDIR_TOOL_DESCRIPTION = """Creates a directory under `/documents/`.

Stages the folder for end-of-turn commit; the Folder row is inserted only
after the agent's turn finishes successfully.

Args:
- path: absolute path of the new directory (must start with
  `/documents/`).

Notes:
- Parent folders are created as needed.
"""

# --- desktop-only ----------------------------------------------------------

_DESKTOP_LIST_FILES_TOOL_DESCRIPTION = """Lists files and directories at the given path.

Usage:
- Provide an absolute path using a mount prefix (e.g. `/<mount>/sub/dir`).
  Use `ls('/')` to discover available mounts.
- For very large folders, use `offset` and `limit` to paginate the listing.
- Returns one entry per line; directories end with a trailing `/`.
"""

_DESKTOP_WRITE_FILE_TOOL_DESCRIPTION = """Writes a text file to disk.

Usage:
- Use mount-prefixed absolute paths like `/<mount>/sub/file.ext`.
- Writes hit disk immediately. There is no end-of-turn staging.
- Supported outputs include common LLM-friendly text formats like markdown,
  json, yaml, csv, xml, html, css, sql, and code files.
- Avoid placeholders; produce concrete and useful text.
"""

_DESKTOP_EDIT_FILE_TOOL_DESCRIPTION = """Performs exact string replacements in files on disk.

IMPORTANT:
- Read the file before editing.
- Preserve exact indentation and formatting.
- Edits hit disk immediately.
"""

_DESKTOP_MOVE_FILE_TOOL_DESCRIPTION = """Moves or renames a file or folder on disk.

Use mount-prefixed absolute paths for both source and destination
(e.g. `/<mount>/old.txt` -> `/<mount>/new.txt`).

Notes:
- Cross-mount moves are not supported.
- Rename is a special case of move (same folder, different filename).
"""

_DESKTOP_LIST_TREE_TOOL_DESCRIPTION = """Lists files/folders recursively in a single bounded call.

Args:
- path: absolute path to start from. Defaults to `/`.
- max_depth: recursion depth limit (default 8).
- page_size: maximum number of entries returned (max 1000).
- include_files / include_dirs: filter returned entry types.

Returns JSON with:
- entries: [{path, is_dir, size, modified_at, depth}]
- truncated: true when additional entries were omitted due to page_size.
"""

_DESKTOP_GREP_TOOL_DESCRIPTION = """Search for a literal text pattern across files.

Searches files on disk and any in-memory edits. Returns real line numbers.
"""

_DESKTOP_MKDIR_TOOL_DESCRIPTION = """Creates a directory on disk.

Args:
- path: absolute mount-prefixed path of the new directory.

Notes:
- Parent folders are created as needed.
"""


def _build_tool_descriptions(filesystem_mode: FilesystemMode) -> dict[str, str]:
    """Pick the active-mode description for every filesystem tool."""
    if filesystem_mode == FilesystemMode.CLOUD:
        return {
            "ls": _CLOUD_LIST_FILES_TOOL_DESCRIPTION,
            "read_file": SURFSENSE_READ_FILE_TOOL_DESCRIPTION,
            "write_file": _CLOUD_WRITE_FILE_TOOL_DESCRIPTION,
            "edit_file": _CLOUD_EDIT_FILE_TOOL_DESCRIPTION,
            "move_file": _CLOUD_MOVE_FILE_TOOL_DESCRIPTION,
            "list_tree": _CLOUD_LIST_TREE_TOOL_DESCRIPTION,
            "glob": SURFSENSE_GLOB_TOOL_DESCRIPTION,
            "grep": _CLOUD_GREP_TOOL_DESCRIPTION,
            "mkdir": _CLOUD_MKDIR_TOOL_DESCRIPTION,
            "cd": SURFSENSE_CD_TOOL_DESCRIPTION,
            "pwd": SURFSENSE_PWD_TOOL_DESCRIPTION,
        }
    return {
        "ls": _DESKTOP_LIST_FILES_TOOL_DESCRIPTION,
        "read_file": SURFSENSE_READ_FILE_TOOL_DESCRIPTION,
        "write_file": _DESKTOP_WRITE_FILE_TOOL_DESCRIPTION,
        "edit_file": _DESKTOP_EDIT_FILE_TOOL_DESCRIPTION,
        "move_file": _DESKTOP_MOVE_FILE_TOOL_DESCRIPTION,
        "list_tree": _DESKTOP_LIST_TREE_TOOL_DESCRIPTION,
        "glob": SURFSENSE_GLOB_TOOL_DESCRIPTION,
        "grep": _DESKTOP_GREP_TOOL_DESCRIPTION,
        "mkdir": _DESKTOP_MKDIR_TOOL_DESCRIPTION,
        "cd": SURFSENSE_CD_TOOL_DESCRIPTION,
        "pwd": SURFSENSE_PWD_TOOL_DESCRIPTION,
    }


# Backwards-compatible aliases retained for any external imports/tests that
# referenced the original CLOUD-flavoured constants.
SURFSENSE_LIST_FILES_TOOL_DESCRIPTION = _CLOUD_LIST_FILES_TOOL_DESCRIPTION
SURFSENSE_WRITE_FILE_TOOL_DESCRIPTION = _CLOUD_WRITE_FILE_TOOL_DESCRIPTION
SURFSENSE_EDIT_FILE_TOOL_DESCRIPTION = _CLOUD_EDIT_FILE_TOOL_DESCRIPTION
SURFSENSE_MOVE_FILE_TOOL_DESCRIPTION = _CLOUD_MOVE_FILE_TOOL_DESCRIPTION
SURFSENSE_LIST_TREE_TOOL_DESCRIPTION = _CLOUD_LIST_TREE_TOOL_DESCRIPTION
SURFSENSE_GREP_TOOL_DESCRIPTION = _CLOUD_GREP_TOOL_DESCRIPTION
SURFSENSE_MKDIR_TOOL_DESCRIPTION = _CLOUD_MKDIR_TOOL_DESCRIPTION


# =============================================================================
# Helpers
# =============================================================================


_TEMP_PREFIX = "temp_"


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


class SurfSenseFilesystemMiddleware(FilesystemMiddleware):
    """SurfSense-specific filesystem middleware (cloud + desktop)."""

    state_schema = SurfSenseFilesystemState

    _MAX_EXECUTE_TIMEOUT = 300

    def __init__(
        self,
        *,
        backend: Any = None,
        filesystem_mode: FilesystemMode = FilesystemMode.CLOUD,
        search_space_id: int | None = None,
        created_by_id: str | None = None,
        thread_id: int | str | None = None,
        tool_token_limit_before_evict: int | None = 20000,
    ) -> None:
        self._filesystem_mode = filesystem_mode
        self._search_space_id = search_space_id
        self._created_by_id = created_by_id
        self._thread_id = thread_id
        self._sandbox_available = is_sandbox_enabled() and thread_id is not None

        # Build the prompt + tool descriptions for the active mode only —
        # mixing both modes wastes tokens and confuses the model with rules
        # it can't actually use this session.
        system_prompt = _build_filesystem_system_prompt(
            filesystem_mode,
            sandbox_available=self._sandbox_available,
        )

        super().__init__(
            backend=backend,
            system_prompt=system_prompt,
            custom_tool_descriptions=_build_tool_descriptions(filesystem_mode),
            tool_token_limit_before_evict=tool_token_limit_before_evict,
            max_execute_timeout=self._MAX_EXECUTE_TIMEOUT,
        )
        self.tools = [t for t in self.tools if t.name != "execute"]
        self.tools.append(self._create_mkdir_tool())
        self.tools.append(self._create_cd_tool())
        self.tools.append(self._create_pwd_tool())
        self.tools.append(self._create_move_file_tool())
        self.tools.append(self._create_list_tree_tool())
        if self._sandbox_available:
            self.tools.append(self._create_execute_code_tool())

    # ------------------------------------------------------------------ helpers

    def _is_cloud(self) -> bool:
        return self._filesystem_mode == FilesystemMode.CLOUD

    @staticmethod
    def _run_async_blocking(coro: Any) -> Any:
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                return "Error: sync filesystem operation not supported inside an active event loop."
        except RuntimeError:
            pass
        return asyncio.run(coro)

    @staticmethod
    def _normalize_absolute_path(candidate: str) -> str:
        normalized = re.sub(r"/+", "/", candidate.strip().replace("\\", "/"))
        if not normalized:
            return "/"
        if normalized.startswith("/"):
            return normalized
        return f"/{normalized.lstrip('/')}"

    @staticmethod
    def _extract_mount_from_path(path: str, mounts: tuple[str, ...]) -> str | None:
        rel = path.lstrip("/")
        if not rel:
            return None
        mount, _, _ = rel.partition("/")
        if mount in mounts:
            return mount
        return None

    @staticmethod
    def _local_parent_path(path: str) -> str:
        rel = path.lstrip("/")
        if "/" not in rel:
            return "/"
        parent = rel.rsplit("/", 1)[0].strip("/")
        if not parent:
            return "/"
        return f"/{parent}"

    @staticmethod
    def _path_exists_under_mount(
        backend: MultiRootLocalFolderBackend,
        mount: str,
        local_path: str,
    ) -> bool:
        result = backend.list_tree(
            f"/{mount}{local_path}",
            max_depth=0,
            page_size=1,
            include_files=True,
            include_dirs=True,
        )
        return not bool(result.get("error"))

    def _normalize_local_mount_path(
        self,
        candidate: str,
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
    ) -> str:
        normalized = self._normalize_absolute_path(candidate)
        backend = self._get_backend(runtime)
        if not isinstance(backend, MultiRootLocalFolderBackend):
            return normalized

        mounts = backend.list_mounts()
        explicit_mount = self._extract_mount_from_path(normalized, mounts)
        if explicit_mount:
            return normalized

        if len(mounts) == 1:
            return f"/{mounts[0]}{normalized}"

        suggested_mount: str | None = None
        contract = runtime.state.get("file_operation_contract") or {}
        suggested_path = contract.get("suggested_path")
        if isinstance(suggested_path, str) and suggested_path.strip():
            normalized_suggested = self._normalize_absolute_path(suggested_path)
            suggested_mount = self._extract_mount_from_path(
                normalized_suggested, mounts
            )

        matching_mounts = [
            mount
            for mount in mounts
            if self._path_exists_under_mount(backend, mount, normalized)
        ]
        if len(matching_mounts) == 1:
            return f"/{matching_mounts[0]}{normalized}"

        parent_path = self._local_parent_path(normalized)
        if parent_path != "/":
            parent_matching_mounts = [
                mount
                for mount in mounts
                if self._path_exists_under_mount(backend, mount, parent_path)
            ]
            if len(parent_matching_mounts) == 1:
                return f"/{parent_matching_mounts[0]}{normalized}"

        if suggested_mount:
            return f"/{suggested_mount}{normalized}"

        return f"/{backend.default_mount()}{normalized}"

    def _default_cwd(self) -> str:
        return DOCUMENTS_ROOT if self._is_cloud() else "/"

    def _current_cwd(self, runtime: ToolRuntime[None, SurfSenseFilesystemState]) -> str:
        cwd = runtime.state.get("cwd") if hasattr(runtime, "state") else None
        if isinstance(cwd, str) and cwd.startswith("/"):
            return cwd
        return self._default_cwd()

    def _get_contract_suggested_path(
        self, runtime: ToolRuntime[None, SurfSenseFilesystemState]
    ) -> str:
        contract = runtime.state.get("file_operation_contract") or {}
        suggested = contract.get("suggested_path")
        if isinstance(suggested, str) and suggested.strip():
            return self._normalize_absolute_path(suggested)
        return self._default_cwd().rstrip("/") + "/notes.md"

    def _resolve_relative(
        self,
        path: str,
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
    ) -> str:
        candidate = path.strip()
        if not candidate:
            return self._current_cwd(runtime)
        if candidate.startswith("/"):
            return self._normalize_absolute_path(candidate)
        cwd = self._current_cwd(runtime)
        joined = posixpath.normpath(posixpath.join(cwd, candidate))
        return self._normalize_absolute_path(joined)

    def _resolve_write_target_path(
        self,
        file_path: str,
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
    ) -> str:
        candidate = file_path.strip()
        if not candidate:
            return self._get_contract_suggested_path(runtime)
        if self._filesystem_mode == FilesystemMode.DESKTOP_LOCAL_FOLDER:
            return self._normalize_local_mount_path(candidate, runtime)
        return self._resolve_relative(candidate, runtime)

    def _resolve_move_target_path(
        self,
        file_path: str,
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
    ) -> str:
        candidate = file_path.strip()
        if not candidate:
            return ""
        if self._filesystem_mode == FilesystemMode.DESKTOP_LOCAL_FOLDER:
            return self._normalize_local_mount_path(candidate, runtime)
        return self._resolve_relative(candidate, runtime)

    def _resolve_list_target_path(
        self,
        path: str,
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
    ) -> str:
        candidate = path.strip() or self._current_cwd(runtime)
        if candidate == "/":
            return "/"
        if self._filesystem_mode == FilesystemMode.DESKTOP_LOCAL_FOLDER:
            return self._normalize_local_mount_path(candidate, runtime)
        return self._resolve_relative(candidate, runtime)

    # ------------------------------------------------------------------ namespace policy

    def _check_cloud_write_namespace(
        self,
        path: str,
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
    ) -> str | None:
        """Return an error string if cloud writes to ``path`` are not allowed.

        Order matters:
        1. Reject writes to the anonymous read-only doc.
        2. Allow ``/documents/*``.
        3. Allow ``temp_*`` basename anywhere.
        4. Reject everything else.
        """
        if not self._is_cloud():
            return None
        anon = runtime.state.get("kb_anon_doc") or {}
        if isinstance(anon, dict):
            anon_path = str(anon.get("path") or "")
            if anon_path and anon_path == path:
                return "Error: the anonymous uploaded document is read-only."
        if path.startswith(DOCUMENTS_ROOT + "/") or path == DOCUMENTS_ROOT:
            return None
        if _basename(path).startswith(_TEMP_PREFIX):
            return None
        return (
            "Error: cloud writes must target /documents/<...> or use a 'temp_' "
            f"basename for scratch (got '{path}')."
        )

    # ------------------------------------------------------------------ tool: ls

    def _create_ls_tool(self) -> BaseTool:
        tool_description = (
            self._custom_tool_descriptions.get("ls")
            or SURFSENSE_LIST_FILES_TOOL_DESCRIPTION
        )

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
            return self._run_async_blocking(
                async_ls(runtime, path=path, offset=offset, limit=limit)
            )

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
            target = self._resolve_list_target_path(path, runtime)
            try:
                validated = validate_path(target)
            except ValueError as exc:
                return f"Error: {exc}"
            if offset < 0:
                offset = 0
            if limit < 1:
                limit = 1
            backend = self._get_backend(runtime)
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

        return StructuredTool.from_function(
            name="ls",
            description=tool_description,
            func=sync_ls,
            coroutine=async_ls,
        )

    # ------------------------------------------------------------------ tool: read_file

    def _create_read_file_tool(self) -> BaseTool:
        tool_description = (
            self._custom_tool_descriptions.get("read_file")
            or SURFSENSE_READ_FILE_TOOL_DESCRIPTION
        )

        async def async_read_file(
            file_path: Annotated[
                str,
                "Absolute path to the file to read. Relative paths resolve against the current cwd.",
            ],
            runtime: ToolRuntime[None, SurfSenseFilesystemState],
            offset: Annotated[
                int,
                "Line number to start reading from (0-indexed).",
            ] = 0,
            limit: Annotated[
                int,
                "Maximum number of lines to read.",
            ] = 100,
        ) -> Command | str:
            target = self._resolve_relative(file_path, runtime)
            try:
                validated = validate_path(target)
            except ValueError as exc:
                return f"Error: {exc}"

            files = runtime.state.get("files") or {}
            if validated in files:
                return format_read_response(files[validated], offset, limit)

            backend = self._get_backend(runtime)
            if isinstance(backend, KBPostgresBackend):
                loaded = await backend._load_file_data(validated)
                if loaded is None:
                    return f"Error: File '{validated}' not found"
                file_data, doc_id = loaded
                rendered = format_read_response(file_data, offset, limit)
                update: dict[str, Any] = {
                    "files": {validated: file_data},
                    "messages": [
                        ToolMessage(
                            content=rendered,
                            tool_call_id=runtime.tool_call_id,
                        )
                    ],
                }
                if doc_id is not None:
                    update["doc_id_by_path"] = {validated: doc_id}
                return Command(update=update)

            try:
                rendered = await backend.aread(validated, offset=offset, limit=limit)
            except Exception as exc:  # pragma: no cover - defensive
                return f"Error: {exc}"
            return rendered

        def sync_read_file(
            file_path: Annotated[
                str,
                "Absolute path to the file to read. Relative paths resolve against the current cwd.",
            ],
            runtime: ToolRuntime[None, SurfSenseFilesystemState],
            offset: Annotated[
                int,
                "Line number to start reading from (0-indexed).",
            ] = 0,
            limit: Annotated[
                int,
                "Maximum number of lines to read.",
            ] = 100,
        ) -> Command | str:
            return self._run_async_blocking(
                async_read_file(file_path, runtime, offset, limit)
            )

        return StructuredTool.from_function(
            name="read_file",
            description=tool_description,
            func=sync_read_file,
            coroutine=async_read_file,
        )

    # ------------------------------------------------------------------ tool: write_file

    def _create_write_file_tool(self) -> BaseTool:
        tool_description = (
            self._custom_tool_descriptions.get("write_file")
            or SURFSENSE_WRITE_FILE_TOOL_DESCRIPTION
        )

        async def async_write_file(
            file_path: Annotated[
                str,
                "Absolute path where the file should be created. Relative paths resolve against the current cwd.",
            ],
            content: Annotated[str, "Text content to write to the file."],
            runtime: ToolRuntime[None, SurfSenseFilesystemState],
        ) -> Command | str:
            target = self._resolve_write_target_path(file_path, runtime)
            try:
                validated = validate_path(target)
            except ValueError as exc:
                return f"Error: {exc}"

            namespace_error = self._check_cloud_write_namespace(validated, runtime)
            if namespace_error:
                return namespace_error

            backend = self._get_backend(runtime)
            res: WriteResult = await backend.awrite(validated, content)
            if res.error:
                return res.error

            path = res.path or validated
            files_update = res.files_update or {path: create_file_data(content)}
            update: dict[str, Any] = {
                "files": files_update,
                "messages": [
                    ToolMessage(
                        content=f"Updated file {path}",
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
            if self._is_cloud():
                update["dirty_paths"] = [path]
            return Command(update=update)

        def sync_write_file(
            file_path: Annotated[
                str,
                "Absolute path where the file should be created. Relative paths resolve against the current cwd.",
            ],
            content: Annotated[str, "Text content to write to the file."],
            runtime: ToolRuntime[None, SurfSenseFilesystemState],
        ) -> Command | str:
            return self._run_async_blocking(
                async_write_file(file_path, content, runtime)
            )

        return StructuredTool.from_function(
            name="write_file",
            description=tool_description,
            func=sync_write_file,
            coroutine=async_write_file,
        )

    # ------------------------------------------------------------------ tool: edit_file

    def _create_edit_file_tool(self) -> BaseTool:
        tool_description = (
            self._custom_tool_descriptions.get("edit_file")
            or SURFSENSE_EDIT_FILE_TOOL_DESCRIPTION
        )

        async def async_edit_file(
            file_path: Annotated[
                str,
                "Absolute path to the file to edit. Relative paths resolve against the current cwd.",
            ],
            old_string: Annotated[
                str,
                "Exact text to replace. Must be unique unless replace_all is True.",
            ],
            new_string: Annotated[
                str,
                "Replacement text. Must differ from old_string.",
            ],
            runtime: ToolRuntime[None, SurfSenseFilesystemState],
            *,
            replace_all: Annotated[
                bool,
                "If True, replace all occurrences of old_string. Defaults to False.",
            ] = False,
        ) -> Command | str:
            target = self._resolve_relative(file_path, runtime)
            try:
                validated = validate_path(target)
            except ValueError as exc:
                return f"Error: {exc}"

            namespace_error = self._check_cloud_write_namespace(validated, runtime)
            if namespace_error:
                return namespace_error

            backend = self._get_backend(runtime)
            files_state = runtime.state.get("files") or {}
            doc_id_to_attach: int | None = None

            if (
                self._is_cloud()
                and validated not in files_state
                and isinstance(backend, KBPostgresBackend)
            ):
                loaded = await backend._load_file_data(validated)
                if loaded is None:
                    return f"Error: File '{validated}' not found"
                _, doc_id_to_attach = loaded

            res: EditResult = await backend.aedit(
                validated, old_string, new_string, replace_all=replace_all
            )
            if res.error:
                return res.error

            path = res.path or validated
            files_update = res.files_update or {}
            update: dict[str, Any] = {
                "files": files_update,
                "messages": [
                    ToolMessage(
                        content=(
                            f"Successfully replaced {res.occurrences} instance(s) "
                            f"of the string in '{path}'"
                        ),
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
            if self._is_cloud():
                update["dirty_paths"] = [path]
                if doc_id_to_attach is not None:
                    update["doc_id_by_path"] = {path: doc_id_to_attach}
            return Command(update=update)

        def sync_edit_file(
            file_path: Annotated[
                str,
                "Absolute path to the file to edit. Relative paths resolve against the current cwd.",
            ],
            old_string: Annotated[
                str,
                "Exact text to replace. Must be unique unless replace_all is True.",
            ],
            new_string: Annotated[
                str,
                "Replacement text. Must differ from old_string.",
            ],
            runtime: ToolRuntime[None, SurfSenseFilesystemState],
            *,
            replace_all: Annotated[
                bool,
                "If True, replace all occurrences of old_string. Defaults to False.",
            ] = False,
        ) -> Command | str:
            return self._run_async_blocking(
                async_edit_file(
                    file_path, old_string, new_string, runtime, replace_all=replace_all
                )
            )

        return StructuredTool.from_function(
            name="edit_file",
            description=tool_description,
            func=sync_edit_file,
            coroutine=async_edit_file,
        )

    # ------------------------------------------------------------------ tool: mkdir

    def _create_mkdir_tool(self) -> BaseTool:
        tool_description = (
            self._custom_tool_descriptions.get("mkdir")
            or SURFSENSE_MKDIR_TOOL_DESCRIPTION
        )

        async def async_mkdir(
            path: Annotated[str, "Absolute or relative directory path to create."],
            runtime: ToolRuntime[None, SurfSenseFilesystemState],
        ) -> Command | str:
            target = self._resolve_relative(path, runtime)
            try:
                validated = validate_path(target)
            except ValueError as exc:
                return f"Error: {exc}"

            if self._is_cloud():
                if not (
                    validated.startswith(DOCUMENTS_ROOT + "/")
                    or validated == DOCUMENTS_ROOT
                ):
                    return (
                        "Error: cloud mkdir must target a path under /documents/ "
                        f"(got '{validated}')."
                    )
                return Command(
                    update={
                        "staged_dirs": [validated],
                        "messages": [
                            ToolMessage(
                                content=(
                                    f"Staged directory '{validated}' (will be created "
                                    "at end of turn)."
                                ),
                                tool_call_id=runtime.tool_call_id,
                            )
                        ],
                    }
                )

            backend = self._get_backend(runtime)
            local_method = getattr(backend, "amkdir", None) or getattr(
                backend, "mkdir", None
            )
            if callable(local_method):
                try:
                    res = local_method(validated, parents=True, exist_ok=True)
                    if asyncio.iscoroutine(res):
                        await res
                except TypeError:
                    res = local_method(validated)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as exc:  # pragma: no cover
                    return f"Error: {exc}"
            return f"Created directory {validated}"

        def sync_mkdir(
            path: Annotated[str, "Absolute or relative directory path to create."],
            runtime: ToolRuntime[None, SurfSenseFilesystemState],
        ) -> Command | str:
            return self._run_async_blocking(async_mkdir(path, runtime))

        return StructuredTool.from_function(
            name="mkdir",
            description=tool_description,
            func=sync_mkdir,
            coroutine=async_mkdir,
        )

    # ------------------------------------------------------------------ tool: cd

    def _create_cd_tool(self) -> BaseTool:
        tool_description = (
            self._custom_tool_descriptions.get("cd") or SURFSENSE_CD_TOOL_DESCRIPTION
        )

        async def async_cd(
            path: Annotated[str, "Absolute or relative directory path to switch into."],
            runtime: ToolRuntime[None, SurfSenseFilesystemState],
        ) -> Command | str:
            target = self._resolve_relative(path, runtime)
            try:
                validated = validate_path(target)
            except ValueError as exc:
                return f"Error: {exc}"

            backend = self._get_backend(runtime)
            try:
                infos = await backend.als_info(validated)
            except Exception as exc:  # pragma: no cover - defensive
                return f"Error: {exc}"
            staged_dirs = list(runtime.state.get("staged_dirs") or [])
            files = runtime.state.get("files") or {}
            cwd_exists = (
                bool(infos)
                or validated in staged_dirs
                or any(p == validated for p in files)
                or any(
                    isinstance(p, str) and p.startswith(validated.rstrip("/") + "/")
                    for p in files
                )
                or validated == "/"
                or validated == DOCUMENTS_ROOT
            )
            if not cwd_exists:
                return f"Error: directory '{validated}' not found."
            return Command(
                update={
                    "cwd": validated,
                    "messages": [
                        ToolMessage(
                            content=f"cwd changed to {validated}",
                            tool_call_id=runtime.tool_call_id,
                        )
                    ],
                }
            )

        def sync_cd(
            path: Annotated[str, "Absolute or relative directory path to switch into."],
            runtime: ToolRuntime[None, SurfSenseFilesystemState],
        ) -> Command | str:
            return self._run_async_blocking(async_cd(path, runtime))

        return StructuredTool.from_function(
            name="cd",
            description=tool_description,
            func=sync_cd,
            coroutine=async_cd,
        )

    # ------------------------------------------------------------------ tool: pwd

    def _create_pwd_tool(self) -> BaseTool:
        tool_description = (
            self._custom_tool_descriptions.get("pwd") or SURFSENSE_PWD_TOOL_DESCRIPTION
        )

        def sync_pwd(
            runtime: ToolRuntime[None, SurfSenseFilesystemState],
        ) -> str:
            return self._current_cwd(runtime)

        async def async_pwd(
            runtime: ToolRuntime[None, SurfSenseFilesystemState],
        ) -> str:
            return self._current_cwd(runtime)

        return StructuredTool.from_function(
            name="pwd",
            description=tool_description,
            func=sync_pwd,
            coroutine=async_pwd,
        )

    # ------------------------------------------------------------------ tool: move_file

    def _create_move_file_tool(self) -> BaseTool:
        tool_description = (
            self._custom_tool_descriptions.get("move_file")
            or SURFSENSE_MOVE_FILE_TOOL_DESCRIPTION
        )

        async def async_move_file(
            source_path: Annotated[str, "Absolute or relative source path."],
            destination_path: Annotated[str, "Absolute or relative destination path."],
            runtime: ToolRuntime[None, SurfSenseFilesystemState],
            *,
            overwrite: Annotated[
                bool,
                "If True, replace existing destination. Cloud mode rejects True. Defaults to False.",
            ] = False,
        ) -> Command | str:
            if not source_path.strip() or not destination_path.strip():
                return "Error: source_path and destination_path are required."

            source = self._resolve_move_target_path(source_path, runtime)
            dest = self._resolve_move_target_path(destination_path, runtime)
            try:
                validated_source = validate_path(source)
                validated_dest = validate_path(dest)
            except ValueError as exc:
                return f"Error: {exc}"

            if self._is_cloud():
                return await self._cloud_move_file(
                    runtime,
                    validated_source,
                    validated_dest,
                    overwrite=overwrite,
                )

            backend = self._get_backend(runtime)
            res: WriteResult = await backend.amove(
                validated_source, validated_dest, overwrite=overwrite
            )
            if res.error:
                return res.error
            update: dict[str, Any] = {
                "messages": [
                    ToolMessage(
                        content=f"Moved '{validated_source}' to '{res.path or validated_dest}'",
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
            if res.files_update is not None:
                update["files"] = res.files_update
            return Command(update=update)

        def sync_move_file(
            source_path: Annotated[str, "Absolute or relative source path."],
            destination_path: Annotated[str, "Absolute or relative destination path."],
            runtime: ToolRuntime[None, SurfSenseFilesystemState],
            *,
            overwrite: Annotated[
                bool,
                "If True, replace existing destination. Cloud mode rejects True. Defaults to False.",
            ] = False,
        ) -> Command | str:
            return self._run_async_blocking(
                async_move_file(
                    source_path, destination_path, runtime, overwrite=overwrite
                )
            )

        return StructuredTool.from_function(
            name="move_file",
            description=tool_description,
            func=sync_move_file,
            coroutine=async_move_file,
        )

    async def _cloud_move_file(
        self,
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
        source: str,
        dest: str,
        *,
        overwrite: bool,
    ) -> Command | str:
        backend = self._get_backend(runtime)
        if not isinstance(backend, KBPostgresBackend):
            return "Error: cloud move requires KBPostgresBackend."

        if source == dest:
            return f"Moved '{source}' to '{dest}' (no-op)"
        if overwrite:
            return (
                "Error: overwrite=True is not supported in cloud mode. Move/edit "
                "the destination doc explicitly first."
            )
        if not source.startswith(DOCUMENTS_ROOT + "/"):
            return (
                "Error: cloud move_file source must be under /documents/ (got "
                f"'{source}')."
            )
        if not dest.startswith(DOCUMENTS_ROOT + "/"):
            return (
                "Error: cloud move_file destination must be under /documents/ (got "
                f"'{dest}')."
            )
        anon = runtime.state.get("kb_anon_doc") or {}
        if isinstance(anon, dict):
            anon_path = str(anon.get("path") or "")
            if anon_path and (anon_path in (source, dest)):
                return "Error: the anonymous uploaded document is read-only."

        files = runtime.state.get("files") or {}
        doc_id_by_path = runtime.state.get("doc_id_by_path") or {}
        pending_moves = list(runtime.state.get("pending_moves") or [])

        # Dest collision: occupied in state, in pending moves, or in DB.
        if dest in files:
            return f"Error: destination '{dest}' already exists."
        if any(move.get("dest") == dest for move in pending_moves):
            return f"Error: destination '{dest}' already exists."
        if dest != source:
            existing_dest = await backend._load_file_data(dest)
            if existing_dest is not None:
                return f"Error: destination '{dest}' already exists."

        # Source materialization: lazy load if not in state.
        source_file_data = files.get(source)
        source_doc_id = doc_id_by_path.get(source)
        if source_file_data is None:
            loaded = await backend._load_file_data(source)
            if loaded is None:
                return f"Error: source '{source}' not found."
            source_file_data, loaded_doc_id = loaded
            if source_doc_id is None:
                source_doc_id = loaded_doc_id

        files_update: dict[str, Any] = {source: None, dest: source_file_data}
        update: dict[str, Any] = {
            "files": files_update,
            "pending_moves": [{"source": source, "dest": dest, "overwrite": False}],
            "messages": [
                ToolMessage(
                    content=(
                        f"Moved '{source}' to '{dest}' (will commit at end of turn)."
                    ),
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }

        doc_id_update: dict[str, int | None] = {source: None}
        if source_doc_id is not None:
            doc_id_update[dest] = source_doc_id
        update["doc_id_by_path"] = doc_id_update

        dirty_paths = list(runtime.state.get("dirty_paths") or [])
        if source in dirty_paths:
            new_dirty: list[Any] = [_CLEAR]
            for entry in dirty_paths:
                new_dirty.append(dest if entry == source else entry)
            update["dirty_paths"] = new_dirty
        return Command(update=update)

    # ------------------------------------------------------------------ tool: list_tree

    def _create_list_tree_tool(self) -> BaseTool:
        tool_description = (
            self._custom_tool_descriptions.get("list_tree")
            or SURFSENSE_LIST_TREE_TOOL_DESCRIPTION
        )

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

            target = self._resolve_list_target_path(path, runtime)
            try:
                validated = validate_path(target)
            except ValueError as exc:
                return f"Error: {exc}"

            backend = self._get_backend(runtime)
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
            return self._run_async_blocking(
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
            description=tool_description,
            func=sync_list_tree,
            coroutine=async_list_tree,
        )

    # ------------------------------------------------------------------ tool: execute_code (sandbox)

    def _create_execute_code_tool(self) -> BaseTool:
        def sync_execute_code(
            command: Annotated[
                str, "Python code to execute. Use print() to see output."
            ],
            runtime: ToolRuntime[None, SurfSenseFilesystemState],
            timeout: Annotated[
                int | None,
                "Optional timeout in seconds.",
            ] = None,
        ) -> str:
            if timeout is not None:
                if timeout < 0:
                    return f"Error: timeout must be non-negative, got {timeout}."
                if timeout > self._MAX_EXECUTE_TIMEOUT:
                    return f"Error: timeout {timeout}s exceeds maximum ({self._MAX_EXECUTE_TIMEOUT}s)."
            return self._run_async_blocking(
                self._execute_in_sandbox(command, runtime, timeout)
            )

        async def async_execute_code(
            command: Annotated[
                str, "Python code to execute. Use print() to see output."
            ],
            runtime: ToolRuntime[None, SurfSenseFilesystemState],
            timeout: Annotated[
                int | None,
                "Optional timeout in seconds.",
            ] = None,
        ) -> str:
            if timeout is not None:
                if timeout < 0:
                    return f"Error: timeout must be non-negative, got {timeout}."
                if timeout > self._MAX_EXECUTE_TIMEOUT:
                    return f"Error: timeout {timeout}s exceeds maximum ({self._MAX_EXECUTE_TIMEOUT}s)."
            return await self._execute_in_sandbox(command, runtime, timeout)

        return StructuredTool.from_function(
            name="execute_code",
            description=SURFSENSE_EXECUTE_CODE_TOOL_DESCRIPTION,
            func=sync_execute_code,
            coroutine=async_execute_code,
        )

    @staticmethod
    def _wrap_as_python(code: str) -> str:
        sentinel = f"_PYEOF_{secrets.token_hex(8)}"
        return f"python3 << '{sentinel}'\n{code}\n{sentinel}"

    async def _execute_in_sandbox(
        self,
        command: str,
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
        timeout: int | None,
    ) -> str:
        assert self._thread_id is not None
        command = self._wrap_as_python(command)
        try:
            return await self._try_sandbox_execute(command, runtime, timeout)
        except (DaytonaError, Exception) as first_err:
            logger.warning(
                "Sandbox execute failed for thread %s, retrying: %s",
                self._thread_id,
                first_err,
            )
            try:
                await delete_sandbox(self._thread_id)
            except Exception:
                _evict_sandbox_cache(self._thread_id)
            try:
                return await self._try_sandbox_execute(command, runtime, timeout)
            except Exception:
                logger.exception(
                    "Sandbox retry also failed for thread %s", self._thread_id
                )
                return "Error: Code execution is temporarily unavailable. Please try again."

    async def _try_sandbox_execute(
        self,
        command: str,
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
        timeout: int | None,
    ) -> str:
        sandbox, _is_new = await get_or_create_sandbox(self._thread_id)
        result = await sandbox.aexecute(command, timeout=timeout)
        output = (result.output or "").strip()
        if not output and result.exit_code == 0:
            return (
                "[Code executed successfully but produced no output. "
                "Use print() to display results, then try again.]"
            )
        parts = [result.output]
        if result.exit_code is not None:
            status = "succeeded" if result.exit_code == 0 else "failed"
            parts.append(f"\n[Command {status} with exit code {result.exit_code}]")
        if result.truncated:
            parts.append("\n[Output was truncated due to size limits]")
        return "".join(parts)
