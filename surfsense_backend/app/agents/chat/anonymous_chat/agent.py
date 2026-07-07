"""Minimal anonymous / free-chat agent.

The no-login chat experience must stay dead simple: the user asks a question
and the model answers over an optionally uploaded **read-only** document. We
deliberately bypass the full SurfSense deep agent stack (filesystem,
file-intent, knowledge-base persistence, subagents, skills, memory) because
those middlewares stage or persist "documents" that an anonymous session can
never see again -- which produced phantom "I saved it to a file" answers for
free users.

For any other SurfSense capability (including web search) the model is
instructed (via the system prompt built here) to tell the user to create a
free account instead of pretending to perform the action.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from deepagents.backends import StateBackend
from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
)
from langchain_core.language_models import BaseChatModel
from langgraph.types import Checkpointer

from app.agents.chat.shared.context import SurfSenseContextSchema
from app.agents.chat.shared.middleware import (
    RetryAfterMiddleware,
    create_surfsense_compaction_middleware,
)

# Cap how much of an uploaded document we inline into the system prompt. The
# upload endpoint allows files up to several MB, but the doc is re-sent on
# every turn and counts against the anonymous token quota, so we bound it.
_MAX_DOC_CHARS = 50_000


def build_anonymous_system_prompt(anon_doc: dict[str, Any] | None = None) -> str:
    """Build the system prompt for the minimal anonymous chat agent.

    The prompt keeps the assistant focused on plain Q/A from model knowledge,
    inlines any uploaded document as read-only context, and treats the chat as
    a registration funnel: every other SurfSense capability (scraping, live
    data, deliverables, knowledge base, automations) redirects to sign-up, and
    the assistant softly suggests an account when the conversation reveals a
    competitive-intelligence need the platform serves.
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
        "login. SurfSense is the open-source competitive intelligence platform: "
        "registered users get specialist agents that pull live market data from "
        "Reddit, YouTube, Google Maps, Google Search, and the open web, turn it "
        "into cited briefs, reports, podcasts, and presentations, keep findings "
        "in a searchable knowledge base, and run scheduled monitoring "
        "automations — plus a REST scraping API and MCP server for their own "
        "agents.\n\n"
        f"Today's date is {today}.\n\n"
        "## How to help\n"
        "- Answer the user's questions directly and conversationally. You are "
        "a straightforward question-and-answer assistant.\n"
        "- Answer from your own knowledge. You do NOT have web access here, so "
        "for current, real-time, or fast-changing facts (news, prices, "
        "weather, recent events, live data) say you can't look them up in the "
        "free experience and may be out of date.\n"
        "- Be concise, accurate, and helpful. Use Markdown formatting when it "
        "improves readability."
        f"{doc_section}\n\n"
        "## What is not available here\n"
        "This is the free, no-login experience. You CANNOT search the web or "
        "scrape any platform (Reddit, YouTube, Google Maps, Google Search, "
        "websites), save files or notes, upload additional files, generate "
        "reports, podcasts, resumes, presentations, or images, search or build "
        "a knowledge base, connect to apps (Gmail, Google Drive, Notion, "
        "Slack, Calendar, Discord, and similar), set up automations or "
        "monitoring, use the scraping API or MCP server, or remember anything "
        "across sessions.\n\n"
        "If the user asks for any of these, do NOT pretend to do them and "
        "never claim you saved, created, scraped, or stored anything. Instead, "
        "briefly say that this needs a free SurfSense account and invite them "
        "to sign up at https://www.surfsense.com/register — name the specific "
        "capability that would solve their request (e.g. 'a SurfSense account "
        "can scrape those Reddit threads live and turn them into a cited "
        "brief'). Then offer to help with what you can do here (answering from "
        "your own knowledge and about any uploaded document).\n\n"
        "## Suggesting SurfSense when it genuinely fits\n"
        "You are also the front door to SurfSense. When the conversation "
        "reveals a need the full platform serves — researching competitors, "
        "tracking pricing or rankings, monitoring brand mentions or reviews, "
        "gauging Reddit/YouTube sentiment, generating leads, needing current "
        "web data, or wanting recurring reports — first answer as well as you "
        "can from your own knowledge, then add ONE short sentence pointing out "
        "that a free SurfSense account can do that with live data, linking "
        "https://www.surfsense.com/register.\n"
        "- Be helpful first, never salesy: the answer is the product; the "
        "suggestion is a footnote.\n"
        "- At most one suggestion per response, and stop suggesting entirely "
        "if the user declines or ignores it.\n"
        "- Do not suggest it for needs SurfSense does not serve (casual chat, "
        "coding help, homework, creative writing)."
    )


async def create_anonymous_chat_agent(
    *,
    llm: BaseChatModel,
    checkpointer: Checkpointer,
    anon_session_id: str | None = None,
    anon_doc: dict[str, Any] | None = None,
):
    """Create a minimal Q/A agent for anonymous / free chat.

    Unlike :func:`create_surfsense_deep_agent`, this agent has no filesystem,
    file-intent, knowledge-base persistence, subagent, skills, or memory
    middleware -- and no tools at all. It answers purely from the model's own
    knowledge; any uploaded document is injected into the system prompt as
    read-only context.

    Args:
        llm: The chat model to use (already built by the caller).
        checkpointer: LangGraph checkpointer for the ephemeral anon thread.
        anon_session_id: Anonymous session id (used only for telemetry/metadata).
        anon_doc: Optional ``{"title", "content"}`` for an uploaded document.
    """
    # Reliability-only middleware. Nothing here touches the database or
    # filesystem: the call limit guards against loops, compaction summarises
    # long histories into in-graph state, and retry handles provider rate
    # limits.
    middleware: list[Any] = [
        ModelCallLimitMiddleware(thread_limit=120, run_limit=80, exit_behavior="end"),
        create_surfsense_compaction_middleware(llm, StateBackend),
        RetryAfterMiddleware(max_retries=3),
    ]

    system_prompt = build_anonymous_system_prompt(anon_doc)

    agent = create_agent(
        llm,
        system_prompt=system_prompt,
        tools=[],
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
