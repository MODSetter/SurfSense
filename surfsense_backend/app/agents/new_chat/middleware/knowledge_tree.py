"""Workspace-tree middleware for the SurfSense agent.

Renders the full ``Folder``+``Document`` tree under ``/documents/`` once per
turn (cloud only), caches it by ``(search_space_id, tree_version)``, and
injects the result as a ``<workspace_tree>`` system message immediately
before the latest human turn.

The render is bounded by two truncation layers:

1. **Entry cap** — at most ``MAX_TREE_ENTRIES`` lines. The remainder is
   replaced with a "use ls" hint.
2. **Token cap** — at most ``MAX_TREE_TOKENS`` tokens (using the LLM's
   token-count profile when available). If the entry-truncated tree still
   exceeds the token cap we fall back to a root-only summary.

Anonymous mode renders only ``state['kb_anon_doc']`` (no DB calls).

This middleware also performs a one-time initialization of ``state['cwd']``
to ``"/documents"`` so subsequent middlewares and tools always see a valid
cwd in cloud mode.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langgraph.runtime import Runtime
from sqlalchemy import select

from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.filesystem_state import SurfSenseFilesystemState
from app.agents.new_chat.path_resolver import (
    DOCUMENTS_ROOT,
    PathIndex,
    build_path_index,
    doc_to_virtual_path,
)
from app.db import Document, shielded_async_session

try:
    from litellm import token_counter
except Exception:  # pragma: no cover - optional dep
    token_counter = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


MAX_TREE_ENTRIES = 500
MAX_TREE_TOKENS = 4000


def _approx_tokens(text: str) -> int:
    """Cheap fallback token estimate (1 token ~= 4 chars)."""
    return max(1, (len(text) + 3) // 4)


def _count_tokens(text: str, *, llm: BaseChatModel | None) -> int:
    if llm is None:
        return _approx_tokens(text)
    count_fn = getattr(llm, "_count_tokens", None)
    if callable(count_fn):
        try:
            return int(count_fn([{"role": "user", "content": text}]))
        except Exception:
            pass
    profile = getattr(llm, "profile", None)
    model_names: list[str] = []
    if isinstance(profile, dict):
        tcms = profile.get("token_count_models")
        if isinstance(tcms, list):
            model_names.extend(name for name in tcms if isinstance(name, str) and name)
        tcm = profile.get("token_count_model")
        if isinstance(tcm, str) and tcm and tcm not in model_names:
            model_names.append(tcm)
    model_name = model_names[0] if model_names else getattr(llm, "model", None)
    if not isinstance(model_name, str) or not model_name or token_counter is None:
        return _approx_tokens(text)
    try:
        return int(
            token_counter(
                messages=[{"role": "user", "content": text}],
                model=model_name,
            )
        )
    except Exception:
        return _approx_tokens(text)


class KnowledgeTreeMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Inject the workspace folder/document tree into the agent's context."""

    tools = ()
    state_schema = SurfSenseFilesystemState

    def __init__(
        self,
        *,
        search_space_id: int,
        filesystem_mode: FilesystemMode,
        llm: BaseChatModel | None = None,
        max_entries: int = MAX_TREE_ENTRIES,
        max_tokens: int = MAX_TREE_TOKENS,
    ) -> None:
        self.search_space_id = search_space_id
        self.filesystem_mode = filesystem_mode
        self.llm = llm
        self.max_entries = max_entries
        self.max_tokens = max_tokens
        self._cache: dict[tuple[int, int, bool], str] = {}

    async def abefore_agent(  # type: ignore[override]
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        del runtime
        if self.filesystem_mode != FilesystemMode.CLOUD:
            return None

        update: dict[str, Any] = {}
        if not state.get("cwd"):
            update["cwd"] = DOCUMENTS_ROOT

        anon_doc = state.get("kb_anon_doc")
        if anon_doc:
            tree_msg = self._render_anon_tree(anon_doc)
        else:
            tree_msg = await self._render_kb_tree(state)

        messages = list(state.get("messages") or [])
        insert_at = max(len(messages) - 1, 0)
        messages.insert(insert_at, SystemMessage(content=tree_msg))
        update["messages"] = messages
        return update

    def before_agent(  # type: ignore[override]
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                return None
        except RuntimeError:
            pass
        return asyncio.run(self.abefore_agent(state, runtime))

    # ------------------------------------------------------------------ render

    def _render_anon_tree(self, anon_doc: dict[str, Any]) -> str:
        path = str(anon_doc.get("path") or "")
        title = str(anon_doc.get("title") or "uploaded_document")
        return (
            "<workspace_tree>\n"
            "Anonymous session — only one read-only document is available.\n"
            f"{DOCUMENTS_ROOT}/\n"
            f"  {path} — {title}\n"
            "</workspace_tree>"
        )

    async def _render_kb_tree(self, state: AgentState) -> str:
        version = int(state.get("tree_version") or 0)
        cache_key = (self.search_space_id, version, False)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            async with shielded_async_session() as session:
                index = await build_path_index(session, self.search_space_id)
                doc_rows = await session.execute(
                    select(Document.id, Document.title, Document.folder_id).where(
                        Document.search_space_id == self.search_space_id
                    )
                )
                docs = list(doc_rows.all())
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("knowledge_tree: DB error %s", exc)
            return "<workspace_tree>\n(unavailable)\n</workspace_tree>"

        rendered = self._format_tree(index, docs)
        self._cache[cache_key] = rendered
        return rendered

    def _format_tree(self, index: PathIndex, docs: list[Any]) -> str:
        folder_paths = sorted(set(index.folder_paths.values()))
        doc_paths = sorted(
            doc_to_virtual_path(
                doc_id=row.id,
                title=str(row.title or "untitled"),
                folder_id=row.folder_id,
                index=index,
            )
            for row in docs
        )
        all_paths = sorted(set(folder_paths + doc_paths + [DOCUMENTS_ROOT]))

        lines: list[str] = []
        for path in all_paths:
            depth = (
                0
                if path == DOCUMENTS_ROOT
                else len([p for p in path[len(DOCUMENTS_ROOT) :].split("/") if p])
            )
            indent = "  " * depth
            is_dir = path == DOCUMENTS_ROOT or path in folder_paths
            display = (
                path.rsplit("/", 1)[-1] if path != DOCUMENTS_ROOT else "/documents"
            )
            if is_dir:
                lines.append(f"{indent}{display}/")
            else:
                lines.append(f"{indent}{display}")
            if len(lines) >= self.max_entries:
                remaining = len(all_paths) - len(lines)
                if remaining > 0:
                    lines.append(
                        f"... {remaining} more entries — use "
                        "ls('/documents/<folder>', offset, limit) to expand"
                    )
                break

        body = "\n".join(lines)
        rendered = f"<workspace_tree>\n{body}\n</workspace_tree>"

        token_count = _count_tokens(rendered, llm=self.llm)
        if token_count <= self.max_tokens:
            return rendered

        return self._format_root_summary(folder_paths, doc_paths)

    def _format_root_summary(
        self, folder_paths: list[str], doc_paths: list[str]
    ) -> str:
        top_level: dict[str, int] = {}
        loose_docs = 0
        for path in doc_paths:
            rel = path[len(DOCUMENTS_ROOT) :].lstrip("/")
            if "/" in rel:
                top = rel.split("/", 1)[0]
                top_level[top] = top_level.get(top, 0) + 1
            else:
                loose_docs += 1
        for path in folder_paths:
            rel = path[len(DOCUMENTS_ROOT) :].lstrip("/")
            if not rel:
                continue
            top = rel.split("/", 1)[0]
            top_level.setdefault(top, 0)

        lines = [DOCUMENTS_ROOT + "/"]
        for name in sorted(top_level):
            count = top_level[name]
            lines.append(f"  {name}/ ({count} document{'s' if count != 1 else ''})")
        if loose_docs:
            lines.append(
                f"  ({loose_docs} loose document{'s' if loose_docs != 1 else ''})"
            )
        lines.append(
            "Tree is large; use list_tree('/documents/<folder>') to drill in "
            "or ls('/documents/<folder>', offset, limit) for paginated listings."
        )
        return "<workspace_tree>\n" + "\n".join(lines) + "\n</workspace_tree>"


__all__ = ["KnowledgeTreeMiddleware"]
