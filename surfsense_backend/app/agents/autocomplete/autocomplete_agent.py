"""Vision autocomplete agent with scoped filesystem exploration.

Converts the stateless single-shot vision autocomplete into an agent that
seeds a virtual filesystem from KB search results and lets the vision LLM
explore documents via ``ls``, ``read_file``, ``glob``, ``grep``, etc.
before generating the final completion.

Performance: KB search and agent graph compilation run in parallel so
the only sequential latency is KB-search (or agent compile, whichever is
slower) + the agent's LLM turns.  There is no separate "query extraction"
LLM call — the window title is used directly as the KB search query.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from deepagents.graph import BASE_AGENT_PROMPT
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from langchain.agents import create_agent
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage

from app.agents.new_chat.middleware.filesystem import SurfSenseFilesystemMiddleware
from app.agents.new_chat.middleware.knowledge_search import (
    build_scoped_filesystem,
    search_knowledge_base,
)
from app.services.new_streaming_service import VercelStreamingService

logger = logging.getLogger(__name__)

KB_TOP_K = 10

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

AUTOCOMPLETE_SYSTEM_PROMPT = """You are a smart writing assistant that analyzes the user's screen to draft or complete text.

You will receive a screenshot of the user's screen. Your PRIMARY source of truth is the screenshot itself — the visual context determines what to write.

Your job:
1. Analyze the ENTIRE screenshot to understand what the user is working on (email thread, chat conversation, document, code editor, form, etc.).
2. Identify the text area where the user will type.
3. Generate the text the user most likely wants to write based on the visual context.

You also have access to the user's knowledge base documents via filesystem tools. However:
- ONLY consult the knowledge base if the screenshot clearly involves a topic where your KB documents are DIRECTLY relevant (e.g., the user is writing about a specific project/topic that matches a document title).
- Do NOT explore documents just because they exist. Most autocomplete requests can be answered purely from the screenshot.
- If you do read a document, only incorporate information that is 100% relevant to what the user is typing RIGHT NOW. Do not add extra details, background, or tangential information from the KB.
- Keep your output SHORT — autocomplete should feel like a natural continuation, not an essay.

Key behavior:
- If the text area is EMPTY, draft a concise response or message based on what you see on screen (e.g., reply to an email, respond to a chat message, continue a document).
- If the text area already has text, continue it naturally — typically just a sentence or two.

Rules:
- Be CONCISE. Prefer a single paragraph or a few sentences. Autocomplete is a quick assist, not a full draft.
- Match the tone and formality of the surrounding context.
- If the screen shows code, write code. If it shows a casual chat, be casual. If it shows a formal email, be formal.
- Do NOT describe the screenshot or explain your reasoning.
- Do NOT cite or reference documents explicitly — just let the knowledge inform your writing naturally.
- If you cannot determine what to write, output an empty JSON array: []

## Output Format

You MUST provide exactly 3 different suggestion options. Each should be a distinct, plausible completion — vary the tone, detail level, or angle.

Return your suggestions as a JSON array of exactly 3 strings. Output ONLY the JSON array, nothing else — no markdown fences, no explanation, no commentary.

Example format:
["First suggestion text here.", "Second suggestion — a different take.", "Third option with another approach."]

## Filesystem Tools `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`

All file paths must start with a `/`.
- ls: list files and directories at a given path.
- read_file: read a file from the filesystem.
- write_file: create a temporary file in the session (not persisted).
- edit_file: edit a file in the session (not persisted for /documents/ files).
- glob: find files matching a pattern (e.g., "**/*.xml").
- grep: search for text within files.

## When to Use Filesystem Tools

BEFORE reaching for any tool, ask yourself: "Can I write a good completion purely from the screenshot?" If yes, just write it — do NOT explore the KB.

Only use tools when:
- The user is clearly writing about a specific topic that likely has detailed information in their KB.
- You need a specific fact, name, number, or reference that the screenshot doesn't provide.

When you do use tools, be surgical:
- Check the `ls` output first. If no document title looks relevant, stop — do not read files just to see what's there.
- If a title looks relevant, read only the `<chunk_index>` (first ~20 lines) and jump to matched chunks. Do not read entire documents.
- Extract only the specific information you need and move on to generating the completion.

## Reading Documents Efficiently

Documents are formatted as XML. Each document contains:
- `<document_metadata>` — title, type, URL, etc.
- `<chunk_index>` — a table of every chunk with its **line range** and a
  `matched="true"` flag for chunks that matched the search query.
- `<document_content>` — the actual chunks in original document order.

**Workflow**: read the first ~20 lines to see the `<chunk_index>`, identify
chunks marked `matched="true"`, then use `read_file(path, offset=<start_line>,
limit=<lines>)` to jump directly to those sections."""

APP_CONTEXT_BLOCK = """

The user is currently working in "{app_name}" (window: "{window_title}"). Use this to understand the type of application and adapt your tone and format accordingly."""


def _build_autocomplete_system_prompt(app_name: str, window_title: str) -> str:
    prompt = AUTOCOMPLETE_SYSTEM_PROMPT
    if app_name:
        prompt += APP_CONTEXT_BLOCK.format(app_name=app_name, window_title=window_title)
    return prompt


# ---------------------------------------------------------------------------
# Pre-compute KB filesystem (runs in parallel with agent compilation)
# ---------------------------------------------------------------------------


class _KBResult:
    """Container for pre-computed KB filesystem results."""

    __slots__ = ("files", "ls_ai_msg", "ls_tool_msg")

    def __init__(
        self,
        files: dict[str, Any] | None = None,
        ls_ai_msg: AIMessage | None = None,
        ls_tool_msg: ToolMessage | None = None,
    ) -> None:
        self.files = files
        self.ls_ai_msg = ls_ai_msg
        self.ls_tool_msg = ls_tool_msg

    @property
    def has_documents(self) -> bool:
        return bool(self.files)


async def precompute_kb_filesystem(
    search_space_id: int,
    query: str,
    top_k: int = KB_TOP_K,
) -> _KBResult:
    """Search the KB and build the scoped filesystem outside the agent.

    This is designed to be called via ``asyncio.gather`` alongside agent
    graph compilation so the two run concurrently.
    """
    if not query:
        return _KBResult()

    try:
        search_results = await search_knowledge_base(
            query=query,
            search_space_id=search_space_id,
            top_k=top_k,
        )

        if not search_results:
            return _KBResult()

        new_files, _ = await build_scoped_filesystem(
            documents=search_results,
            search_space_id=search_space_id,
        )

        if not new_files:
            return _KBResult()

        doc_paths = [
            p
            for p, v in new_files.items()
            if p.startswith("/documents/") and v is not None
        ]
        tool_call_id = f"auto_ls_{uuid.uuid4().hex[:12]}"
        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "ls", "args": {"path": "/documents"}, "id": tool_call_id}
            ],
        )
        tool_msg = ToolMessage(
            content=str(doc_paths) if doc_paths else "No documents found.",
            tool_call_id=tool_call_id,
        )
        return _KBResult(files=new_files, ls_ai_msg=ai_msg, ls_tool_msg=tool_msg)

    except Exception:
        logger.warning(
            "KB pre-computation failed, proceeding without KB", exc_info=True
        )
        return _KBResult()


# ---------------------------------------------------------------------------
# Filesystem middleware — no save_document, no persistence
# ---------------------------------------------------------------------------


class AutocompleteFilesystemMiddleware(SurfSenseFilesystemMiddleware):
    """Filesystem middleware for autocomplete — read-only exploration only.

    Strips ``save_document`` (permanent KB persistence) and passes
    ``search_space_id=None`` so ``write_file`` / ``edit_file`` stay ephemeral.
    """

    def __init__(self) -> None:
        super().__init__(search_space_id=None, created_by_id=None)
        self.tools = [t for t in self.tools if t.name != "save_document"]


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


async def _compile_agent(
    llm: BaseChatModel,
    app_name: str,
    window_title: str,
) -> Any:
    """Compile the agent graph (CPU-bound, runs in a thread)."""
    system_prompt = _build_autocomplete_system_prompt(app_name, window_title)
    final_system_prompt = system_prompt + "\n\n" + BASE_AGENT_PROMPT

    middleware = [
        AutocompleteFilesystemMiddleware(),
        PatchToolCallsMiddleware(),
        AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
    ]

    agent = await asyncio.to_thread(
        create_agent,
        llm,
        system_prompt=final_system_prompt,
        tools=[],
        middleware=middleware,
    )
    return agent.with_config({"recursion_limit": 200})


async def create_autocomplete_agent(
    llm: BaseChatModel,
    *,
    search_space_id: int,
    kb_query: str,
    app_name: str = "",
    window_title: str = "",
) -> tuple[Any, _KBResult]:
    """Create the autocomplete agent and pre-compute KB in parallel.

    Returns ``(agent, kb_result)`` so the caller can inject the pre-computed
    filesystem into the agent's initial state without any middleware delay.
    """
    agent, kb = await asyncio.gather(
        _compile_agent(llm, app_name, window_title),
        precompute_kb_filesystem(search_space_id, kb_query),
    )
    return agent, kb


# ---------------------------------------------------------------------------
# JSON suggestion parsing (robust fallback)
# ---------------------------------------------------------------------------


def _parse_suggestions(raw: str) -> list[str]:
    """Extract a list of suggestion strings from the agent's output.

    Tries, in order:
      1. Direct ``json.loads``
      2. Extract content between ```json ... ``` fences
      3. Find the first ``[`` … ``]`` span
    Falls back to wrapping the raw text as a single suggestion.
    """
    text = raw.strip()
    if not text:
        return []

    for candidate in _json_candidates(text):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, list) and all(isinstance(s, str) for s in parsed):
                return [s for s in parsed if s.strip()]
        except (json.JSONDecodeError, ValueError):
            continue

    return [text]


def _json_candidates(text: str) -> list[str]:
    """Yield candidate JSON strings from raw text."""
    candidates = [text]

    fence = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence:
        candidates.append(fence.group(1).strip())

    bracket = re.search(r"\[.*]", text, re.DOTALL)
    if bracket:
        candidates.append(bracket.group(0))

    return candidates


# ---------------------------------------------------------------------------
# Streaming helper
# ---------------------------------------------------------------------------


async def stream_autocomplete_agent(
    agent: Any,
    input_data: dict[str, Any],
    streaming_service: VercelStreamingService,
    *,
    emit_message_start: bool = True,
) -> AsyncGenerator[str, None]:
    """Stream agent events as Vercel SSE, with thinking steps for tool calls.

    When ``emit_message_start`` is False the caller has already sent the
    ``message_start`` event (e.g. to show preparation steps before the agent
    runs).
    """
    thread_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}

    text_buffer: list[str] = []
    active_tool_depth = 0
    thinking_step_counter = 0
    tool_step_ids: dict[str, str] = {}
    step_titles: dict[str, str] = {}
    completed_step_ids: set[str] = set()
    last_active_step_id: str | None = None

    def next_thinking_step_id() -> str:
        nonlocal thinking_step_counter
        thinking_step_counter += 1
        return f"autocomplete-step-{thinking_step_counter}"

    def complete_current_step() -> str | None:
        nonlocal last_active_step_id
        if last_active_step_id and last_active_step_id not in completed_step_ids:
            completed_step_ids.add(last_active_step_id)
            title = step_titles.get(last_active_step_id, "Done")
            event = streaming_service.format_thinking_step(
                step_id=last_active_step_id,
                title=title,
                status="complete",
            )
            last_active_step_id = None
            return event
        return None

    if emit_message_start:
        yield streaming_service.format_message_start()

    gen_step_id = next_thinking_step_id()
    last_active_step_id = gen_step_id
    step_titles[gen_step_id] = "Generating suggestions"
    yield streaming_service.format_thinking_step(
        step_id=gen_step_id,
        title="Generating suggestions",
        status="in_progress",
    )

    try:
        async for event in agent.astream_events(
            input_data, config=config, version="v2"
        ):
            event_type = event.get("event", "")

            if event_type == "on_chat_model_stream":
                if active_tool_depth > 0:
                    continue
                if "surfsense:internal" in event.get("tags", []):
                    continue
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content"):
                    content = chunk.content
                    if content and isinstance(content, str):
                        text_buffer.append(content)

            elif event_type == "on_tool_start":
                active_tool_depth += 1
                tool_name = event.get("name", "unknown_tool")
                run_id = event.get("run_id", "")
                tool_input = event.get("data", {}).get("input", {})

                step_event = complete_current_step()
                if step_event:
                    yield step_event

                tool_step_id = next_thinking_step_id()
                tool_step_ids[run_id] = tool_step_id
                last_active_step_id = tool_step_id

                title, items = _describe_tool_call(tool_name, tool_input)
                step_titles[tool_step_id] = title
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title=title,
                    status="in_progress",
                    items=items,
                )

            elif event_type == "on_tool_end":
                active_tool_depth = max(0, active_tool_depth - 1)
                run_id = event.get("run_id", "")
                step_id = tool_step_ids.pop(run_id, None)
                if step_id and step_id not in completed_step_ids:
                    completed_step_ids.add(step_id)
                    title = step_titles.get(step_id, "Done")
                    yield streaming_service.format_thinking_step(
                        step_id=step_id,
                        title=title,
                        status="complete",
                    )
                    if last_active_step_id == step_id:
                        last_active_step_id = None

        step_event = complete_current_step()
        if step_event:
            yield step_event

        raw_text = "".join(text_buffer)
        suggestions = _parse_suggestions(raw_text)

        yield streaming_service.format_data(
            "suggestions", {"options": suggestions}
        )

        yield streaming_service.format_finish()
        yield streaming_service.format_done()

    except Exception as e:
        logger.error(f"Autocomplete agent streaming error: {e}", exc_info=True)
        yield streaming_service.format_error("Autocomplete failed. Please try again.")
        yield streaming_service.format_done()


def _describe_tool_call(tool_name: str, tool_input: Any) -> tuple[str, list[str]]:
    """Return a human-readable (title, items) for a tool call thinking step."""
    inp = tool_input if isinstance(tool_input, dict) else {}
    if tool_name == "ls":
        path = inp.get("path", "/")
        return "Listing files", [path]
    if tool_name == "read_file":
        fp = inp.get("file_path", "")
        display = fp if len(fp) <= 80 else "…" + fp[-77:]
        return "Reading file", [display]
    if tool_name == "write_file":
        fp = inp.get("file_path", "")
        display = fp if len(fp) <= 80 else "…" + fp[-77:]
        return "Writing file", [display]
    if tool_name == "edit_file":
        fp = inp.get("file_path", "")
        display = fp if len(fp) <= 80 else "…" + fp[-77:]
        return "Editing file", [display]
    if tool_name == "glob":
        pat = inp.get("pattern", "")
        base = inp.get("path", "/")
        return "Searching files", [f"{pat} in {base}"]
    if tool_name == "grep":
        pat = inp.get("pattern", "")
        path = inp.get("path", "")
        display_pat = pat[:60] + ("…" if len(pat) > 60 else "")
        return "Searching content", [
            f'"{display_pat}"' + (f" in {path}" if path else "")
        ]
    return f"Using {tool_name}", []
