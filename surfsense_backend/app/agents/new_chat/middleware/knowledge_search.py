"""Knowledge-base pre-search middleware for the SurfSense new chat agent.

This middleware runs before the main agent loop and seeds a virtual filesystem
(`files` state) with relevant documents retrieved via hybrid search.  On each
turn the filesystem is *expanded* — new results merge with documents loaded
during prior turns — and a synthetic ``ls`` result is injected into the message
history so the LLM is immediately aware of the current filesystem structure.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime
from litellm import token_counter
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.utils import parse_date_or_datetime, resolve_date_range
from app.db import NATIVE_TO_LEGACY_DOCTYPE, Document, Folder, shielded_async_session
from app.retriever.chunks_hybrid_search import ChucksHybridSearchRetriever
from app.utils.document_converters import embed_texts
from app.utils.perf import get_perf_logger

logger = logging.getLogger(__name__)
_perf_log = get_perf_logger()


class KBSearchPlan(BaseModel):
    """Structured internal plan for KB retrieval."""

    optimized_query: str = Field(
        min_length=1,
        description="Optimized retrieval query preserving the user's intent.",
    )
    start_date: str | None = Field(
        default=None,
        description="Optional ISO start date or datetime for KB search filtering.",
    )
    end_date: str | None = Field(
        default=None,
        description="Optional ISO end date or datetime for KB search filtering.",
    )


def _extract_text_from_message(message: BaseMessage) -> str:
    """Extract plain text from a message content."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(p for p in parts if p)
    return str(content)


def _safe_filename(value: str, *, fallback: str = "untitled.xml") -> str:
    """Convert arbitrary text into a filesystem-safe filename."""
    name = re.sub(r"[\\/:*?\"<>|]+", "_", value).strip()
    name = re.sub(r"\s+", " ", name)
    if not name:
        name = fallback
    if len(name) > 180:
        name = name[:180].rstrip()
    if not name.lower().endswith(".xml"):
        name = f"{name}.xml"
    return name


def _render_recent_conversation(
    messages: Sequence[BaseMessage],
    *,
    llm: BaseChatModel | None = None,
    user_text: str = "",
    max_messages: int = 6,
) -> str:
    """Render recent dialogue for internal planning under a token budget.

    Prefers the latest messages and uses the project's existing model-aware
    token budgeting hooks when available on the LLM (`_count_tokens`,
    `_get_max_input_tokens`). Falls back to the prior fixed-message heuristic
    if token counting is unavailable.
    """
    rendered: list[tuple[str, str]] = []
    for message in messages:
        role: str | None = None
        if isinstance(message, HumanMessage):
            role = "user"
        elif isinstance(message, AIMessage):
            if getattr(message, "tool_calls", None):
                continue
            role = "assistant"
        else:
            continue

        text = _extract_text_from_message(message).strip()
        if not text:
            continue
        text = re.sub(r"\s+", " ", text)
        rendered.append((role, text))

    if not rendered:
        return ""

    # Exclude the latest user message from "recent conversation" because it is
    # already passed separately as "Latest user message" in the planner prompt.
    if rendered and rendered[-1][0] == "user" and rendered[-1][1] == user_text.strip():
        rendered = rendered[:-1]

    if not rendered:
        return ""

    def _legacy_render() -> str:
        legacy_lines: list[str] = []
        for role, text in rendered[-max_messages:]:
            clipped = text[:400].rstrip() + "..." if len(text) > 400 else text
            legacy_lines.append(f"{role}: {clipped}")
        return "\n".join(legacy_lines)

    def _count_prompt_tokens(conversation_text: str) -> int | None:
        prompt = _build_kb_planner_prompt(
            recent_conversation=conversation_text or "(none)",
            user_text=user_text,
        )
        message_payload = [{"role": "user", "content": prompt}]

        count_fn = getattr(llm, "_count_tokens", None) if llm is not None else None
        if callable(count_fn):
            try:
                return count_fn(message_payload)
            except Exception:
                pass

        profile = getattr(llm, "profile", None) if llm is not None else None
        model_names: list[str] = []
        if isinstance(profile, dict):
            tcms = profile.get("token_count_models")
            if isinstance(tcms, list):
                model_names.extend(
                    name for name in tcms if isinstance(name, str) and name
                )
            tcm = profile.get("token_count_model")
            if isinstance(tcm, str) and tcm and tcm not in model_names:
                model_names.append(tcm)
        model_name = model_names[0] if model_names else getattr(llm, "model", None)
        if not isinstance(model_name, str) or not model_name:
            return None
        try:
            return token_counter(messages=message_payload, model=model_name)
        except Exception:
            return None

    get_max_input_tokens = getattr(llm, "_get_max_input_tokens", None) if llm else None
    if callable(get_max_input_tokens):
        try:
            max_input_tokens = int(get_max_input_tokens())
        except Exception:
            max_input_tokens = None
    else:
        profile = getattr(llm, "profile", None) if llm is not None else None
        max_input_tokens = (
            profile.get("max_input_tokens")
            if isinstance(profile, dict)
            and isinstance(profile.get("max_input_tokens"), int)
            else None
        )

    if not isinstance(max_input_tokens, int) or max_input_tokens <= 0:
        return _legacy_render()

    output_reserve = min(max(int(max_input_tokens * 0.02), 256), 1024)
    budget = max_input_tokens - output_reserve
    if budget <= 0:
        return _legacy_render()

    selected_lines: list[str] = []
    for role, text in reversed(rendered):
        candidate_line = f"{role}: {text}"
        candidate_lines = [candidate_line, *selected_lines]
        candidate_conversation = "\n".join(candidate_lines)
        token_count = _count_prompt_tokens(candidate_conversation)
        if token_count is None:
            return _legacy_render()
        if token_count <= budget:
            selected_lines = candidate_lines
            continue

        # If the full message does not fit, keep as much of this most-recent
        # older message as possible via binary search.
        lo, hi = 1, len(text)
        best_line: str | None = None
        while lo <= hi:
            mid = (lo + hi) // 2
            clipped_text = text[:mid].rstrip() + "..."
            clipped_line = f"{role}: {clipped_text}"
            clipped_conversation = "\n".join([clipped_line, *selected_lines])
            clipped_tokens = _count_prompt_tokens(clipped_conversation)
            if clipped_tokens is None:
                break
            if clipped_tokens <= budget:
                best_line = clipped_line
                lo = mid + 1
            else:
                hi = mid - 1

        if best_line is not None:
            selected_lines = [best_line, *selected_lines]
        break

    if not selected_lines:
        return _legacy_render()

    return "\n".join(selected_lines)


def _build_kb_planner_prompt(
    *,
    recent_conversation: str,
    user_text: str,
) -> str:
    """Build a compact internal prompt for KB query rewriting and date scoping."""
    today = datetime.now(UTC).date().isoformat()
    return (
        "You optimize internal knowledge-base search inputs for document retrieval.\n"
        "Return JSON only with this exact shape:\n"
        '{"optimized_query":"string","start_date":"ISO string or null","end_date":"ISO string or null"}\n\n'
        "Rules:\n"
        "- Preserve the user's intent.\n"
        "- Rewrite the query to improve retrieval using concrete entities, acronyms, projects, tools, people, and document-specific terms when helpful.\n"
        "- Keep the query concise and retrieval-focused.\n"
        "- Only use date filters when the latest user request or recent dialogue clearly implies a time range.\n"
        "- If you use date filters, prefer returning both bounds.\n"
        "- If no date filter is useful, return null for both dates.\n"
        "- Do not include markdown, prose, or explanations.\n\n"
        f"Today's UTC date: {today}\n\n"
        f"Recent conversation:\n{recent_conversation or '(none)'}\n\n"
        f"Latest user message:\n{user_text}"
    )


def _extract_json_payload(text: str) -> str:
    """Extract a JSON object from a raw LLM response."""
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fenced:
        return fenced.group(1)

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


def _parse_kb_search_plan_response(response_text: str) -> KBSearchPlan:
    """Parse and validate the planner's JSON response."""
    payload = json.loads(_extract_json_payload(response_text))
    return KBSearchPlan.model_validate(payload)


def _normalize_optional_date_range(
    start_date: str | None,
    end_date: str | None,
) -> tuple[datetime | None, datetime | None]:
    """Normalize optional planner dates into a UTC datetime range."""
    parsed_start = parse_date_or_datetime(start_date) if start_date else None
    parsed_end = parse_date_or_datetime(end_date) if end_date else None

    if parsed_start is None and parsed_end is None:
        return None, None

    resolved_start, resolved_end = resolve_date_range(parsed_start, parsed_end)
    return resolved_start, resolved_end


def _build_document_xml(
    document: dict[str, Any],
    matched_chunk_ids: set[int] | None = None,
) -> str:
    """Build citation-friendly XML with a ``<chunk_index>`` for smart seeking.

    The ``<chunk_index>`` at the top of each document lists every chunk with its
    line range inside ``<document_content>`` and flags chunks that directly
    matched the search query (``matched="true"``).  This lets the LLM jump
    straight to the most relevant section via ``read_file(offset=…, limit=…)``
    instead of reading sequentially from the start.
    """
    matched = matched_chunk_ids or set()

    doc_meta = document.get("document") or {}
    metadata = (doc_meta.get("metadata") or {}) if isinstance(doc_meta, dict) else {}
    document_id = doc_meta.get("id", document.get("document_id", "unknown"))
    document_type = doc_meta.get("document_type", document.get("source", "UNKNOWN"))
    title = doc_meta.get("title") or metadata.get("title") or "Untitled Document"
    url = (
        metadata.get("url") or metadata.get("source") or metadata.get("page_url") or ""
    )
    metadata_json = json.dumps(metadata, ensure_ascii=False)

    # --- 1. Metadata header (fixed structure) ---
    metadata_lines: list[str] = [
        "<document>",
        "<document_metadata>",
        f"  <document_id>{document_id}</document_id>",
        f"  <document_type>{document_type}</document_type>",
        f"  <title><![CDATA[{title}]]></title>",
        f"  <url><![CDATA[{url}]]></url>",
        f"  <metadata_json><![CDATA[{metadata_json}]]></metadata_json>",
        "</document_metadata>",
        "",
    ]

    # --- 2. Pre-build chunk XML strings to compute line counts ---
    chunks = document.get("chunks") or []
    chunk_entries: list[tuple[int | None, str]] = []  # (chunk_id, xml_string)
    if isinstance(chunks, list):
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            chunk_id = chunk.get("chunk_id") or chunk.get("id")
            chunk_content = str(chunk.get("content", "")).strip()
            if not chunk_content:
                continue
            if chunk_id is None:
                xml = f"  <chunk><![CDATA[{chunk_content}]]></chunk>"
            else:
                xml = f"  <chunk id='{chunk_id}'><![CDATA[{chunk_content}]]></chunk>"
            chunk_entries.append((chunk_id, xml))

    # --- 3. Compute line numbers for every chunk ---
    # Layout (1-indexed lines for read_file):
    #   metadata_lines          -> len(metadata_lines) lines
    #   <chunk_index>           -> 1 line
    #   index entries           -> len(chunk_entries) lines
    #   </chunk_index>          -> 1 line
    #   (empty line)            -> 1 line
    #   <document_content>      -> 1 line
    #   chunk xml lines…
    #   </document_content>     -> 1 line
    #   </document>             -> 1 line
    index_overhead = (
        1 + len(chunk_entries) + 1 + 1 + 1
    )  # tags + empty + <document_content>
    first_chunk_line = len(metadata_lines) + index_overhead + 1  # 1-indexed

    current_line = first_chunk_line
    index_entry_lines: list[str] = []
    for cid, xml_str in chunk_entries:
        num_lines = xml_str.count("\n") + 1
        end_line = current_line + num_lines - 1
        matched_attr = ' matched="true"' if cid is not None and cid in matched else ""
        if cid is not None:
            index_entry_lines.append(
                f'  <entry chunk_id="{cid}" lines="{current_line}-{end_line}"{matched_attr}/>'
            )
        else:
            index_entry_lines.append(
                f'  <entry lines="{current_line}-{end_line}"{matched_attr}/>'
            )
        current_line = end_line + 1

    # --- 4. Assemble final XML ---
    lines = metadata_lines.copy()
    lines.append("<chunk_index>")
    lines.extend(index_entry_lines)
    lines.append("</chunk_index>")
    lines.append("")
    lines.append("<document_content>")
    for _, xml_str in chunk_entries:
        lines.append(xml_str)
    lines.extend(["</document_content>", "</document>"])
    return "\n".join(lines)


async def _get_folder_paths(
    session: AsyncSession, search_space_id: int
) -> dict[int, str]:
    """Return a map of folder_id -> virtual folder path under /documents."""
    result = await session.execute(
        select(Folder.id, Folder.name, Folder.parent_id).where(
            Folder.search_space_id == search_space_id
        )
    )
    rows = result.all()
    by_id = {row.id: {"name": row.name, "parent_id": row.parent_id} for row in rows}

    cache: dict[int, str] = {}

    def resolve_path(folder_id: int) -> str:
        if folder_id in cache:
            return cache[folder_id]
        parts: list[str] = []
        cursor: int | None = folder_id
        visited: set[int] = set()
        while cursor is not None and cursor in by_id and cursor not in visited:
            visited.add(cursor)
            entry = by_id[cursor]
            parts.append(
                _safe_filename(str(entry["name"]), fallback="folder").removesuffix(
                    ".xml"
                )
            )
            cursor = entry["parent_id"]
        parts.reverse()
        path = "/documents/" + "/".join(parts) if parts else "/documents"
        cache[folder_id] = path
        return path

    for folder_id in by_id:
        resolve_path(folder_id)
    return cache


def _build_synthetic_ls(
    existing_files: dict[str, Any] | None,
    new_files: dict[str, Any],
) -> tuple[AIMessage, ToolMessage]:
    """Build a synthetic ls("/documents") tool-call + result for the LLM context.

    Paths are listed with *new* (rank-ordered) files first, then existing files
    that were already in state from prior turns.
    """
    merged: dict[str, Any] = {**(existing_files or {}), **new_files}
    doc_paths = [
        p for p, v in merged.items() if p.startswith("/documents/") and v is not None
    ]

    new_set = set(new_files)
    new_paths = [p for p in doc_paths if p in new_set]
    old_paths = [p for p in doc_paths if p not in new_set]
    ordered = new_paths + old_paths

    tool_call_id = f"auto_ls_{uuid.uuid4().hex[:12]}"
    ai_msg = AIMessage(
        content="",
        tool_calls=[{"name": "ls", "args": {"path": "/documents"}, "id": tool_call_id}],
    )
    tool_msg = ToolMessage(
        content=str(ordered) if ordered else "No documents found.",
        tool_call_id=tool_call_id,
    )
    return ai_msg, tool_msg


def _resolve_search_types(
    available_connectors: list[str] | None,
    available_document_types: list[str] | None,
) -> list[str] | None:
    """Build a flat list of document-type strings for the chunk retriever.

    Includes legacy equivalents from ``NATIVE_TO_LEGACY_DOCTYPE`` so that
    old documents indexed under Composio names are still found.

    Returns ``None`` when no filtering is desired (search all types).
    """
    types: set[str] = set()
    if available_document_types:
        types.update(available_document_types)
    if available_connectors:
        types.update(available_connectors)
    if not types:
        return None

    expanded: set[str] = set(types)
    for t in types:
        legacy = NATIVE_TO_LEGACY_DOCTYPE.get(t)
        if legacy:
            expanded.add(legacy)
    return list(expanded) if expanded else None


async def search_knowledge_base(
    *,
    query: str,
    search_space_id: int,
    available_connectors: list[str] | None = None,
    available_document_types: list[str] | None = None,
    top_k: int = 10,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[dict[str, Any]]:
    """Run a single unified hybrid search against the knowledge base.

    Uses one ``ChucksHybridSearchRetriever`` call across all document types
    instead of fanning out per-connector.  This reduces the number of DB
    queries from ~10 to 2 (one RRF query + one chunk fetch).
    """
    if not query:
        return []

    [embedding] = embed_texts([query])

    doc_types = _resolve_search_types(available_connectors, available_document_types)
    retriever_top_k = min(top_k * 3, 30)

    async with shielded_async_session() as session:
        retriever = ChucksHybridSearchRetriever(session)
        results = await retriever.hybrid_search(
            query_text=query,
            top_k=retriever_top_k,
            search_space_id=search_space_id,
            document_type=doc_types,
            start_date=start_date,
            end_date=end_date,
            query_embedding=embedding.tolist(),
        )

    return results[:top_k]


async def build_scoped_filesystem(
    *,
    documents: Sequence[dict[str, Any]],
    search_space_id: int,
) -> dict[str, dict[str, str]]:
    """Build a StateBackend-compatible files dict from search results."""
    async with shielded_async_session() as session:
        folder_paths = await _get_folder_paths(session, search_space_id)
        doc_ids = [
            (doc.get("document") or {}).get("id")
            for doc in documents
            if isinstance(doc, dict)
        ]
        doc_ids = [doc_id for doc_id in doc_ids if isinstance(doc_id, int)]
        folder_by_doc_id: dict[int, int | None] = {}
        if doc_ids:
            doc_rows = await session.execute(
                select(Document.id, Document.folder_id).where(
                    Document.search_space_id == search_space_id,
                    Document.id.in_(doc_ids),
                )
            )
            folder_by_doc_id = {
                row.id: row.folder_id for row in doc_rows.all() if row.id is not None
            }

    files: dict[str, dict[str, str]] = {}
    for document in documents:
        doc_meta = document.get("document") or {}
        title = str(doc_meta.get("title") or "untitled")
        doc_id = doc_meta.get("id")
        folder_id = folder_by_doc_id.get(doc_id) if isinstance(doc_id, int) else None
        base_folder = folder_paths.get(folder_id, "/documents")
        file_name = _safe_filename(title)
        path = f"{base_folder}/{file_name}"
        matched_ids = set(document.get("matched_chunk_ids") or [])
        xml_content = _build_document_xml(document, matched_chunk_ids=matched_ids)
        files[path] = {
            "content": xml_content.split("\n"),
            "encoding": "utf-8",
            "created_at": "",
            "modified_at": "",
        }
    return files


class KnowledgeBaseSearchMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Pre-agent middleware that always searches the KB and seeds a scoped filesystem."""

    tools = ()

    def __init__(
        self,
        *,
        llm: BaseChatModel | None = None,
        search_space_id: int,
        available_connectors: list[str] | None = None,
        available_document_types: list[str] | None = None,
        top_k: int = 10,
    ) -> None:
        self.llm = llm
        self.search_space_id = search_space_id
        self.available_connectors = available_connectors
        self.available_document_types = available_document_types
        self.top_k = top_k

    async def _plan_search_inputs(
        self,
        *,
        messages: Sequence[BaseMessage],
        user_text: str,
    ) -> tuple[str, datetime | None, datetime | None]:
        """Rewrite the KB query and infer optional date filters with the LLM."""
        if self.llm is None:
            return user_text, None, None

        recent_conversation = _render_recent_conversation(
            messages,
            llm=self.llm,
            user_text=user_text,
        )
        prompt = _build_kb_planner_prompt(
            recent_conversation=recent_conversation,
            user_text=user_text,
        )
        loop = asyncio.get_running_loop()
        t0 = loop.time()

        try:
            response = await self.llm.ainvoke(
                [HumanMessage(content=prompt)],
                config={"tags": ["surfsense:internal"]},
            )
            plan = _parse_kb_search_plan_response(_extract_text_from_message(response))
            optimized_query = (
                re.sub(r"\s+", " ", plan.optimized_query).strip() or user_text
            )
            start_date, end_date = _normalize_optional_date_range(
                plan.start_date,
                plan.end_date,
            )
            _perf_log.info(
                "[kb_fs_middleware] planner in %.3fs query=%r optimized=%r start=%s end=%s",
                loop.time() - t0,
                user_text[:80],
                optimized_query[:120],
                start_date.isoformat() if start_date else None,
                end_date.isoformat() if end_date else None,
            )
            return optimized_query, start_date, end_date
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            logger.warning(
                "KB planner returned invalid output, using raw query: %s", exc
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("KB planner failed, using raw query: %s", exc)

        return user_text, None, None

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

    async def abefore_agent(  # type: ignore[override]
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        del runtime
        messages = state.get("messages") or []
        if not messages:
            return None
        last_message = messages[-1]
        if not isinstance(last_message, HumanMessage):
            return None

        user_text = _extract_text_from_message(last_message).strip()
        if not user_text:
            return None

        t0 = _perf_log and asyncio.get_event_loop().time()
        existing_files = state.get("files")
        planned_query, start_date, end_date = await self._plan_search_inputs(
            messages=messages,
            user_text=user_text,
        )

        search_results = await search_knowledge_base(
            query=planned_query,
            search_space_id=self.search_space_id,
            available_connectors=self.available_connectors,
            available_document_types=self.available_document_types,
            top_k=self.top_k,
            start_date=start_date,
            end_date=end_date,
        )
        new_files = await build_scoped_filesystem(
            documents=search_results,
            search_space_id=self.search_space_id,
        )

        ai_msg, tool_msg = _build_synthetic_ls(existing_files, new_files)

        if t0 is not None:
            _perf_log.info(
                "[kb_fs_middleware] completed in %.3fs query=%r optimized=%r new_files=%d total=%d",
                asyncio.get_event_loop().time() - t0,
                user_text[:80],
                planned_query[:120],
                len(new_files),
                len(new_files) + len(existing_files or {}),
            )
        return {"files": new_files, "messages": [ai_msg, tool_msg]}
