"""Custom filesystem middleware for the SurfSense agent.

This middleware customizes prompts and persists write/edit operations for
`/documents/*` files into SurfSense's `Document`/`Chunk` tables.
"""

from __future__ import annotations

import asyncio
import logging
import re
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

from app.agents.new_chat.sandbox import (
    _evict_sandbox_cache,
    get_or_create_sandbox,
    is_sandbox_enabled,
    sync_files_to_sandbox,
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

SURFSENSE_WRITE_FILE_TOOL_DESCRIPTION = """Writes a new file to the in-memory filesystem (session-only).

Use this to create scratch/working files during the conversation. Files created
here are ephemeral and will not be saved to the user's knowledge base.

To permanently save a document to the user's knowledge base, use the
`save_document` tool instead.
"""

SURFSENSE_EDIT_FILE_TOOL_DESCRIPTION = """Performs exact string replacements in files.

IMPORTANT:
- Read the file before editing.
- Preserve exact indentation and formatting.
- Edits to documents under `/documents/` are session-only (not persisted to the
  database) because those files use an XML citation wrapper around the original
  content.
"""

SURFSENSE_GLOB_TOOL_DESCRIPTION = """Find files matching a glob pattern.

Supports standard glob patterns: `*`, `**`, `?`.
Returns absolute file paths.
"""

SURFSENSE_GREP_TOOL_DESCRIPTION = """Search for a literal text pattern across files.

Use this to locate relevant document files/chunks before reading full files.
"""

SURFSENSE_EXECUTE_CODE_TOOL_DESCRIPTION = """Executes a shell command in an isolated sandbox environment.

The sandbox runs Python with common data-science packages pre-installed
(pandas, numpy, matplotlib, scipy, scikit-learn).

Knowledge base documents from your conversation are automatically available
as XML files under /home/daytona/documents/.

Usage notes:
- Commands run in an isolated sandbox with no outbound network access.
- Returns combined stdout/stderr output with exit code.
- Use the optional timeout parameter to override the default timeout.
- When issuing multiple commands, use ';' or '&&' to chain them.
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
        search_space_id: int | None = None,
        created_by_id: str | None = None,
        thread_id: int | str | None = None,
        tool_token_limit_before_evict: int | None = 20000,
    ) -> None:
        self._search_space_id = search_space_id
        self._created_by_id = created_by_id
        self._thread_id = thread_id
        self._sandbox_available = is_sandbox_enabled() and thread_id is not None

        system_prompt = SURFSENSE_FILESYSTEM_SYSTEM_PROMPT
        if self._sandbox_available:
            system_prompt += (
                "\n- execute_code: run shell commands in an isolated Python sandbox."
            )

        super().__init__(
            system_prompt=system_prompt,
            custom_tool_descriptions={
                "ls": SURFSENSE_LIST_FILES_TOOL_DESCRIPTION,
                "read_file": SURFSENSE_READ_FILE_TOOL_DESCRIPTION,
                "write_file": SURFSENSE_WRITE_FILE_TOOL_DESCRIPTION,
                "edit_file": SURFSENSE_EDIT_FILE_TOOL_DESCRIPTION,
                "glob": SURFSENSE_GLOB_TOOL_DESCRIPTION,
                "grep": SURFSENSE_GREP_TOOL_DESCRIPTION,
            },
            tool_token_limit_before_evict=tool_token_limit_before_evict,
            max_execute_timeout=self._MAX_EXECUTE_TIMEOUT,
        )
        self.tools = [t for t in self.tools if t.name != "execute"]
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
                str, "Shell command to execute in the sandbox environment."
            ],
            runtime: ToolRuntime[None, FilesystemState],
            timeout: Annotated[
                int | None,
                "Optional timeout in seconds for this command.",
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
                str, "Shell command to execute in the sandbox environment."
            ],
            runtime: ToolRuntime[None, FilesystemState],
            timeout: Annotated[
                int | None,
                "Optional timeout in seconds for this command.",
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

    async def _execute_in_sandbox(
        self,
        command: str,
        runtime: ToolRuntime[None, FilesystemState],
        timeout: int | None,
    ) -> str:
        """Core logic: get sandbox, sync files, run command, handle retries."""
        assert self._thread_id is not None

        try:
            return await self._try_sandbox_execute(command, runtime, timeout)
        except (DaytonaError, Exception) as first_err:
            logger.warning(
                "Sandbox execute failed for thread %s, retrying: %s",
                self._thread_id,
                first_err,
            )
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
        sandbox, is_new = await get_or_create_sandbox(self._thread_id)
        files = runtime.state.get("files") or {}
        await sync_files_to_sandbox(self._thread_id, files, sandbox, is_new)
        result = await sandbox.aexecute(command, timeout=timeout)
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
            try:
                validated_path = validate_path(file_path)
            except ValueError as exc:
                return f"Error: {exc}"
            res: WriteResult = resolved_backend.write(validated_path, content)
            if res.error:
                return res.error

            if not self._is_kb_document(validated_path):
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
            try:
                validated_path = validate_path(file_path)
            except ValueError as exc:
                return f"Error: {exc}"
            res: WriteResult = await resolved_backend.awrite(validated_path, content)
            if res.error:
                return res.error

            if not self._is_kb_document(validated_path):
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
            try:
                validated_path = validate_path(file_path)
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

            if not self._is_kb_document(validated_path):
                read_result = resolved_backend.read(
                    validated_path, offset=0, limit=200000
                )
                if read_result.error or read_result.file_data is None:
                    return f"Error: could not reload edited file '{validated_path}' for persistence."
                updated_content = read_result.file_data["content"]
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
            try:
                validated_path = validate_path(file_path)
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

            if not self._is_kb_document(validated_path):
                read_result = await resolved_backend.aread(
                    validated_path, offset=0, limit=200000
                )
                if read_result.error or read_result.file_data is None:
                    return f"Error: could not reload edited file '{validated_path}' for persistence."
                updated_content = read_result.file_data["content"]
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
