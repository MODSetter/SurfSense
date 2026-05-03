"""Hybrid-search priority middleware for the SurfSense new chat agent.

This middleware runs ``before_agent`` on every turn and writes:

* ``state["kb_priority"]`` — the top-K most relevant documents for the
  current user message, used to render a ``<priority_documents>`` system
  message immediately before the user turn.
* ``state["kb_matched_chunk_ids"]`` — internal hand-off mapping
  (``Document.id`` → matched chunk IDs) consumed by
  :class:`KBPostgresBackend._load_file_data` when the agent first reads each
  document, so the XML wrapper can flag matched sections in
  ``<chunk_index>``.

The previous "scoped filesystem" behaviour (synthetic ``ls`` + state
``files`` seeding) is intentionally removed: documents are now lazy-loaded
from Postgres on demand, with the full workspace tree rendered separately
by :class:`KnowledgeTreeMiddleware`.

In anonymous mode the middleware skips hybrid search entirely and emits a
single-entry priority list pointing at the Redis-loaded document
(``state["kb_anon_doc"]``).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langgraph.runtime import Runtime
from litellm import token_counter
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select

from app.agents.new_chat.feature_flags import get_flags
from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.filesystem_state import SurfSenseFilesystemState
from app.agents.new_chat.path_resolver import (
    PathIndex,
    build_path_index,
    doc_to_virtual_path,
)
from app.agents.new_chat.utils import parse_date_or_datetime, resolve_date_range
from app.db import (
    NATIVE_TO_LEGACY_DOCTYPE,
    Chunk,
    Document,
    shielded_async_session,
)
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
    is_recency_query: bool = Field(
        default=False,
        description=(
            "True when the user's intent is primarily about recency or temporal "
            "ordering (e.g. 'latest', 'newest', 'most recent', 'last uploaded') "
            "rather than topical relevance."
        ),
    )


def _extract_text_from_message(message: BaseMessage) -> str:
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


def _render_recent_conversation(
    messages: Sequence[BaseMessage],
    *,
    llm: BaseChatModel | None = None,
    user_text: str = "",
    max_messages: int = 6,
) -> str:
    """Render recent dialogue for internal planning under a token budget.

    Filters to ``HumanMessage`` and ``AIMessage`` (without tool_calls) so that
    injected ``SystemMessage`` artefacts (priority list, workspace tree,
    file-write contract) don't pollute the planner prompt.
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
    today = datetime.now(UTC).date().isoformat()
    return (
        "You optimize internal knowledge-base search inputs for document retrieval.\n"
        "Return JSON only with this exact shape:\n"
        '{"optimized_query":"string","start_date":"ISO string or null","end_date":"ISO string or null","is_recency_query":bool}\n\n'
        "Rules:\n"
        "- Preserve the user's intent.\n"
        "- Rewrite the query to improve retrieval using concrete entities, acronyms, projects, tools, people, and document-specific terms when helpful.\n"
        "- Keep the query concise and retrieval-focused.\n"
        "- Only use date filters when the latest user request or recent dialogue clearly implies a time range.\n"
        "- If you use date filters, prefer returning both bounds.\n"
        "- If no date filter is useful, return null for both dates.\n"
        '- Set "is_recency_query" to true ONLY when the user\'s primary intent is about '
        "recency or temporal ordering rather than topical relevance. Examples: "
        '"latest file", "newest upload", "most recent document", "what did I save last", '
        '"show me files from today", "last thing I added". '
        "When true, results will be sorted by date instead of relevance.\n"
        "- Do not include markdown, prose, or explanations.\n\n"
        f"Today's UTC date: {today}\n\n"
        f"Recent conversation:\n{recent_conversation or '(none)'}\n\n"
        f"Latest user message:\n{user_text}"
    )


def _extract_json_payload(text: str) -> str:
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
    payload = json.loads(_extract_json_payload(response_text))
    return KBSearchPlan.model_validate(payload)


def _normalize_optional_date_range(
    start_date: str | None,
    end_date: str | None,
) -> tuple[datetime | None, datetime | None]:
    parsed_start = parse_date_or_datetime(start_date) if start_date else None
    parsed_end = parse_date_or_datetime(end_date) if end_date else None

    if parsed_start is None and parsed_end is None:
        return None, None

    return resolve_date_range(parsed_start, parsed_end)


def _resolve_search_types(
    available_connectors: list[str] | None,
    available_document_types: list[str] | None,
) -> list[str] | None:
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


_RECENCY_MAX_CHUNKS_PER_DOC = 5


async def browse_recent_documents(
    *,
    search_space_id: int,
    document_type: list[str] | None = None,
    top_k: int = 10,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return documents ordered by recency (newest first), no relevance ranking."""
    from sqlalchemy import func

    from app.db import DocumentType

    async with shielded_async_session() as session:
        base_conditions = [
            Document.search_space_id == search_space_id,
            func.coalesce(Document.status["state"].astext, "ready") != "deleting",
        ]

        if document_type is not None:
            import contextlib

            doc_type_enums = []
            for dt in document_type:
                if isinstance(dt, str):
                    with contextlib.suppress(KeyError):
                        doc_type_enums.append(DocumentType[dt])
                else:
                    doc_type_enums.append(dt)
            if doc_type_enums:
                if len(doc_type_enums) == 1:
                    base_conditions.append(Document.document_type == doc_type_enums[0])
                else:
                    base_conditions.append(Document.document_type.in_(doc_type_enums))

        if start_date is not None:
            base_conditions.append(Document.updated_at >= start_date)
        if end_date is not None:
            base_conditions.append(Document.updated_at <= end_date)

        doc_query = (
            select(Document)
            .where(*base_conditions)
            .order_by(Document.updated_at.desc())
            .limit(top_k)
        )
        result = await session.execute(doc_query)
        documents = result.scalars().unique().all()

        if not documents:
            return []

        doc_ids = [d.id for d in documents]
        numbered = (
            select(
                Chunk.id.label("chunk_id"),
                Chunk.document_id,
                Chunk.content,
                func.row_number()
                .over(partition_by=Chunk.document_id, order_by=Chunk.id)
                .label("rn"),
            )
            .where(Chunk.document_id.in_(doc_ids))
            .subquery("numbered")
        )

        chunk_query = (
            select(numbered.c.chunk_id, numbered.c.document_id, numbered.c.content)
            .where(numbered.c.rn <= _RECENCY_MAX_CHUNKS_PER_DOC)
            .order_by(numbered.c.document_id, numbered.c.chunk_id)
        )
        chunk_result = await session.execute(chunk_query)
        fetched_chunks = chunk_result.all()

    doc_chunks: dict[int, list[dict[str, Any]]] = {d.id: [] for d in documents}
    for row in fetched_chunks:
        if row.document_id in doc_chunks:
            doc_chunks[row.document_id].append(
                {"chunk_id": row.chunk_id, "content": row.content}
            )

    results: list[dict[str, Any]] = []
    for doc in documents:
        chunks_list = doc_chunks.get(doc.id, [])
        metadata = doc.document_metadata or {}
        results.append(
            {
                "document_id": doc.id,
                "content": "\n\n".join(
                    c["content"] for c in chunks_list if c.get("content")
                ),
                "score": 0.0,
                "chunks": chunks_list,
                "matched_chunk_ids": [],
                "document": {
                    "id": doc.id,
                    "title": doc.title,
                    "document_type": (
                        doc.document_type.value
                        if getattr(doc, "document_type", None)
                        else None
                    ),
                    "metadata": metadata,
                    "folder_id": getattr(doc, "folder_id", None),
                },
                "source": (
                    doc.document_type.value
                    if getattr(doc, "document_type", None)
                    else None
                ),
            }
        )
    return results


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
    """Run a single unified hybrid search against the knowledge base."""
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


async def fetch_mentioned_documents(
    *,
    document_ids: list[int],
    search_space_id: int,
) -> list[dict[str, Any]]:
    """Fetch explicitly mentioned documents."""
    if not document_ids:
        return []

    async with shielded_async_session() as session:
        doc_result = await session.execute(
            select(Document).where(
                Document.id.in_(document_ids),
                Document.search_space_id == search_space_id,
            )
        )
        docs = {doc.id: doc for doc in doc_result.scalars().all()}

        if not docs:
            return []

        chunk_result = await session.execute(
            select(Chunk.id, Chunk.content, Chunk.document_id)
            .where(Chunk.document_id.in_(list(docs.keys())))
            .order_by(Chunk.document_id, Chunk.id)
        )
        chunks_by_doc: dict[int, list[dict[str, Any]]] = {doc_id: [] for doc_id in docs}
        for row in chunk_result.all():
            if row.document_id in chunks_by_doc:
                chunks_by_doc[row.document_id].append(
                    {"chunk_id": row.id, "content": row.content}
                )

    results: list[dict[str, Any]] = []
    for doc_id in document_ids:
        doc = docs.get(doc_id)
        if doc is None:
            continue
        metadata = doc.document_metadata or {}
        results.append(
            {
                "document_id": doc.id,
                "content": "",
                "score": 1.0,
                "chunks": chunks_by_doc.get(doc.id, []),
                "matched_chunk_ids": [],
                "document": {
                    "id": doc.id,
                    "title": doc.title,
                    "document_type": (
                        doc.document_type.value
                        if getattr(doc, "document_type", None)
                        else None
                    ),
                    "metadata": metadata,
                    "folder_id": getattr(doc, "folder_id", None),
                },
                "source": (
                    doc.document_type.value
                    if getattr(doc, "document_type", None)
                    else None
                ),
                "_user_mentioned": True,
            }
        )
    return results


def _render_priority_message(priority: list[dict[str, Any]]) -> SystemMessage:
    """Render the priority list as a single ``<priority_documents>`` system message."""
    if not priority:
        body = "(no priority documents for this turn)"
    else:
        lines: list[str] = []
        for entry in priority:
            score = entry.get("score")
            mentioned = entry.get("mentioned")
            score_str = f"{score:.3f}" if isinstance(score, int | float) else "n/a"
            mark = " [USER-MENTIONED]" if mentioned else ""
            lines.append(f"- {entry.get('path', '')} (score={score_str}){mark}")
        body = "\n".join(lines)
    return SystemMessage(
        content=(
            "<priority_documents>\n"
            "These documents are most relevant to the latest user message; "
            "read them first. Matched sections are flagged inside each "
            "document's <chunk_index>.\n"
            f"{body}\n"
            "</priority_documents>"
        )
    )


class KnowledgePriorityMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Compute hybrid-search priority hints for the current turn."""

    tools = ()
    state_schema = SurfSenseFilesystemState

    def __init__(
        self,
        *,
        llm: BaseChatModel | None = None,
        search_space_id: int,
        filesystem_mode: FilesystemMode = FilesystemMode.CLOUD,
        available_connectors: list[str] | None = None,
        available_document_types: list[str] | None = None,
        top_k: int = 10,
        mentioned_document_ids: list[int] | None = None,
    ) -> None:
        self.llm = llm
        self.search_space_id = search_space_id
        self.filesystem_mode = filesystem_mode
        self.available_connectors = available_connectors
        self.available_document_types = available_document_types
        self.top_k = top_k
        self.mentioned_document_ids = mentioned_document_ids or []
        # Build the kb-planner private Runnable ONCE here so we don't pay
        # the ``create_agent`` compile cost (50-200ms) on every turn.
        # Disabled by default behind ``enable_kb_planner_runnable``; when
        # off the planner falls back to the legacy ``self.llm.ainvoke``
        # path.
        self._planner: Runnable | None = None
        self._planner_compile_failed = False

    def _build_kb_planner_runnable(self) -> Runnable | None:
        """Compile the kb-planner private :class:`Runnable` once.

        Returns ``None`` when the feature flag is disabled, when the LLM is
        unavailable, or when ``create_agent`` raises (we fall back to the
        legacy ``self.llm.ainvoke`` path in that case). Compilation happens
        lazily on first call, then memoized via ``self._planner``.

        The compiled agent is constructed without tools — the planner's
        contract is "answer with structured JSON" — but it inherits the
        :class:`RetryAfterMiddleware` so transient rate-limit errors
        from the planner LLM call don't fail the whole turn.
        """
        if self._planner is not None or self._planner_compile_failed:
            return self._planner
        if self.llm is None:
            return None
        flags = get_flags()
        if not flags.enable_kb_planner_runnable or flags.disable_new_agent_stack:
            return None

        from app.agents.new_chat.middleware.retry_after import RetryAfterMiddleware

        try:
            self._planner = create_agent(
                self.llm,
                tools=[],
                middleware=[RetryAfterMiddleware(max_retries=2)],
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "kb-planner Runnable compile failed; falling back to llm.ainvoke: %s",
                exc,
            )
            self._planner_compile_failed = True
            self._planner = None
        return self._planner

    async def _plan_search_inputs(
        self,
        *,
        messages: Sequence[BaseMessage],
        user_text: str,
    ) -> tuple[str, datetime | None, datetime | None, bool]:
        if self.llm is None:
            return user_text, None, None, False

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

        # Prefer the compiled-once planner Runnable when enabled; otherwise
        # fall back to ``self.llm.ainvoke``. The ``surfsense:internal`` tag
        # is preserved on both paths so ``_stream_agent_events`` still
        # suppresses the planner's intermediate events from the UI.
        planner = self._build_kb_planner_runnable()
        try:
            if planner is not None:
                planner_state = await planner.ainvoke(
                    {"messages": [HumanMessage(content=prompt)]},
                    config={"tags": ["surfsense:internal"]},
                )
                response_messages = (
                    planner_state.get("messages", [])
                    if isinstance(planner_state, dict)
                    else []
                )
                response = (
                    response_messages[-1]
                    if response_messages
                    else AIMessage(content="")
                )
            else:
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
            is_recency = plan.is_recency_query
            _perf_log.info(
                "[kb_priority] planner in %.3fs query=%r optimized=%r "
                "start=%s end=%s recency=%s",
                loop.time() - t0,
                user_text[:80],
                optimized_query[:120],
                start_date.isoformat() if start_date else None,
                end_date.isoformat() if end_date else None,
                is_recency,
            )
            return optimized_query, start_date, end_date, is_recency
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            logger.warning(
                "KB planner returned invalid output, using raw query: %s", exc
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("KB planner failed, using raw query: %s", exc)

        return user_text, None, None, False

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
        if self.filesystem_mode != FilesystemMode.CLOUD:
            return None

        messages = state.get("messages") or []
        if not messages:
            return None

        last_human: HumanMessage | None = None
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                last_human = msg
                break
        if last_human is None:
            return None
        user_text = _extract_text_from_message(last_human).strip()
        if not user_text:
            return None

        anon_doc = state.get("kb_anon_doc")
        if anon_doc:
            return self._anon_priority(state, anon_doc)

        return await self._authenticated_priority(state, messages, user_text, runtime)

    def _anon_priority(
        self,
        state: AgentState,
        anon_doc: dict[str, Any],
    ) -> dict[str, Any]:
        path = str(anon_doc.get("path") or "")
        title = str(anon_doc.get("title") or "uploaded_document")
        priority = [
            {
                "path": path,
                "score": 1.0,
                "document_id": None,
                "title": title,
                "mentioned": True,
            }
        ]
        new_messages = list(state.get("messages") or [])
        insert_at = max(len(new_messages) - 1, 0)
        new_messages.insert(insert_at, _render_priority_message(priority))
        return {
            "kb_priority": priority,
            "kb_matched_chunk_ids": {},
            "messages": new_messages,
        }

    async def _authenticated_priority(
        self,
        state: AgentState,
        messages: Sequence[BaseMessage],
        user_text: str,
        runtime: Runtime[Any] | None = None,
    ) -> dict[str, Any]:
        t0 = asyncio.get_event_loop().time()
        (
            planned_query,
            start_date,
            end_date,
            is_recency,
        ) = await self._plan_search_inputs(
            messages=messages,
            user_text=user_text,
        )

        # Per-turn ``mentioned_document_ids`` flow:
        # 1. Preferred path (Phase 1.5+): read from ``runtime.context`` — the
        #    streaming task supplies a fresh :class:`SurfSenseContextSchema`
        #    on every ``astream_events`` call, so this list is naturally
        #    scoped to the current turn. Allows cross-turn graph reuse via
        #    ``agent_cache``.
        # 2. Legacy fallback (cache disabled / context not propagated): the
        #    constructor-injected ``self.mentioned_document_ids`` list. We
        #    drain it after the first read so a cached graph (no Phase 1.5
        #    wiring) doesn't keep replaying the same mentions on every
        #    turn.
        #
        # CRITICAL: distinguish "context absent" (legacy caller, no field at
        # all) from "context provided but empty" (turn with no mentions).
        # ``ctx_mentions`` is a ``list[int]``; an empty list is falsy in
        # Python, so a naive ``if ctx_mentions:`` would fall through to the
        # legacy closure on every no-mention follow-up turn — replaying the
        # mentions baked in by turn 1's cache-miss build. Always drain the
        # closure once the runtime path has fired so a cached middleware
        # instance can never resurrect stale state.
        mention_ids: list[int] = []
        ctx = getattr(runtime, "context", None) if runtime is not None else None
        ctx_mentions = getattr(ctx, "mentioned_document_ids", None) if ctx else None
        if ctx_mentions is not None:
            # Runtime path is authoritative — even an empty list means
            # "this turn has no mentions", NOT "look at the closure".
            mention_ids = list(ctx_mentions)
            if self.mentioned_document_ids:
                self.mentioned_document_ids = []
        elif self.mentioned_document_ids:
            mention_ids = list(self.mentioned_document_ids)
            self.mentioned_document_ids = []

        mentioned_results: list[dict[str, Any]] = []
        if mention_ids:
            mentioned_results = await fetch_mentioned_documents(
                document_ids=mention_ids,
                search_space_id=self.search_space_id,
            )

        if is_recency:
            doc_types = _resolve_search_types(
                self.available_connectors, self.available_document_types
            )
            search_results = await browse_recent_documents(
                search_space_id=self.search_space_id,
                document_type=doc_types,
                top_k=self.top_k,
                start_date=start_date,
                end_date=end_date,
            )
        else:
            search_results = await search_knowledge_base(
                query=planned_query,
                search_space_id=self.search_space_id,
                available_connectors=self.available_connectors,
                available_document_types=self.available_document_types,
                top_k=self.top_k,
                start_date=start_date,
                end_date=end_date,
            )

        seen_doc_ids: set[int] = set()
        merged: list[dict[str, Any]] = []
        for doc in mentioned_results:
            doc_id = (doc.get("document") or {}).get("id")
            if isinstance(doc_id, int):
                seen_doc_ids.add(doc_id)
            merged.append(doc)
        for doc in search_results:
            doc_id = (doc.get("document") or {}).get("id")
            if isinstance(doc_id, int) and doc_id in seen_doc_ids:
                continue
            merged.append(doc)

        priority, matched_chunk_ids = await self._materialize_priority(merged)

        new_messages = list(messages)
        insert_at = max(len(new_messages) - 1, 0)
        new_messages.insert(insert_at, _render_priority_message(priority))

        _perf_log.info(
            "[kb_priority] completed in %.3fs query=%r priority=%d mentioned=%d",
            asyncio.get_event_loop().time() - t0,
            user_text[:80],
            len(priority),
            len(mentioned_results),
        )

        return {
            "kb_priority": priority,
            "kb_matched_chunk_ids": matched_chunk_ids,
            "messages": new_messages,
        }

    async def _materialize_priority(
        self, merged: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], dict[int, list[int]]]:
        """Resolve canonical paths and matched chunk ids for the priority list."""
        priority: list[dict[str, Any]] = []
        matched_chunk_ids: dict[int, list[int]] = {}

        if not merged:
            return priority, matched_chunk_ids

        async with shielded_async_session() as session:
            index: PathIndex = await build_path_index(session, self.search_space_id)
            doc_ids = [
                (doc.get("document") or {}).get("id")
                for doc in merged
                if isinstance(doc, dict)
            ]
            doc_ids = [doc_id for doc_id in doc_ids if isinstance(doc_id, int)]
            folder_by_doc_id: dict[int, int | None] = {}
            if doc_ids:
                folder_rows = await session.execute(
                    select(Document.id, Document.folder_id).where(
                        Document.search_space_id == self.search_space_id,
                        Document.id.in_(doc_ids),
                    )
                )
                folder_by_doc_id = {row.id: row.folder_id for row in folder_rows.all()}

        for doc in merged:
            doc_meta = doc.get("document") or {}
            doc_id = doc_meta.get("id")
            title = doc_meta.get("title") or "untitled"
            folder_id = (
                folder_by_doc_id.get(doc_id)
                if isinstance(doc_id, int)
                else doc_meta.get("folder_id")
            )
            path = doc_to_virtual_path(
                doc_id=doc_id if isinstance(doc_id, int) else None,
                title=str(title),
                folder_id=folder_id if isinstance(folder_id, int) else None,
                index=index,
            )
            priority.append(
                {
                    "path": path,
                    "score": float(doc.get("score") or 0.0),
                    "document_id": doc_id if isinstance(doc_id, int) else None,
                    "title": str(title),
                    "mentioned": bool(doc.get("_user_mentioned")),
                }
            )
            if isinstance(doc_id, int):
                chunk_ids = doc.get("matched_chunk_ids") or []
                if chunk_ids:
                    matched_chunk_ids[doc_id] = [
                        int(cid) for cid in chunk_ids if isinstance(cid, int | str)
                    ]
        return priority, matched_chunk_ids


# Backwards-compatible alias for any external imports.
KnowledgeBaseSearchMiddleware = KnowledgePriorityMiddleware


__all__ = [
    "KnowledgeBaseSearchMiddleware",
    "KnowledgePriorityMiddleware",
    "browse_recent_documents",
    "fetch_mentioned_documents",
    "search_knowledge_base",
]
