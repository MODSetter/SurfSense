"""Minimal anonymous / free-chat agent.

The no-login chat experience must stay dead simple: the user asks a question
and the model answers, optionally using ``web_search`` and an optionally
uploaded **read-only** document. We deliberately bypass the full SurfSense deep
agent stack (filesystem, file-intent, knowledge-base persistence, subagents,
skills, memory) because those middlewares stage or persist "documents" that an
anonymous session can never see again -- which produced phantom
"I saved it to a file" answers for free users.

For any other SurfSense capability the model is instructed (via the system
prompt built here) to tell the user to create a free account instead of
pretending to perform the action.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from deepagents.backends import StateBackend
from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
)
from langchain_core.language_models import BaseChatModel
from langgraph.types import Checkpointer

from app.agents.new_chat.context import SurfSenseContextSchema
from app.agents.shared.middleware import (
    RetryAfterMiddleware,
    create_surfsense_compaction_middleware,
)
from app.agents.new_chat.tools.web_search import create_web_search_tool

# Cap how much of an uploaded document we inline into the system prompt. The
# upload endpoint allows files up to several MB, but the doc is re-sent on
# every turn and counts against the anonymous token quota, so we bound it.
_MAX_DOC_CHARS = 50_000


def build_anonymous_system_prompt(anon_doc: dict[str, Any] | None = None) -> str:
    """Build the system prompt for the minimal anonymous chat agent.

    The prompt keeps the assistant focused on plain Q/A + web search, inlines
    any uploaded document as read-only context, and redirects every other
    SurfSense feature to account registration.
    """
    today = datetime.now(UTC).strftime("%A, %B %d, %Y")

    doc_section = ""
    if anon_doc:
        title = str(anon_doc.get("title") or "uploaded_document")
        content = str(anon_doc.get("content") or "")
        truncated = content[:_MAX_DOC_CHARS]
        truncation_note = ""
        if len(content) > _MAX_DOC_CHARS:
            truncation_note = (
                "\n\n[Note: the document was truncated because it is large; "
                "only the beginning is shown.]"
            )
        doc_section = (
            "\n\n## Uploaded document (read-only)\n"
            f'The user uploaded a document named "{title}". Its contents are '
            "provided below for reference only. You may read it and answer "
            "questions about it, but you cannot modify, save, or store it.\n\n"
            f'<uploaded_document title="{title}">\n'
            f"{truncated}{truncation_note}\n"
            "</uploaded_document>"
        )

    return (
        "You are SurfSense's free AI assistant, available to everyone without "
        "login.\n\n"
        f"Today's date is {today}.\n\n"
        "## How to help\n"
        "- Answer the user's questions directly and conversationally. You are "
        "a straightforward question-and-answer assistant.\n"
        "- When a question needs current, real-time, or factual information "
        "from the internet (news, prices, weather, recent events, live data), "
        "use the `web_search` tool. Otherwise, answer directly from your own "
        "knowledge.\n"
        "- Be concise, accurate, and helpful. Use Markdown formatting when it "
        "improves readability."
        f"{doc_section}\n\n"
        "## What is not available here\n"
        "This is the free, no-login experience. You CANNOT save files or "
        "notes, generate reports, podcasts, resumes, presentations, or images, "
        "search or build a knowledge base, connect to apps (Gmail, Google "
        "Drive, Notion, Slack, Calendar, Discord, and similar), set up "
        "automations, or remember anything across sessions.\n\n"
        "If the user asks for any of these, do NOT pretend to do them and "
        "never claim you saved, created, or stored anything. Instead, briefly "
        "let them know the feature requires a free SurfSense account and "
        "invite them to create one at https://www.surfsense.com. Then offer to "
        "help with what you can do here (answering questions and searching the "
        "web)."
    )


async def create_anonymous_chat_agent(
    *,
    llm: BaseChatModel,
    checkpointer: Checkpointer,
    anon_session_id: str | None = None,
    anon_doc: dict[str, Any] | None = None,
    enable_web_search: bool = True,
):
    """Create a minimal Q/A agent for anonymous / free chat.

    Unlike :func:`create_surfsense_deep_agent`, this agent has no filesystem,
    file-intent, knowledge-base persistence, subagent, skills, or memory
    middleware. Its only tool is ``web_search`` (when ``enable_web_search`` is
    True), and any uploaded document is injected into the system prompt as
    read-only context.

    Args:
        llm: The chat model to use (already built by the caller).
        checkpointer: LangGraph checkpointer for the ephemeral anon thread.
        anon_session_id: Anonymous session id (used only for telemetry/metadata).
        anon_doc: Optional ``{"title", "content"}`` for an uploaded document.
        enable_web_search: When False, the agent runs as a pure LLM with no
            tools (used when the user toggles web search off).
    """
    tools = (
        [create_web_search_tool(search_space_id=None, available_connectors=None)]
        if enable_web_search
        else []
    )

    # Reliability-only middleware. Nothing here touches the database or
    # filesystem: call limits guard against loops, compaction summarises long
    # histories into in-graph state, and retry handles provider rate limits.
    middleware: list[Any] = [
        ModelCallLimitMiddleware(thread_limit=120, run_limit=80, exit_behavior="end"),
    ]
    if tools:
        middleware.append(
            ToolCallLimitMiddleware(
                thread_limit=300, run_limit=80, exit_behavior="continue"
            )
        )
    middleware.append(create_surfsense_compaction_middleware(llm, StateBackend))
    middleware.append(RetryAfterMiddleware(max_retries=3))

    system_prompt = build_anonymous_system_prompt(anon_doc)

    agent = create_agent(
        llm,
        system_prompt=system_prompt,
        tools=tools,
        middleware=middleware,
        context_schema=SurfSenseContextSchema,
        checkpointer=checkpointer,
    )
    return agent.with_config(
        {
            "recursion_limit": 40,
            "metadata": {
                "ls_integration": "surfsense_anonymous_chat",
                "anon_session_id": anon_session_id,
            },
        }
    )


__all__ = ["build_anonymous_system_prompt", "create_anonymous_chat_agent"]
