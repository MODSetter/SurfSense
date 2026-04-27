"""Custom filesystem middleware for the SurfSense agent.

This middleware customizes prompts and persists write/edit operations for
`/documents/*` files into SurfSense's `Document`/`Chunk` tables.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
from datetime import UTC, datetime
from typing import Annotated, Any

from daytona.common.errors import DaytonaError
from deepagents import FilesystemMiddleware
from deepagents.backends.protocol import EditResult, WriteResult
from deepagents.backends.utils import validate_path
from deepagents.middleware.filesystem import FilesystemState
from fractional_indexing import generate_key_between
from langchain.tools import ToolRuntime
from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command
from sqlalchemy import delete, select

from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.middleware.multi_root_local_folder_backend import (
    MultiRootLocalFolderBackend,
)
from app.agents.new_chat.sandbox import (
    _evict_sandbox_cache,
    delete_sandbox,
    get_or_create_sandbox,
    is_sandbox_enabled,
)
from app.db import Chunk, Document, DocumentType, Folder, shielded_async_session
from app.indexing_pipeline.document_chunker import chunk_text
from app.utils.document_converters import (
    embed_texts,
    generate_content_hash,
    generate_unique_identifier_hash,
)

logger = logging.getLogger(__name__)

# =============================================================================
# System Prompt (injected into every model call by wrap_model_call)
# =============================================================================

SURFSENSE_FILESYSTEM_SYSTEM_PROMPT = """## Following Conventions

- Read files before editing — understand existing content before making changes.
- Mimic existing style, naming conventions, and patterns.
- Never claim a file was created/updated unless filesystem tool output confirms success.
- If a file write/edit fails, explicitly report the failure.

## Filesystem Tools

All file paths must start with a `/`.
- ls: list files and directories at a given path.
- read_file: read a file from the filesystem.
- write_file: create a temporary file in the session (not persisted).
- edit_file: edit a file in the session (not persisted for /documents/ files).
- glob: find files matching a pattern (e.g., "**/*.xml").
- grep: search for text within files.
- save_document: **permanently** save a new document to the user's knowledge
  base. Use only when the user explicitly asks to save/create a document.

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

## User-Mentioned Documents

When the `ls` output tags a file with `[MENTIONED BY USER — read deeply]`,
the user **explicitly selected** that document. These files are your highest-
priority sources:
1. **Always read them thoroughly** — scan the full `<chunk_index>`, then read
   all major sections, not just matched chunks.
2. **Prefer their content** over other search results when answering.
3. **Cite from them first** whenever applicable.
"""

# =============================================================================
# Per-Tool Descriptions (shown to the LLM as the tool's docstring)
# =============================================================================

SURFSENSE_LIST_FILES_TOOL_DESCRIPTION = """Lists files and directories at the given path.
"""

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

SURFSENSE_WRITE_FILE_TOOL_DESCRIPTION = """Writes a new text file to the in-memory filesystem (session-only).

Use this to create scratch/working files during the conversation. Files created
here are ephemeral and will not be saved to the user's knowledge base.

To permanently save a document to the user's knowledge base, use the
`save_document` tool instead.

Supported outputs include common LLM-friendly text formats like markdown, json,
yaml, csv, xml, html, css, sql, and code files.

When creating content from open-ended prompts, produce concrete and useful text,
not placeholders. Avoid adding dates/timestamps unless the user explicitly asks
for them.
"""

SURFSENSE_EDIT_FILE_TOOL_DESCRIPTION = """Performs exact string replacements in files.

IMPORTANT:
- Read the file before editing.
- Preserve exact indentation and formatting.
- Edits to documents under `/documents/` are session-only (not persisted to the
  database) because those files use an XML citation wrapper around the original
  content.
"""

SURFSENSE_MOVE_FILE_TOOL_DESCRIPTION = """Moves or renames a file or folder.

Use absolute paths for both source and destination.

Notes:
- In local-folder mode, paths should use mount prefixes (e.g., /<mount>/foo.txt).
- Rename is a special case of move (same folder, different filename).
- Cross-mount moves are not supported.
"""

SURFSENSE_LIST_TREE_TOOL_DESCRIPTION = """Lists files/folders recursively in a single bounded call.

Use this in desktop local-folder mode to discover nested files at scale.

Args:
- path: absolute mount-prefixed path (e.g., /<mount>/src) or "/" for mount roots.
- max_depth: recursion depth limit (default 8).
- page_size: maximum number of entries returned (max 1000).
- include_files/include_dirs: filter returned entry types.

Returns JSON with:
- entries: [{path, is_dir, size, modified_at, depth}]
- truncated: true when additional entries were omitted due to page_size
"""

SURFSENSE_GLOB_TOOL_DESCRIPTION = """Find files matching a glob pattern.

Supports standard glob patterns: `*`, `**`, `?`.
Returns absolute file paths.
"""

SURFSENSE_GREP_TOOL_DESCRIPTION = """Search for a literal text pattern across files.

Use this to locate relevant document files/chunks before reading full files.
"""

SURFSENSE_EXECUTE_CODE_TOOL_DESCRIPTION = """Executes Python code in an isolated sandbox environment.

Common data-science packages are pre-installed (pandas, numpy, matplotlib,
scipy, scikit-learn).

When to use this tool: use execute_code for numerical computation, data
analysis, statistics, and any task that benefits from running Python code.
Never perform arithmetic manually when this tool is available.

Usage notes:
- No outbound network access.
- Returns combined stdout/stderr with exit code.
- Use print() to produce output.
- You can create files, run shell commands via subprocess or os.system(),
  and use any standard library module.
- Use the optional timeout parameter to override the default timeout.
"""

SURFSENSE_SAVE_DOCUMENT_TOOL_DESCRIPTION = """Permanently saves a document to the user's knowledge base.

This is an expensive operation — it creates a new Document record in the
database, chunks the content, and generates embeddings for search.

Use ONLY when the user explicitly asks to save/create/store a document.
Do NOT use this for scratch work; use `write_file` for temporary files.

Args:
  title: The document title (e.g., "Meeting Notes 2025-06-01").
  content: The plain-text or markdown content to save. Do NOT include XML
           citation wrappers — pass only the actual document text.
  folder_path: Optional folder path under /documents/ (e.g., "Work/Notes").
               Folders are created automatically if they don't exist.
"""


class SurfSenseFilesystemMiddleware(FilesystemMiddleware):
    """SurfSense-specific filesystem middleware with DB persistence for docs."""

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

        system_prompt = SURFSENSE_FILESYSTEM_SYSTEM_PROMPT
        if self._sandbox_available:
            system_prompt += (
                "\n- execute_code: run Python code in an isolated sandbox."
                "\n\n## Code Execution"
                "\n\nUse execute_code whenever a task benefits from running code."
                " Never perform arithmetic manually."
                "\n\nDocuments here are XML-wrapped markdown, not raw data files."
                " To work with them programmatically, read the document first,"
                " extract the data, write it as a clean file (CSV, JSON, etc.),"
                " and then run your code against it."
            )
        if filesystem_mode == FilesystemMode.DESKTOP_LOCAL_FOLDER:
            system_prompt += (
                "\n- move_file: move or rename files/folders in local-folder mode."
                "\n- list_tree: recursively list nested local paths in one bounded response."
                "\n\n## Local Folder Mode"
                "\n\nThis chat is running in desktop local-folder mode."
                " Keep all file operations local. Do not use save_document."
                " Always use mount-prefixed absolute paths like /<folder>/file.ext."
                " If you are unsure which mounts are available, call ls('/') first."
                " For big trees: use list_tree, then grep, then read_file."
            )

        super().__init__(
            backend=backend,
            system_prompt=system_prompt,
            custom_tool_descriptions={
                "ls": SURFSENSE_LIST_FILES_TOOL_DESCRIPTION,
                "read_file": SURFSENSE_READ_FILE_TOOL_DESCRIPTION,
                "write_file": SURFSENSE_WRITE_FILE_TOOL_DESCRIPTION,
                "edit_file": SURFSENSE_EDIT_FILE_TOOL_DESCRIPTION,
                "move_file": SURFSENSE_MOVE_FILE_TOOL_DESCRIPTION,
                "list_tree": SURFSENSE_LIST_TREE_TOOL_DESCRIPTION,
                "glob": SURFSENSE_GLOB_TOOL_DESCRIPTION,
                "grep": SURFSENSE_GREP_TOOL_DESCRIPTION,
            },
            tool_token_limit_before_evict=tool_token_limit_before_evict,
            max_execute_timeout=self._MAX_EXECUTE_TIMEOUT,
        )
        self.tools = [t for t in self.tools if t.name != "execute"]
        if self._filesystem_mode == FilesystemMode.DESKTOP_LOCAL_FOLDER:
            self.tools.append(self._create_move_file_tool())
            self.tools.append(self._create_list_tree_tool())
        if self._should_persist_documents():
            self.tools.append(self._create_save_document_tool())
        if self._sandbox_available:
            self.tools.append(self._create_execute_code_tool())

    @staticmethod
    def _run_async_blocking(coro: Any) -> Any:
        """Run async coroutine from sync code path when no event loop is running."""
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                return "Error: sync filesystem persistence not supported inside an active event loop."
        except RuntimeError:
            pass
        return asyncio.run(coro)

    @staticmethod
    def _parse_virtual_path(file_path: str) -> tuple[list[str], str]:
        """Parse /documents/... path into folder parts and a document title."""
        if not file_path.startswith("/documents/"):
            return [], ""
        rel = file_path[len("/documents/") :].strip("/")
        if not rel:
            return [], ""
        parts = [part for part in rel.split("/") if part]
        file_name = parts[-1]
        title = file_name[:-4] if file_name.lower().endswith(".xml") else file_name
        return parts[:-1], title

    async def _ensure_folder_hierarchy(
        self,
        *,
        folder_parts: list[str],
        search_space_id: int,
    ) -> int | None:
        """Ensure folder hierarchy exists and return leaf folder ID."""
        if not folder_parts:
            return None
        async with shielded_async_session() as session:
            parent_id: int | None = None
            for name in folder_parts:
                result = await session.execute(
                    select(Folder).where(
                        Folder.search_space_id == search_space_id,
                        Folder.parent_id == parent_id
                        if parent_id is not None
                        else Folder.parent_id.is_(None),
                        Folder.name == name,
                    )
                )
                folder = result.scalar_one_or_none()
                if folder is None:
                    sibling_result = await session.execute(
                        select(Folder.position)
                        .where(
                            Folder.search_space_id == search_space_id,
                            Folder.parent_id == parent_id
                            if parent_id is not None
                            else Folder.parent_id.is_(None),
                        )
                        .order_by(Folder.position.desc())
                        .limit(1)
                    )
                    last_position = sibling_result.scalar_one_or_none()
                    folder = Folder(
                        name=name,
                        position=generate_key_between(last_position, None),
                        parent_id=parent_id,
                        search_space_id=search_space_id,
                        created_by_id=self._created_by_id,
                        updated_at=datetime.now(UTC),
                    )
                    session.add(folder)
                    await session.flush()
                parent_id = folder.id
            await session.commit()
            return parent_id

    async def _persist_new_document(
        self, *, file_path: str, content: str
    ) -> dict[str, Any] | str:
        """Persist a new NOTE document from a newly written file.

        Returns a dict with document metadata on success, or an error string.
        """
        if self._search_space_id is None:
            return {}
        folder_parts, title = self._parse_virtual_path(file_path)
        if not title:
            return "Error: write_file for document persistence requires path under /documents/<name>.xml"
        folder_id = await self._ensure_folder_hierarchy(
            folder_parts=folder_parts,
            search_space_id=self._search_space_id,
        )
        async with shielded_async_session() as session:
            content_hash = generate_content_hash(content, self._search_space_id)
            existing = await session.execute(
                select(Document.id).where(Document.content_hash == content_hash)
            )
            if existing.scalar_one_or_none() is not None:
                return "Error: A document with identical content already exists."
            unique_identifier_hash = generate_unique_identifier_hash(
                DocumentType.NOTE,
                file_path,
                self._search_space_id,
            )
            doc = Document(
                title=title,
                document_type=DocumentType.NOTE,
                document_metadata={"virtual_path": file_path},
                content=content,
                content_hash=content_hash,
                unique_identifier_hash=unique_identifier_hash,
                source_markdown=content,
                search_space_id=self._search_space_id,
                folder_id=folder_id,
                created_by_id=self._created_by_id,
                updated_at=datetime.now(UTC),
            )
            session.add(doc)
            await session.flush()

            summary_embedding = embed_texts([content])[0]
            doc.embedding = summary_embedding
            chunk_texts = chunk_text(content)
            if chunk_texts:
                chunk_embeddings = embed_texts(chunk_texts)
                chunks = [
                    Chunk(document_id=doc.id, content=text, embedding=embedding)
                    for text, embedding in zip(
                        chunk_texts, chunk_embeddings, strict=True
                    )
                ]
                session.add_all(chunks)
            await session.commit()

            return {
                "id": doc.id,
                "title": title,
                "documentType": DocumentType.NOTE.value,
                "searchSpaceId": self._search_space_id,
                "folderId": folder_id,
                "createdById": str(self._created_by_id)
                if self._created_by_id
                else None,
            }

    async def _persist_edited_document(
        self, *, file_path: str, updated_content: str
    ) -> str | None:
        """Persist edits for an existing NOTE document and recreate chunks."""
        if self._search_space_id is None:
            return None
        unique_identifier_hash = generate_unique_identifier_hash(
            DocumentType.NOTE,
            file_path,
            self._search_space_id,
        )
        doc_id_from_xml: int | None = None
        match = re.search(r"<document_id>\s*(\d+)\s*</document_id>", updated_content)
        if match:
            doc_id_from_xml = int(match.group(1))
        async with shielded_async_session() as session:
            doc_result = await session.execute(
                select(Document).where(
                    Document.search_space_id == self._search_space_id,
                    Document.unique_identifier_hash == unique_identifier_hash,
                )
            )
            document = doc_result.scalar_one_or_none()
            if document is None and doc_id_from_xml is not None:
                by_id_result = await session.execute(
                    select(Document).where(
                        Document.search_space_id == self._search_space_id,
                        Document.id == doc_id_from_xml,
                    )
                )
                document = by_id_result.scalar_one_or_none()
            if document is None:
                return "Error: Could not map edited file to an existing document."

            document.content = updated_content
            document.source_markdown = updated_content
            document.content_hash = generate_content_hash(
                updated_content, self._search_space_id
            )
            document.updated_at = datetime.now(UTC)
            if not document.document_metadata:
                document.document_metadata = {}
            document.document_metadata["virtual_path"] = file_path

            summary_embedding = embed_texts([updated_content])[0]
            document.embedding = summary_embedding

            await session.execute(delete(Chunk).where(Chunk.document_id == document.id))
            chunk_texts = chunk_text(updated_content)
            if chunk_texts:
                chunk_embeddings = embed_texts(chunk_texts)
                session.add_all(
                    [
                        Chunk(
                            document_id=document.id, content=text, embedding=embedding
                        )
                        for text, embedding in zip(
                            chunk_texts, chunk_embeddings, strict=True
                        )
                    ]
                )
            await session.commit()
        return None

    def _create_save_document_tool(self) -> BaseTool:
        """Create save_document tool that persists a new document to the KB."""

        def sync_save_document(
            title: Annotated[str, "Title for the new document."],
            content: Annotated[
                str,
                "Plain-text or markdown content to save. Do NOT include XML wrappers.",
            ],
            runtime: ToolRuntime[None, FilesystemState],
            folder_path: Annotated[
                str,
                "Optional folder path under /documents/ (e.g. 'Work/Notes'). Created automatically.",
            ] = "",
        ) -> Command | str:
            if not content.strip():
                return "Error: content cannot be empty."
            file_name = re.sub(r'[\\/:*?"<>|]+', "_", title).strip() or "untitled"
            if not file_name.lower().endswith(".xml"):
                file_name = f"{file_name}.xml"
            folder = folder_path.strip().strip("/") if folder_path else ""
            virtual_path = (
                f"/documents/{folder}/{file_name}"
                if folder
                else f"/documents/{file_name}"
            )

            persist_result = self._run_async_blocking(
                self._persist_new_document(file_path=virtual_path, content=content)
            )
            if isinstance(persist_result, str):
                return persist_result
            if isinstance(persist_result, dict) and persist_result.get("id"):
                dispatch_custom_event("document_created", persist_result)
            return f"Document '{title}' saved to knowledge base (path: {virtual_path})."

        async def async_save_document(
            title: Annotated[str, "Title for the new document."],
            content: Annotated[
                str,
                "Plain-text or markdown content to save. Do NOT include XML wrappers.",
            ],
            runtime: ToolRuntime[None, FilesystemState],
            folder_path: Annotated[
                str,
                "Optional folder path under /documents/ (e.g. 'Work/Notes'). Created automatically.",
            ] = "",
        ) -> Command | str:
            if not content.strip():
                return "Error: content cannot be empty."
            file_name = re.sub(r'[\\/:*?"<>|]+', "_", title).strip() or "untitled"
            if not file_name.lower().endswith(".xml"):
                file_name = f"{file_name}.xml"
            folder = folder_path.strip().strip("/") if folder_path else ""
            virtual_path = (
                f"/documents/{folder}/{file_name}"
                if folder
                else f"/documents/{file_name}"
            )

            persist_result = await self._persist_new_document(
                file_path=virtual_path, content=content
            )
            if isinstance(persist_result, str):
                return persist_result
            if isinstance(persist_result, dict) and persist_result.get("id"):
                dispatch_custom_event("document_created", persist_result)
            return f"Document '{title}' saved to knowledge base (path: {virtual_path})."

        return StructuredTool.from_function(
            name="save_document",
            description=SURFSENSE_SAVE_DOCUMENT_TOOL_DESCRIPTION,
            func=sync_save_document,
            coroutine=async_save_document,
        )

    def _create_execute_code_tool(self) -> BaseTool:
        """Create execute_code tool backed by a Daytona sandbox."""

        def sync_execute_code(
            command: Annotated[
                str, "Python code to execute. Use print() to see output."
            ],
            runtime: ToolRuntime[None, FilesystemState],
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
            runtime: ToolRuntime[None, FilesystemState],
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
        """Wrap Python code in a shell invocation for the sandbox."""
        sentinel = f"_PYEOF_{secrets.token_hex(8)}"
        return f"python3 << '{sentinel}'\n{code}\n{sentinel}"

    async def _execute_in_sandbox(
        self,
        command: str,
        runtime: ToolRuntime[None, FilesystemState],
        timeout: int | None,
    ) -> str:
        """Core logic: get sandbox, sync files, run command, handle retries."""
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
        runtime: ToolRuntime[None, FilesystemState],
        timeout: int | None,
    ) -> str:
        sandbox, _is_new = await get_or_create_sandbox(self._thread_id)
        # NOTE: sync_files_to_sandbox is intentionally disabled.
        # The virtual FS contains XML-wrapped KB documents whose paths
        # would double-nest under SANDBOX_DOCUMENTS_ROOT (e.g.
        # /home/daytona/documents/documents/Report.xml) and uploading
        # all KB docs on the first execute_code call adds significant
        # latency.  Re-enable once path mapping is fixed and upload is
        # limited to user-created scratch files.
        # files = runtime.state.get("files") or {}
        # await sync_files_to_sandbox(self._thread_id, files, sandbox, is_new)
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

    def _create_write_file_tool(self) -> BaseTool:
        """Create write_file — ephemeral for /documents/*, persisted otherwise."""
        tool_description = (
            self._custom_tool_descriptions.get("write_file")
            or SURFSENSE_WRITE_FILE_TOOL_DESCRIPTION
        )

        def sync_write_file(
            file_path: Annotated[
                str,
                "Absolute path where the file should be created. Must be absolute, not relative.",
            ],
            content: Annotated[
                str,
                "The text content to write to the file. This parameter is required.",
            ],
            runtime: ToolRuntime[None, FilesystemState],
        ) -> Command | str:
            resolved_backend = self._get_backend(runtime)
            target_path = self._resolve_write_target_path(file_path, runtime)
            try:
                validated_path = validate_path(target_path)
            except ValueError as exc:
                return f"Error: {exc}"
            res: WriteResult = resolved_backend.write(validated_path, content)
            if res.error:
                return res.error
            verify_error = self._verify_written_content_sync(
                backend=resolved_backend,
                path=validated_path,
                expected_content=content,
            )
            if verify_error:
                return verify_error

            if self._should_persist_documents() and not self._is_kb_document(
                validated_path
            ):
                persist_result = self._run_async_blocking(
                    self._persist_new_document(
                        file_path=validated_path, content=content
                    )
                )
                if isinstance(persist_result, str):
                    return persist_result
                if isinstance(persist_result, dict) and persist_result.get("id"):
                    dispatch_custom_event("document_created", persist_result)

            if res.files_update is not None:
                return Command(
                    update={
                        "files": res.files_update,
                        "messages": [
                            ToolMessage(
                                content=f"Updated file {res.path}",
                                tool_call_id=runtime.tool_call_id,
                            )
                        ],
                    }
                )
            return f"Updated file {res.path}"

        async def async_write_file(
            file_path: Annotated[
                str,
                "Absolute path where the file should be created. Must be absolute, not relative.",
            ],
            content: Annotated[
                str,
                "The text content to write to the file. This parameter is required.",
            ],
            runtime: ToolRuntime[None, FilesystemState],
        ) -> Command | str:
            resolved_backend = self._get_backend(runtime)
            target_path = self._resolve_write_target_path(file_path, runtime)
            try:
                validated_path = validate_path(target_path)
            except ValueError as exc:
                return f"Error: {exc}"
            res: WriteResult = await resolved_backend.awrite(validated_path, content)
            if res.error:
                return res.error
            verify_error = await self._verify_written_content_async(
                backend=resolved_backend,
                path=validated_path,
                expected_content=content,
            )
            if verify_error:
                return verify_error

            if self._should_persist_documents() and not self._is_kb_document(
                validated_path
            ):
                persist_result = await self._persist_new_document(
                    file_path=validated_path,
                    content=content,
                )
                if isinstance(persist_result, str):
                    return persist_result
                if isinstance(persist_result, dict) and persist_result.get("id"):
                    dispatch_custom_event("document_created", persist_result)

            if res.files_update is not None:
                return Command(
                    update={
                        "files": res.files_update,
                        "messages": [
                            ToolMessage(
                                content=f"Updated file {res.path}",
                                tool_call_id=runtime.tool_call_id,
                            )
                        ],
                    }
                )
            return f"Updated file {res.path}"

        return StructuredTool.from_function(
            name="write_file",
            description=tool_description,
            func=sync_write_file,
            coroutine=async_write_file,
        )

    @staticmethod
    def _is_kb_document(path: str) -> bool:
        """Return True for paths under /documents/ (KB-sourced, XML-wrapped)."""
        return path.startswith("/documents/")

    def _should_persist_documents(self) -> bool:
        """Only cloud mode persists file content to Document/Chunk tables."""
        return self._filesystem_mode == FilesystemMode.CLOUD

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
        runtime: ToolRuntime[None, FilesystemState],
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

    def _get_contract_suggested_path(
        self, runtime: ToolRuntime[None, FilesystemState]
    ) -> str:
        contract = runtime.state.get("file_operation_contract") or {}
        suggested = contract.get("suggested_path")
        if isinstance(suggested, str) and suggested.strip():
            return self._normalize_absolute_path(suggested)
        return "/notes.md"

    def _resolve_write_target_path(
        self,
        file_path: str,
        runtime: ToolRuntime[None, FilesystemState],
    ) -> str:
        candidate = file_path.strip()
        if not candidate:
            return self._get_contract_suggested_path(runtime)
        if self._filesystem_mode == FilesystemMode.DESKTOP_LOCAL_FOLDER:
            return self._normalize_local_mount_path(candidate, runtime)
        if not candidate.startswith("/"):
            return f"/{candidate.lstrip('/')}"
        return candidate

    def _resolve_move_target_path(
        self,
        file_path: str,
        runtime: ToolRuntime[None, FilesystemState],
    ) -> str:
        candidate = file_path.strip()
        if not candidate:
            return ""
        if self._filesystem_mode == FilesystemMode.DESKTOP_LOCAL_FOLDER:
            return self._normalize_local_mount_path(candidate, runtime)
        if not candidate.startswith("/"):
            return f"/{candidate.lstrip('/')}"
        return candidate

    def _resolve_list_target_path(
        self,
        path: str,
        runtime: ToolRuntime[None, FilesystemState],
    ) -> str:
        candidate = path.strip() or "/"
        if candidate == "/":
            return "/"
        if self._filesystem_mode == FilesystemMode.DESKTOP_LOCAL_FOLDER:
            return self._normalize_local_mount_path(candidate, runtime)
        if not candidate.startswith("/"):
            return f"/{candidate.lstrip('/')}"
        return candidate

    @staticmethod
    def _is_error_text(value: str) -> bool:
        return value.startswith("Error:")

    @staticmethod
    def _read_for_verification_sync(backend: Any, path: str) -> str:
        read_raw = getattr(backend, "read_raw", None)
        if callable(read_raw):
            return read_raw(path)
        return backend.read(path, offset=0, limit=200000)

    @staticmethod
    async def _read_for_verification_async(backend: Any, path: str) -> str:
        aread_raw = getattr(backend, "aread_raw", None)
        if callable(aread_raw):
            return await aread_raw(path)
        return await backend.aread(path, offset=0, limit=200000)

    def _verify_written_content_sync(
        self,
        *,
        backend: Any,
        path: str,
        expected_content: str,
    ) -> str | None:
        actual = self._read_for_verification_sync(backend, path)
        if self._is_error_text(actual):
            return f"Error: could not verify written file '{path}'."
        if actual.rstrip() != expected_content.rstrip():
            return (
                "Error: file write verification failed; expected content was not fully written "
                f"to '{path}'."
            )
        return None

    async def _verify_written_content_async(
        self,
        *,
        backend: Any,
        path: str,
        expected_content: str,
    ) -> str | None:
        actual = await self._read_for_verification_async(backend, path)
        if self._is_error_text(actual):
            return f"Error: could not verify written file '{path}'."
        if actual.rstrip() != expected_content.rstrip():
            return (
                "Error: file write verification failed; expected content was not fully written "
                f"to '{path}'."
            )
        return None

    def _verify_edited_content_sync(
        self,
        *,
        backend: Any,
        path: str,
        new_string: str,
    ) -> tuple[str | None, str | None]:
        updated_content = self._read_for_verification_sync(backend, path)
        if self._is_error_text(updated_content):
            return (
                f"Error: could not verify edited file '{path}'.",
                None,
            )
        if new_string and new_string not in updated_content:
            return (
                "Error: edit verification failed; updated content was not found in "
                f"'{path}'.",
                None,
            )
        return None, updated_content

    async def _verify_edited_content_async(
        self,
        *,
        backend: Any,
        path: str,
        new_string: str,
    ) -> tuple[str | None, str | None]:
        updated_content = await self._read_for_verification_async(backend, path)
        if self._is_error_text(updated_content):
            return (
                f"Error: could not verify edited file '{path}'.",
                None,
            )
        if new_string and new_string not in updated_content:
            return (
                "Error: edit verification failed; updated content was not found in "
                f"'{path}'.",
                None,
            )
        return None, updated_content

    def _create_move_file_tool(self) -> BaseTool:
        """Create move_file for desktop local-folder mode."""
        tool_description = (
            self._custom_tool_descriptions.get("move_file")
            or SURFSENSE_MOVE_FILE_TOOL_DESCRIPTION
        )

        def sync_move_file(
            source_path: Annotated[
                str,
                "Absolute source path to move from.",
            ],
            destination_path: Annotated[
                str,
                "Absolute destination path to move to.",
            ],
            runtime: ToolRuntime[None, FilesystemState],
            *,
            overwrite: Annotated[
                bool,
                "If True, replace an existing destination file. Defaults to False.",
            ] = False,
        ) -> Command | str:
            if self._filesystem_mode != FilesystemMode.DESKTOP_LOCAL_FOLDER:
                return (
                    "Error: move_file is only available in desktop local-folder mode."
                )

            if not source_path.strip() or not destination_path.strip():
                return "Error: source_path and destination_path are required."

            resolved_backend = self._get_backend(runtime)
            source_target = self._resolve_move_target_path(source_path, runtime)
            destination_target = self._resolve_move_target_path(
                destination_path, runtime
            )
            try:
                validated_source = validate_path(source_target)
                validated_destination = validate_path(destination_target)
            except ValueError as exc:
                return f"Error: {exc}"
            res: WriteResult = resolved_backend.move(
                validated_source,
                validated_destination,
                overwrite=overwrite,
            )
            if res.error:
                return res.error
            if res.files_update is not None:
                return Command(
                    update={
                        "files": res.files_update,
                        "messages": [
                            ToolMessage(
                                content=(
                                    f"Moved '{validated_source}' to "
                                    f"'{res.path or validated_destination}'"
                                ),
                                tool_call_id=runtime.tool_call_id,
                            )
                        ],
                    }
                )
            return (
                f"Moved '{validated_source}' to '{res.path or validated_destination}'"
            )

        async def async_move_file(
            source_path: Annotated[
                str,
                "Absolute source path to move from.",
            ],
            destination_path: Annotated[
                str,
                "Absolute destination path to move to.",
            ],
            runtime: ToolRuntime[None, FilesystemState],
            *,
            overwrite: Annotated[
                bool,
                "If True, replace an existing destination file. Defaults to False.",
            ] = False,
        ) -> Command | str:
            if self._filesystem_mode != FilesystemMode.DESKTOP_LOCAL_FOLDER:
                return (
                    "Error: move_file is only available in desktop local-folder mode."
                )

            if not source_path.strip() or not destination_path.strip():
                return "Error: source_path and destination_path are required."

            resolved_backend = self._get_backend(runtime)
            source_target = self._resolve_move_target_path(source_path, runtime)
            destination_target = self._resolve_move_target_path(
                destination_path, runtime
            )
            try:
                validated_source = validate_path(source_target)
                validated_destination = validate_path(destination_target)
            except ValueError as exc:
                return f"Error: {exc}"
            res: WriteResult = await resolved_backend.amove(
                validated_source,
                validated_destination,
                overwrite=overwrite,
            )
            if res.error:
                return res.error
            if res.files_update is not None:
                return Command(
                    update={
                        "files": res.files_update,
                        "messages": [
                            ToolMessage(
                                content=(
                                    f"Moved '{validated_source}' to "
                                    f"'{res.path or validated_destination}'"
                                ),
                                tool_call_id=runtime.tool_call_id,
                            )
                        ],
                    }
                )
            return (
                f"Moved '{validated_source}' to '{res.path or validated_destination}'"
            )

        return StructuredTool.from_function(
            name="move_file",
            description=tool_description,
            func=sync_move_file,
            coroutine=async_move_file,
        )

    def _create_list_tree_tool(self) -> BaseTool:
        """Create list_tree for desktop local-folder mode."""
        tool_description = (
            self._custom_tool_descriptions.get("list_tree")
            or SURFSENSE_LIST_TREE_TOOL_DESCRIPTION
        )

        def sync_list_tree(
            runtime: ToolRuntime[None, FilesystemState],
            *,
            path: Annotated[
                str,
                "Absolute path to list from. Use '/' for mount roots.",
            ] = "/",
            max_depth: Annotated[
                int,
                "Maximum recursion depth to traverse. Defaults to 8.",
            ] = 8,
            page_size: Annotated[
                int,
                "Maximum number of entries to return. Defaults to 500 (max 1000).",
            ] = 500,
            include_files: Annotated[
                bool,
                "Whether file entries should be included.",
            ] = True,
            include_dirs: Annotated[
                bool,
                "Whether directory entries should be included.",
            ] = True,
        ) -> str:
            if self._filesystem_mode != FilesystemMode.DESKTOP_LOCAL_FOLDER:
                return (
                    "Error: list_tree is only available in desktop local-folder mode."
                )
            if max_depth < 0:
                return "Error: max_depth must be >= 0."
            if page_size < 1:
                return "Error: page_size must be >= 1."
            if not include_files and not include_dirs:
                return "Error: include_files and include_dirs cannot both be false."

            resolved_backend = self._get_backend(runtime)
            target_path = self._resolve_list_target_path(path, runtime)
            try:
                validated_path = validate_path(target_path)
            except ValueError as exc:
                return f"Error: {exc}"

            result = resolved_backend.list_tree(
                validated_path,
                max_depth=max_depth,
                page_size=page_size,
                include_files=include_files,
                include_dirs=include_dirs,
            )
            error = result.get("error") if isinstance(result, dict) else None
            if isinstance(error, str) and error:
                return error
            return json.dumps(result, ensure_ascii=True)

        async def async_list_tree(
            runtime: ToolRuntime[None, FilesystemState],
            *,
            path: Annotated[
                str,
                "Absolute path to list from. Use '/' for mount roots.",
            ] = "/",
            max_depth: Annotated[
                int,
                "Maximum recursion depth to traverse. Defaults to 8.",
            ] = 8,
            page_size: Annotated[
                int,
                "Maximum number of entries to return. Defaults to 500 (max 1000).",
            ] = 500,
            include_files: Annotated[
                bool,
                "Whether file entries should be included.",
            ] = True,
            include_dirs: Annotated[
                bool,
                "Whether directory entries should be included.",
            ] = True,
        ) -> str:
            if self._filesystem_mode != FilesystemMode.DESKTOP_LOCAL_FOLDER:
                return (
                    "Error: list_tree is only available in desktop local-folder mode."
                )
            if max_depth < 0:
                return "Error: max_depth must be >= 0."
            if page_size < 1:
                return "Error: page_size must be >= 1."
            if not include_files and not include_dirs:
                return "Error: include_files and include_dirs cannot both be false."

            resolved_backend = self._get_backend(runtime)
            target_path = self._resolve_list_target_path(path, runtime)
            try:
                validated_path = validate_path(target_path)
            except ValueError as exc:
                return f"Error: {exc}"

            result = await resolved_backend.alist_tree(
                validated_path,
                max_depth=max_depth,
                page_size=page_size,
                include_files=include_files,
                include_dirs=include_dirs,
            )
            error = result.get("error") if isinstance(result, dict) else None
            if isinstance(error, str) and error:
                return error
            return json.dumps(result, ensure_ascii=True)

        return StructuredTool.from_function(
            name="list_tree",
            description=tool_description,
            func=sync_list_tree,
            coroutine=async_list_tree,
        )

    def _create_edit_file_tool(self) -> BaseTool:
        """Create edit_file with DB persistence (skipped for KB documents)."""
        tool_description = (
            self._custom_tool_descriptions.get("edit_file")
            or SURFSENSE_EDIT_FILE_TOOL_DESCRIPTION
        )

        def sync_edit_file(
            file_path: Annotated[
                str,
                "Absolute path to the file to edit. Must be absolute, not relative.",
            ],
            old_string: Annotated[
                str,
                "The exact text to find and replace. Must be unique in the file unless replace_all is True.",
            ],
            new_string: Annotated[
                str,
                "The text to replace old_string with. Must be different from old_string.",
            ],
            runtime: ToolRuntime[None, FilesystemState],
            *,
            replace_all: Annotated[
                bool,
                "If True, replace all occurrences of old_string. If False (default), old_string must be unique.",
            ] = False,
        ) -> Command | str:
            resolved_backend = self._get_backend(runtime)
            target_path = self._resolve_write_target_path(file_path, runtime)
            try:
                validated_path = validate_path(target_path)
            except ValueError as exc:
                return f"Error: {exc}"
            res: EditResult = resolved_backend.edit(
                validated_path,
                old_string,
                new_string,
                replace_all=replace_all,
            )
            if res.error:
                return res.error

            verify_error, updated_content = self._verify_edited_content_sync(
                backend=resolved_backend,
                path=validated_path,
                new_string=new_string,
            )
            if verify_error:
                return verify_error

            if self._should_persist_documents() and not self._is_kb_document(
                validated_path
            ):
                if updated_content is None:
                    return (
                        f"Error: could not reload edited file '{validated_path}' for "
                        "persistence."
                    )
                persist_result = self._run_async_blocking(
                    self._persist_edited_document(
                        file_path=validated_path,
                        updated_content=updated_content,
                    )
                )
                if isinstance(persist_result, str):
                    return persist_result

            if res.files_update is not None:
                return Command(
                    update={
                        "files": res.files_update,
                        "messages": [
                            ToolMessage(
                                content=f"Successfully replaced {res.occurrences} instance(s) of the string in '{res.path}'",
                                tool_call_id=runtime.tool_call_id,
                            )
                        ],
                    }
                )
            return f"Successfully replaced {res.occurrences} instance(s) of the string in '{res.path}'"

        async def async_edit_file(
            file_path: Annotated[
                str,
                "Absolute path to the file to edit. Must be absolute, not relative.",
            ],
            old_string: Annotated[
                str,
                "The exact text to find and replace. Must be unique in the file unless replace_all is True.",
            ],
            new_string: Annotated[
                str,
                "The text to replace old_string with. Must be different from old_string.",
            ],
            runtime: ToolRuntime[None, FilesystemState],
            *,
            replace_all: Annotated[
                bool,
                "If True, replace all occurrences of old_string. If False (default), old_string must be unique.",
            ] = False,
        ) -> Command | str:
            resolved_backend = self._get_backend(runtime)
            target_path = self._resolve_write_target_path(file_path, runtime)
            try:
                validated_path = validate_path(target_path)
            except ValueError as exc:
                return f"Error: {exc}"
            res: EditResult = await resolved_backend.aedit(
                validated_path,
                old_string,
                new_string,
                replace_all=replace_all,
            )
            if res.error:
                return res.error

            verify_error, updated_content = await self._verify_edited_content_async(
                backend=resolved_backend,
                path=validated_path,
                new_string=new_string,
            )
            if verify_error:
                return verify_error

            if self._should_persist_documents() and not self._is_kb_document(
                validated_path
            ):
                if updated_content is None:
                    return (
                        f"Error: could not reload edited file '{validated_path}' for "
                        "persistence."
                    )
                persist_error = await self._persist_edited_document(
                    file_path=validated_path,
                    updated_content=updated_content,
                )
                if persist_error:
                    return persist_error

            if res.files_update is not None:
                return Command(
                    update={
                        "files": res.files_update,
                        "messages": [
                            ToolMessage(
                                content=f"Successfully replaced {res.occurrences} instance(s) of the string in '{res.path}'",
                                tool_call_id=runtime.tool_call_id,
                            )
                        ],
                    }
                )
            return f"Successfully replaced {res.occurrences} instance(s) of the string in '{res.path}'"

        return StructuredTool.from_function(
            name="edit_file",
            description=tool_description,
            func=sync_edit_file,
            coroutine=async_edit_file,
        )
