"""
Streaming task for the new SurfSense deep agent chat.

This module streams responses from the deep agent using the Vercel AI SDK
Data Stream Protocol (SSE format).

Supports loading LLM configurations from:
- YAML files (negative IDs for global configs)
- NewLLMConfig database table (positive IDs for user-created configs with prompt settings)
"""

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.agents.new_chat.chat_deepagent import create_surfsense_deep_agent
from app.agents.new_chat.checkpointer import get_checkpointer
from app.agents.new_chat.llm_config import (
    AgentConfig,
    create_chat_litellm_from_agent_config,
    create_chat_litellm_from_config,
    load_agent_config,
    load_llm_config_from_yaml,
)
from app.db import (
    ChatVisibility,
    Document,
    Report,
    SurfsenseDocsDocument,
    async_session_maker,
)
from app.prompts import TITLE_GENERATION_PROMPT_TEMPLATE
from app.services.chat_session_state_service import (
    clear_ai_responding,
    set_ai_responding,
)
from app.services.connector_service import ConnectorService
from app.services.new_streaming_service import VercelStreamingService
from app.utils.content_utils import bootstrap_history_from_db


def format_mentioned_documents_as_context(documents: list[Document]) -> str:
    """
    Format mentioned documents as context for the agent.

    Uses the same XML structure as knowledge_base.format_documents_for_context
    to ensure citations work properly with chunk IDs.
    """
    if not documents:
        return ""

    context_parts = ["<mentioned_documents>"]
    context_parts.append(
        "The user has explicitly mentioned the following documents from their knowledge base. "
        "These documents are directly relevant to the query and should be prioritized as primary sources. "
        "Use [citation:CHUNK_ID] format for citations (e.g., [citation:123])."
    )
    context_parts.append("")

    for doc in documents:
        # Build metadata JSON
        metadata = doc.document_metadata or {}
        metadata_json = json.dumps(metadata, ensure_ascii=False)

        # Get URL from metadata
        url = (
            metadata.get("url")
            or metadata.get("source")
            or metadata.get("page_url")
            or ""
        )

        context_parts.append("<document>")
        context_parts.append("<document_metadata>")
        context_parts.append(f"  <document_id>{doc.id}</document_id>")
        context_parts.append(
            f"  <document_type>{doc.document_type.value}</document_type>"
        )
        context_parts.append(f"  <title><![CDATA[{doc.title}]]></title>")
        context_parts.append(f"  <url><![CDATA[{url}]]></url>")
        context_parts.append(
            f"  <metadata_json><![CDATA[{metadata_json}]]></metadata_json>"
        )
        context_parts.append("</document_metadata>")
        context_parts.append("")
        context_parts.append("<document_content>")

        # Use chunks if available (preferred for proper citations)
        if hasattr(doc, "chunks") and doc.chunks:
            for chunk in doc.chunks:
                context_parts.append(
                    f"  <chunk id='{chunk.id}'><![CDATA[{chunk.content}]]></chunk>"
                )
        else:
            # Fallback to document content if chunks not loaded
            # Use document ID as chunk ID prefix for consistency
            context_parts.append(
                f"  <chunk id='{doc.id}'><![CDATA[{doc.content}]]></chunk>"
            )

        context_parts.append("</document_content>")
        context_parts.append("</document>")
        context_parts.append("")

    context_parts.append("</mentioned_documents>")

    return "\n".join(context_parts)


def format_mentioned_surfsense_docs_as_context(
    documents: list[SurfsenseDocsDocument],
) -> str:
    """Format mentioned SurfSense documentation as context for the agent."""
    if not documents:
        return ""

    context_parts = ["<mentioned_surfsense_docs>"]
    context_parts.append(
        "The user has explicitly mentioned the following SurfSense documentation pages. "
        "These are official documentation about how to use SurfSense and should be used to answer questions about the application. "
        "Use [citation:CHUNK_ID] format for citations (e.g., [citation:doc-123])."
    )

    for doc in documents:
        metadata_json = json.dumps({"source": doc.source}, ensure_ascii=False)

        context_parts.append("<document>")
        context_parts.append("<document_metadata>")
        context_parts.append(f"  <document_id>doc-{doc.id}</document_id>")
        context_parts.append("  <document_type>SURFSENSE_DOCS</document_type>")
        context_parts.append(f"  <title><![CDATA[{doc.title}]]></title>")
        context_parts.append(f"  <url><![CDATA[{doc.source}]]></url>")
        context_parts.append(
            f"  <metadata_json><![CDATA[{metadata_json}]]></metadata_json>"
        )
        context_parts.append("</document_metadata>")
        context_parts.append("")
        context_parts.append("<document_content>")

        if hasattr(doc, "chunks") and doc.chunks:
            for chunk in doc.chunks:
                context_parts.append(
                    f"  <chunk id='doc-{chunk.id}'><![CDATA[{chunk.content}]]></chunk>"
                )
        else:
            context_parts.append(
                f"  <chunk id='doc-0'><![CDATA[{doc.content}]]></chunk>"
            )

        context_parts.append("</document_content>")
        context_parts.append("</document>")
        context_parts.append("")

    context_parts.append("</mentioned_surfsense_docs>")

    return "\n".join(context_parts)


def extract_todos_from_deepagents(command_output) -> dict:
    """
    Extract todos from deepagents' TodoListMiddleware Command output.

    deepagents returns a Command object with:
    - Command.update['todos'] = [{'content': '...', 'status': '...'}]

    Returns the todos directly (no transformation needed - UI matches deepagents format).
    """
    todos_data = []
    if hasattr(command_output, "update"):
        # It's a Command object from deepagents
        update = command_output.update
        todos_data = update.get("todos", [])
    elif isinstance(command_output, dict):
        # Already a dict - check if it has todos directly or in update
        if "todos" in command_output:
            todos_data = command_output.get("todos", [])
        elif "update" in command_output and isinstance(command_output["update"], dict):
            todos_data = command_output["update"].get("todos", [])

    return {"todos": todos_data}


@dataclass
class StreamResult:
    accumulated_text: str = ""
    is_interrupted: bool = False
    interrupt_value: dict[str, Any] | None = None
    sandbox_files: list[str] = field(default_factory=list)


async def _stream_agent_events(
    agent: Any,
    config: dict[str, Any],
    input_data: Any,
    streaming_service: VercelStreamingService,
    result: StreamResult,
    step_prefix: str = "thinking",
    initial_step_id: str | None = None,
    initial_step_title: str = "",
    initial_step_items: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    """Shared async generator that streams and formats astream_events from the agent.

    Yields SSE-formatted strings. After exhausting, inspect the ``result``
    object for accumulated_text and interrupt state.

    Args:
        agent: The compiled LangGraph agent.
        config: LangGraph config dict (must include configurable.thread_id).
        input_data: The input to pass to agent.astream_events (dict or Command).
        streaming_service: VercelStreamingService instance for formatting events.
        result: Mutable StreamResult populated with accumulated_text / interrupt info.
        step_prefix: Prefix for thinking step IDs (e.g. "thinking" or "thinking-resume").
        initial_step_id: If set, the helper inherits an already-active thinking step.
        initial_step_title: Title of the inherited thinking step.
        initial_step_items: Items of the inherited thinking step.

    Yields:
        SSE-formatted strings for each event.
    """
    accumulated_text = ""
    current_text_id: str | None = None
    thinking_step_counter = 1 if initial_step_id else 0
    tool_step_ids: dict[str, str] = {}
    completed_step_ids: set[str] = set()
    last_active_step_id: str | None = initial_step_id
    last_active_step_title: str = initial_step_title
    last_active_step_items: list[str] = initial_step_items or []
    just_finished_tool: bool = False
    active_tool_depth: int = 0  # Track nesting: >0 means we're inside a tool

    def next_thinking_step_id() -> str:
        nonlocal thinking_step_counter
        thinking_step_counter += 1
        return f"{step_prefix}-{thinking_step_counter}"

    def complete_current_step() -> str | None:
        nonlocal last_active_step_id
        if last_active_step_id and last_active_step_id not in completed_step_ids:
            completed_step_ids.add(last_active_step_id)
            event = streaming_service.format_thinking_step(
                step_id=last_active_step_id,
                title=last_active_step_title,
                status="completed",
                items=last_active_step_items if last_active_step_items else None,
            )
            last_active_step_id = None
            return event
        return None

    async for event in agent.astream_events(input_data, config=config, version="v2"):
        event_type = event.get("event", "")

        if event_type == "on_chat_model_stream":
            if active_tool_depth > 0:
                continue  # Suppress inner-tool LLM tokens from leaking into chat
            chunk = event.get("data", {}).get("chunk")
            if chunk and hasattr(chunk, "content"):
                content = chunk.content
                if content and isinstance(content, str):
                    if current_text_id is None:
                        completion_event = complete_current_step()
                        if completion_event:
                            yield completion_event
                        if just_finished_tool:
                            last_active_step_id = None
                            last_active_step_title = ""
                            last_active_step_items = []
                            just_finished_tool = False
                        current_text_id = streaming_service.generate_text_id()
                        yield streaming_service.format_text_start(current_text_id)
                    yield streaming_service.format_text_delta(current_text_id, content)
                    accumulated_text += content

        elif event_type == "on_tool_start":
            active_tool_depth += 1
            tool_name = event.get("name", "unknown_tool")
            run_id = event.get("run_id", "")
            tool_input = event.get("data", {}).get("input", {})

            if current_text_id is not None:
                yield streaming_service.format_text_end(current_text_id)
                current_text_id = None

            if last_active_step_title != "Synthesizing response":
                completion_event = complete_current_step()
                if completion_event:
                    yield completion_event

            just_finished_tool = False
            tool_step_id = next_thinking_step_id()
            tool_step_ids[run_id] = tool_step_id
            last_active_step_id = tool_step_id

            if tool_name == "search_knowledge_base":
                query = (
                    tool_input.get("query", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                last_active_step_title = "Searching knowledge base"
                last_active_step_items = [
                    f"Query: {query[:100]}{'...' if len(query) > 100 else ''}"
                ]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Searching knowledge base",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "link_preview":
                url = (
                    tool_input.get("url", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                last_active_step_title = "Fetching link preview"
                last_active_step_items = [
                    f"URL: {url[:80]}{'...' if len(url) > 80 else ''}"
                ]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Fetching link preview",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "display_image":
                src = (
                    tool_input.get("src", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                title = (
                    tool_input.get("title", "") if isinstance(tool_input, dict) else ""
                )
                last_active_step_title = "Analyzing the image"
                last_active_step_items = [
                    f"Analyzing: {title[:50] if title else src[:50]}{'...' if len(title or src) > 50 else ''}"
                ]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Analyzing the image",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "scrape_webpage":
                url = (
                    tool_input.get("url", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                last_active_step_title = "Scraping webpage"
                last_active_step_items = [
                    f"URL: {url[:80]}{'...' if len(url) > 80 else ''}"
                ]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Scraping webpage",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "generate_podcast":
                podcast_title = (
                    tool_input.get("podcast_title", "SurfSense Podcast")
                    if isinstance(tool_input, dict)
                    else "SurfSense Podcast"
                )
                content_len = len(
                    tool_input.get("source_content", "")
                    if isinstance(tool_input, dict)
                    else ""
                )
                last_active_step_title = "Generating podcast"
                last_active_step_items = [
                    f"Title: {podcast_title}",
                    f"Content: {content_len:,} characters",
                    "Preparing audio generation...",
                ]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Generating podcast",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "generate_report":
                report_topic = (
                    tool_input.get("topic", "Report")
                    if isinstance(tool_input, dict)
                    else "Report"
                )
                is_revision = bool(
                    isinstance(tool_input, dict) and tool_input.get("parent_report_id")
                )
                step_title = "Revising report" if is_revision else "Generating report"
                last_active_step_title = step_title
                last_active_step_items = [
                    f"Topic: {report_topic}",
                    "Analyzing source content...",
                ]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title=step_title,
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "execute":
                cmd = (
                    tool_input.get("command", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                display_cmd = cmd[:80] + ("…" if len(cmd) > 80 else "")
                last_active_step_title = "Running command"
                last_active_step_items = [f"$ {display_cmd}"]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Running command",
                    status="in_progress",
                    items=last_active_step_items,
                )
            else:
                last_active_step_title = f"Using {tool_name.replace('_', ' ')}"
                last_active_step_items = []
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title=last_active_step_title,
                    status="in_progress",
                )

            tool_call_id = (
                f"call_{run_id[:32]}"
                if run_id
                else streaming_service.generate_tool_call_id()
            )
            yield streaming_service.format_tool_input_start(tool_call_id, tool_name)
            yield streaming_service.format_tool_input_available(
                tool_call_id,
                tool_name,
                tool_input if isinstance(tool_input, dict) else {"input": tool_input},
            )

        elif event_type == "on_tool_end":
            active_tool_depth = max(0, active_tool_depth - 1)
            run_id = event.get("run_id", "")
            tool_name = event.get("name", "unknown_tool")
            raw_output = event.get("data", {}).get("output", "")

            if hasattr(raw_output, "content"):
                content = raw_output.content
                if isinstance(content, str):
                    try:
                        tool_output = json.loads(content)
                    except (json.JSONDecodeError, TypeError):
                        tool_output = {"result": content}
                elif isinstance(content, dict):
                    tool_output = content
                else:
                    tool_output = {"result": str(content)}
            elif isinstance(raw_output, dict):
                tool_output = raw_output
            else:
                tool_output = {"result": str(raw_output) if raw_output else "completed"}

            tool_call_id = f"call_{run_id[:32]}" if run_id else "call_unknown"
            original_step_id = tool_step_ids.get(
                run_id, f"{step_prefix}-unknown-{run_id[:8]}"
            )
            completed_step_ids.add(original_step_id)

            if tool_name == "search_knowledge_base":
                result_info = "Search completed"
                if isinstance(tool_output, dict):
                    result_len = tool_output.get("result_length", 0)
                    if result_len > 0:
                        result_info = f"Found relevant information ({result_len} chars)"
                completed_items = [*last_active_step_items, result_info]
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Searching knowledge base",
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "link_preview":
                if isinstance(tool_output, dict):
                    title = tool_output.get("title", "Link")
                    domain = tool_output.get("domain", "")
                    has_error = "error" in tool_output
                    if has_error:
                        completed_items = [
                            *last_active_step_items,
                            f"Error: {tool_output.get('error', 'Failed to fetch')}",
                        ]
                    else:
                        completed_items = [
                            *last_active_step_items,
                            f"Title: {title[:60]}{'...' if len(title) > 60 else ''}",
                            f"Domain: {domain}" if domain else "Preview loaded",
                        ]
                else:
                    completed_items = [*last_active_step_items, "Preview loaded"]
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Fetching link preview",
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "display_image":
                if isinstance(tool_output, dict):
                    title = tool_output.get("title", "")
                    alt = tool_output.get("alt", "Image")
                    display_name = title or alt
                    completed_items = [
                        *last_active_step_items,
                        f"Analyzed: {display_name[:50]}{'...' if len(display_name) > 50 else ''}",
                    ]
                else:
                    completed_items = [*last_active_step_items, "Image analyzed"]
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Analyzing the image",
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "scrape_webpage":
                if isinstance(tool_output, dict):
                    title = tool_output.get("title", "Webpage")
                    word_count = tool_output.get("word_count", 0)
                    has_error = "error" in tool_output
                    if has_error:
                        completed_items = [
                            *last_active_step_items,
                            f"Error: {tool_output.get('error', 'Failed to scrape')[:50]}",
                        ]
                    else:
                        completed_items = [
                            *last_active_step_items,
                            f"Title: {title[:50]}{'...' if len(title) > 50 else ''}",
                            f"Extracted: {word_count:,} words",
                        ]
                else:
                    completed_items = [*last_active_step_items, "Content extracted"]
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Scraping webpage",
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "generate_podcast":
                podcast_status = (
                    tool_output.get("status", "unknown")
                    if isinstance(tool_output, dict)
                    else "unknown"
                )
                podcast_title = (
                    tool_output.get("title", "Podcast")
                    if isinstance(tool_output, dict)
                    else "Podcast"
                )
                if podcast_status == "processing":
                    completed_items = [
                        f"Title: {podcast_title}",
                        "Audio generation started",
                        "Processing in background...",
                    ]
                elif podcast_status == "already_generating":
                    completed_items = [
                        f"Title: {podcast_title}",
                        "Podcast already in progress",
                        "Please wait for it to complete",
                    ]
                elif podcast_status == "error":
                    error_msg = (
                        tool_output.get("error", "Unknown error")
                        if isinstance(tool_output, dict)
                        else "Unknown error"
                    )
                    completed_items = [
                        f"Title: {podcast_title}",
                        f"Error: {error_msg[:50]}",
                    ]
                else:
                    completed_items = last_active_step_items
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Generating podcast",
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "generate_report":
                report_status = (
                    tool_output.get("status", "unknown")
                    if isinstance(tool_output, dict)
                    else "unknown"
                )
                report_title = (
                    tool_output.get("title", "Report")
                    if isinstance(tool_output, dict)
                    else "Report"
                )
                word_count = (
                    tool_output.get("word_count", 0)
                    if isinstance(tool_output, dict)
                    else 0
                )
                is_revision = (
                    tool_output.get("is_revision", False)
                    if isinstance(tool_output, dict)
                    else False
                )
                step_title = "Revising report" if is_revision else "Generating report"

                if report_status == "ready":
                    completed_items = [
                        f"Topic: {report_title}",
                        f"{word_count:,} words",
                        "Report ready",
                    ]
                elif report_status == "failed":
                    error_msg = (
                        tool_output.get("error", "Unknown error")
                        if isinstance(tool_output, dict)
                        else "Unknown error"
                    )
                    completed_items = [
                        f"Topic: {report_title}",
                        f"Error: {error_msg[:50]}",
                    ]
                else:
                    completed_items = last_active_step_items

                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title=step_title,
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "execute":
                raw_text = (
                    tool_output.get("result", "")
                    if isinstance(tool_output, dict)
                    else str(tool_output)
                )
                m = re.match(r"^Exit code:\s*(\d+)", raw_text)
                exit_code_val = int(m.group(1)) if m else None
                if exit_code_val is not None and exit_code_val == 0:
                    completed_items = [
                        *last_active_step_items,
                        "Completed successfully",
                    ]
                elif exit_code_val is not None:
                    completed_items = [
                        *last_active_step_items,
                        f"Exit code: {exit_code_val}",
                    ]
                else:
                    completed_items = [*last_active_step_items, "Finished"]
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Running command",
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "ls":
                if isinstance(tool_output, dict):
                    ls_output = tool_output.get("result", "")
                elif isinstance(tool_output, str):
                    ls_output = tool_output
                else:
                    ls_output = str(tool_output) if tool_output else ""
                file_names: list[str] = []
                if ls_output:
                    for line in ls_output.strip().split("\n"):
                        line = line.strip()
                        if line:
                            name = line.rstrip("/").split("/")[-1]
                            if name and len(name) <= 40:
                                file_names.append(name)
                            elif name:
                                file_names.append(name[:37] + "...")
                if file_names:
                    if len(file_names) <= 5:
                        completed_items = [f"[{name}]" for name in file_names]
                    else:
                        completed_items = [f"[{name}]" for name in file_names[:4]]
                        completed_items.append(f"(+{len(file_names) - 4} more)")
                else:
                    completed_items = ["No files found"]
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Exploring files",
                    status="completed",
                    items=completed_items,
                )
            else:
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title=f"Using {tool_name.replace('_', ' ')}",
                    status="completed",
                    items=last_active_step_items,
                )

            just_finished_tool = True
            last_active_step_id = None
            last_active_step_title = ""
            last_active_step_items = []

            if tool_name == "generate_podcast":
                yield streaming_service.format_tool_output_available(
                    tool_call_id,
                    tool_output
                    if isinstance(tool_output, dict)
                    else {"result": tool_output},
                )
                if (
                    isinstance(tool_output, dict)
                    and tool_output.get("status") == "success"
                ):
                    yield streaming_service.format_terminal_info(
                        f"Podcast generated successfully: {tool_output.get('title', 'Podcast')}",
                        "success",
                    )
                else:
                    error_msg = (
                        tool_output.get("error", "Unknown error")
                        if isinstance(tool_output, dict)
                        else "Unknown error"
                    )
                    yield streaming_service.format_terminal_info(
                        f"Podcast generation failed: {error_msg}",
                        "error",
                    )
            elif tool_name == "link_preview":
                yield streaming_service.format_tool_output_available(
                    tool_call_id,
                    tool_output
                    if isinstance(tool_output, dict)
                    else {"result": tool_output},
                )
                if isinstance(tool_output, dict) and "error" not in tool_output:
                    title = tool_output.get("title", "Link")
                    yield streaming_service.format_terminal_info(
                        f"Link preview loaded: {title[:50]}{'...' if len(title) > 50 else ''}",
                        "success",
                    )
                else:
                    error_msg = (
                        tool_output.get("error", "Failed to fetch")
                        if isinstance(tool_output, dict)
                        else "Failed to fetch"
                    )
                    yield streaming_service.format_terminal_info(
                        f"Link preview failed: {error_msg}",
                        "error",
                    )
            elif tool_name == "display_image":
                yield streaming_service.format_tool_output_available(
                    tool_call_id,
                    tool_output
                    if isinstance(tool_output, dict)
                    else {"result": tool_output},
                )
                if isinstance(tool_output, dict):
                    title = tool_output.get("title") or tool_output.get("alt", "Image")
                    yield streaming_service.format_terminal_info(
                        f"Image analyzed: {title[:40]}{'...' if len(title) > 40 else ''}",
                        "success",
                    )
            elif tool_name == "scrape_webpage":
                if isinstance(tool_output, dict):
                    display_output = {
                        k: v for k, v in tool_output.items() if k != "content"
                    }
                    if "content" in tool_output:
                        content = tool_output.get("content", "")
                        display_output["content_preview"] = (
                            content[:500] + "..." if len(content) > 500 else content
                        )
                    yield streaming_service.format_tool_output_available(
                        tool_call_id,
                        display_output,
                    )
                else:
                    yield streaming_service.format_tool_output_available(
                        tool_call_id,
                        {"result": tool_output},
                    )
                if isinstance(tool_output, dict) and "error" not in tool_output:
                    title = tool_output.get("title", "Webpage")
                    word_count = tool_output.get("word_count", 0)
                    yield streaming_service.format_terminal_info(
                        f"Scraped: {title[:40]}{'...' if len(title) > 40 else ''} ({word_count:,} words)",
                        "success",
                    )
                else:
                    error_msg = (
                        tool_output.get("error", "Failed to scrape")
                        if isinstance(tool_output, dict)
                        else "Failed to scrape"
                    )
                    yield streaming_service.format_terminal_info(
                        f"Scrape failed: {error_msg}",
                        "error",
                    )
            elif tool_name == "search_knowledge_base":
                yield streaming_service.format_tool_output_available(
                    tool_call_id,
                    {"status": "completed", "result_length": len(str(tool_output))},
                )
                yield streaming_service.format_terminal_info(
                    "Knowledge base search completed", "success"
                )
            elif tool_name == "generate_report":
                # Stream the full report result so frontend can render the ReportCard
                yield streaming_service.format_tool_output_available(
                    tool_call_id,
                    tool_output
                    if isinstance(tool_output, dict)
                    else {"result": tool_output},
                )
                # Send appropriate terminal message based on status
                if (
                    isinstance(tool_output, dict)
                    and tool_output.get("status") == "ready"
                ):
                    word_count = tool_output.get("word_count", 0)
                    yield streaming_service.format_terminal_info(
                        f"Report generated: {tool_output.get('title', 'Report')} ({word_count:,} words)",
                        "success",
                    )
                else:
                    error_msg = (
                        tool_output.get("error", "Unknown error")
                        if isinstance(tool_output, dict)
                        else "Unknown error"
                    )
                    yield streaming_service.format_terminal_info(
                        f"Report generation failed: {error_msg}",
                        "error",
                    )
            elif tool_name in (
                "create_notion_page",
                "update_notion_page",
                "delete_notion_page",
                "create_linear_issue",
                "update_linear_issue",
                "delete_linear_issue",
                "create_google_drive_file",
                "delete_google_drive_file",
            ):
                yield streaming_service.format_tool_output_available(
                    tool_call_id,
                    tool_output
                    if isinstance(tool_output, dict)
                    else {"result": tool_output},
                )
            elif tool_name == "execute":
                raw_text = (
                    tool_output.get("result", "")
                    if isinstance(tool_output, dict)
                    else str(tool_output)
                )
                exit_code: int | None = None
                output_text = raw_text
                m = re.match(r"^Exit code:\s*(\d+)", raw_text)
                if m:
                    exit_code = int(m.group(1))
                    om = re.search(r"\nOutput:\n([\s\S]*)", raw_text)
                    output_text = om.group(1) if om else ""
                thread_id_str = config.get("configurable", {}).get("thread_id", "")

                for sf_match in re.finditer(
                    r"^SANDBOX_FILE:\s*(.+)$", output_text, re.MULTILINE
                ):
                    fpath = sf_match.group(1).strip()
                    if fpath and fpath not in result.sandbox_files:
                        result.sandbox_files.append(fpath)

                yield streaming_service.format_tool_output_available(
                    tool_call_id,
                    {
                        "exit_code": exit_code,
                        "output": output_text,
                        "thread_id": thread_id_str,
                    },
                )
            else:
                yield streaming_service.format_tool_output_available(
                    tool_call_id,
                    {"status": "completed", "result_length": len(str(tool_output))},
                )
                yield streaming_service.format_terminal_info(
                    f"Tool {tool_name} completed", "success"
                )

        elif event_type == "on_custom_event" and event.get("name") == "report_progress":
            # Live progress updates from inside the generate_report tool
            data = event.get("data", {})
            message = data.get("message", "")
            if message and last_active_step_id:
                phase = data.get("phase", "")
                # Always keep the "Topic: ..." line
                topic_items = [
                    item for item in last_active_step_items if item.startswith("Topic:")
                ]

                if phase in ("revising_section", "adding_section"):
                    # During section-level ops: keep plan summary + show current op
                    plan_items = [
                        item
                        for item in last_active_step_items
                        if item.startswith("Topic:")
                        or item.startswith("Modifying ")
                        or item.startswith("Adding ")
                        or item.startswith("Removing ")
                    ]
                    # Only keep plan_items that don't end with "..." (not progress lines)
                    plan_items = [
                        item for item in plan_items if not item.endswith("...")
                    ]
                    last_active_step_items = [*plan_items, message]
                else:
                    # Phase transitions: replace everything after topic
                    last_active_step_items = [*topic_items, message]

                yield streaming_service.format_thinking_step(
                    step_id=last_active_step_id,
                    title=last_active_step_title,
                    status="in_progress",
                    items=last_active_step_items,
                )

        elif event_type in ("on_chain_end", "on_agent_end"):
            if current_text_id is not None:
                yield streaming_service.format_text_end(current_text_id)
                current_text_id = None

    if current_text_id is not None:
        yield streaming_service.format_text_end(current_text_id)

    completion_event = complete_current_step()
    if completion_event:
        yield completion_event

    result.accumulated_text = accumulated_text

    state = await agent.aget_state(config)
    is_interrupted = state.tasks and any(task.interrupts for task in state.tasks)
    if is_interrupted:
        result.is_interrupted = True
        result.interrupt_value = state.tasks[0].interrupts[0].value
        yield streaming_service.format_interrupt_request(result.interrupt_value)


def _try_persist_and_delete_sandbox(
    thread_id: int,
    sandbox_files: list[str],
) -> None:
    """Fire-and-forget: persist sandbox files locally then delete the sandbox."""
    from app.agents.new_chat.sandbox import (
        is_sandbox_enabled,
        persist_and_delete_sandbox,
    )

    if not is_sandbox_enabled():
        return

    async def _run() -> None:
        try:
            await persist_and_delete_sandbox(thread_id, sandbox_files)
        except Exception:
            logging.getLogger(__name__).warning(
                "persist_and_delete_sandbox failed for thread %s",
                thread_id,
                exc_info=True,
            )

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        pass


async def stream_new_chat(
    user_query: str,
    search_space_id: int,
    chat_id: int,
    session: AsyncSession,
    user_id: str | None = None,
    llm_config_id: int = -1,
    mentioned_document_ids: list[int] | None = None,
    mentioned_surfsense_doc_ids: list[int] | None = None,
    checkpoint_id: str | None = None,
    needs_history_bootstrap: bool = False,
    thread_visibility: ChatVisibility | None = None,
    current_user_display_name: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Stream chat responses from the new SurfSense deep agent.

    This uses the Vercel AI SDK Data Stream Protocol (SSE format) for streaming.
    The chat_id is used as LangGraph's thread_id for memory/checkpointing.

    Args:
        user_query: The user's query
        search_space_id: The search space ID
        chat_id: The chat ID (used as LangGraph thread_id for memory)
        session: The database session
        user_id: The current user's UUID string (for memory tools and session state)
        llm_config_id: The LLM configuration ID (default: -1 for first global config)
        needs_history_bootstrap: If True, load message history from DB (for cloned chats)
        mentioned_document_ids: Optional list of document IDs mentioned with @ in the chat
        mentioned_surfsense_doc_ids: Optional list of SurfSense doc IDs mentioned with @ in the chat
        checkpoint_id: Optional checkpoint ID to rewind/fork from (for edit/reload operations)

    Yields:
        str: SSE formatted response strings
    """
    streaming_service = VercelStreamingService()
    stream_result = StreamResult()

    try:
        # Mark AI as responding to this user for live collaboration
        if user_id:
            await set_ai_responding(session, chat_id, UUID(user_id))
        # Load LLM config - supports both YAML (negative IDs) and database (positive IDs)
        agent_config: AgentConfig | None = None

        if llm_config_id >= 0:
            # Positive ID: Load from NewLLMConfig database table
            agent_config = await load_agent_config(
                session=session,
                config_id=llm_config_id,
                search_space_id=search_space_id,
            )
            if not agent_config:
                yield streaming_service.format_error(
                    f"Failed to load NewLLMConfig with id {llm_config_id}"
                )
                yield streaming_service.format_done()
                return

            # Create ChatLiteLLM from AgentConfig
            llm = create_chat_litellm_from_agent_config(agent_config)
        else:
            # Negative ID: Load from YAML (global configs)
            llm_config = load_llm_config_from_yaml(llm_config_id=llm_config_id)
            if not llm_config:
                yield streaming_service.format_error(
                    f"Failed to load LLM config with id {llm_config_id}"
                )
                yield streaming_service.format_done()
                return

            # Create ChatLiteLLM from YAML config dict
            llm = create_chat_litellm_from_config(llm_config)
            # Create AgentConfig from YAML for consistency (uses defaults for prompt settings)
            agent_config = AgentConfig.from_yaml_config(llm_config)

        if not llm:
            yield streaming_service.format_error("Failed to create LLM instance")
            yield streaming_service.format_done()
            return

        # Create connector service
        connector_service = ConnectorService(session, search_space_id=search_space_id)

        # Get Firecrawl API key from webcrawler connector if configured
        from app.db import SearchSourceConnectorType

        firecrawl_api_key = None
        webcrawler_connector = await connector_service.get_connector_by_type(
            SearchSourceConnectorType.WEBCRAWLER_CONNECTOR, search_space_id
        )
        if webcrawler_connector and webcrawler_connector.config:
            firecrawl_api_key = webcrawler_connector.config.get("FIRECRAWL_API_KEY")

        # Get the PostgreSQL checkpointer for persistent conversation memory
        checkpointer = await get_checkpointer()

        # Optionally provision a sandboxed code execution environment
        sandbox_backend = None
        from app.agents.new_chat.sandbox import (
            get_or_create_sandbox,
            is_sandbox_enabled,
        )

        if is_sandbox_enabled():
            try:
                sandbox_backend = await get_or_create_sandbox(chat_id)
            except Exception as sandbox_err:
                logging.getLogger(__name__).warning(
                    "Sandbox creation failed, continuing without execute tool: %s",
                    sandbox_err,
                )

        visibility = thread_visibility or ChatVisibility.PRIVATE
        agent = await create_surfsense_deep_agent(
            llm=llm,
            search_space_id=search_space_id,
            db_session=session,
            connector_service=connector_service,
            checkpointer=checkpointer,
            user_id=user_id,
            thread_id=chat_id,
            agent_config=agent_config,
            firecrawl_api_key=firecrawl_api_key,
            thread_visibility=visibility,
            sandbox_backend=sandbox_backend,
        )

        # Build input with message history
        langchain_messages = []

        # Bootstrap history for cloned chats (no LangGraph checkpoint exists yet)
        if needs_history_bootstrap:
            langchain_messages = await bootstrap_history_from_db(
                session, chat_id, thread_visibility=visibility
            )

            # Clear the flag so we don't bootstrap again on next message
            from app.db import NewChatThread

            thread_result = await session.execute(
                select(NewChatThread).filter(NewChatThread.id == chat_id)
            )
            thread = thread_result.scalars().first()
            if thread:
                thread.needs_history_bootstrap = False
                await session.commit()

        # Fetch mentioned documents if any (with chunks for proper citations)
        mentioned_documents: list[Document] = []
        if mentioned_document_ids:
            from sqlalchemy.orm import selectinload as doc_selectinload

            result = await session.execute(
                select(Document)
                .options(doc_selectinload(Document.chunks))
                .filter(
                    Document.id.in_(mentioned_document_ids),
                    Document.search_space_id == search_space_id,
                )
            )
            mentioned_documents = list(result.scalars().all())

        # Fetch mentioned SurfSense docs if any
        mentioned_surfsense_docs: list[SurfsenseDocsDocument] = []
        if mentioned_surfsense_doc_ids:
            from sqlalchemy.orm import selectinload

            result = await session.execute(
                select(SurfsenseDocsDocument)
                .options(selectinload(SurfsenseDocsDocument.chunks))
                .filter(
                    SurfsenseDocsDocument.id.in_(mentioned_surfsense_doc_ids),
                )
            )
            mentioned_surfsense_docs = list(result.scalars().all())

        # Fetch the most recent report(s) in this thread so the LLM can
        # easily find report_id for versioning decisions, instead of
        # having to dig through conversation history.
        recent_reports_result = await session.execute(
            select(Report)
            .filter(
                Report.thread_id == chat_id,
                Report.content.isnot(None),  # exclude failed reports
            )
            .order_by(Report.id.desc())
            .limit(3)
        )
        recent_reports = list(recent_reports_result.scalars().all())

        # Format the user query with context (mentioned documents + SurfSense docs)
        final_query = user_query
        context_parts = []

        if mentioned_documents:
            context_parts.append(
                format_mentioned_documents_as_context(mentioned_documents)
            )

        if mentioned_surfsense_docs:
            context_parts.append(
                format_mentioned_surfsense_docs_as_context(mentioned_surfsense_docs)
            )

        # Surface report IDs prominently so the LLM doesn't have to
        # retrieve them from old tool responses in conversation history.
        if recent_reports:
            report_lines = []
            for r in recent_reports:
                report_lines.append(
                    f'  - report_id={r.id}, title="{r.title}", '
                    f'style="{r.report_style or "detailed"}"'
                )
            reports_listing = "\n".join(report_lines)
            context_parts.append(
                "<report_context>\n"
                "Previously generated reports in this conversation:\n"
                f"{reports_listing}\n\n"
                "If the user wants to MODIFY, REVISE, UPDATE, or ADD to one of "
                "these reports, set parent_report_id to the relevant report_id above.\n"
                "If the user wants a completely NEW report on a different topic, "
                "leave parent_report_id unset.\n"
                "</report_context>"
            )

        if context_parts:
            context = "\n\n".join(context_parts)
            final_query = f"{context}\n\n<user_query>{user_query}</user_query>"

        if visibility == ChatVisibility.SEARCH_SPACE and current_user_display_name:
            final_query = f"**[{current_user_display_name}]:** {final_query}"

        # if messages:
        #     # Convert frontend messages to LangChain format
        #     for msg in messages:
        #         if msg.role == "user":
        #             langchain_messages.append(HumanMessage(content=msg.content))
        #         elif msg.role == "assistant":
        #             langchain_messages.append(AIMessage(content=msg.content))
        # else:
        # Fallback: just use the current user query with attachment context
        langchain_messages.append(HumanMessage(content=final_query))

        input_state = {
            # Lets not pass this message atm because we are using the checkpointer to manage the conversation history
            # We will use this to simulate group chat functionality in the future
            "messages": langchain_messages,
            "search_space_id": search_space_id,
        }

        # All pre-streaming DB reads are done.  Commit to release the
        # transaction and its ACCESS SHARE locks so we don't block DDL
        # (e.g. migrations) for the entire duration of LLM streaming.
        # Tools that need DB access during streaming will start their own
        # short-lived transactions (or use isolated sessions).
        await session.commit()

        # Configure LangGraph with thread_id for memory
        # If checkpoint_id is provided, fork from that checkpoint (for edit/reload)
        configurable = {"thread_id": str(chat_id)}
        if checkpoint_id:
            configurable["checkpoint_id"] = checkpoint_id

        config = {
            "configurable": configurable,
            "recursion_limit": 80,  # Increase from default 25 to allow more tool iterations
        }

        # Start the message stream
        yield streaming_service.format_message_start()
        yield streaming_service.format_start_step()

        # Initial thinking step - analyzing the request
        if mentioned_documents or mentioned_surfsense_docs:
            initial_title = "Analyzing referenced content"
            action_verb = "Analyzing"
        else:
            initial_title = "Understanding your request"
            action_verb = "Processing"

        processing_parts = []
        query_text = user_query[:80] + ("..." if len(user_query) > 80 else "")
        processing_parts.append(query_text)

        if mentioned_documents:
            doc_names = []
            for doc in mentioned_documents:
                title = doc.title
                if len(title) > 30:
                    title = title[:27] + "..."
                doc_names.append(title)
            if len(doc_names) == 1:
                processing_parts.append(f"[{doc_names[0]}]")
            else:
                processing_parts.append(f"[{len(doc_names)} documents]")

        if mentioned_surfsense_docs:
            doc_names = []
            for doc in mentioned_surfsense_docs:
                title = doc.title
                if len(title) > 30:
                    title = title[:27] + "..."
                doc_names.append(title)
            if len(doc_names) == 1:
                processing_parts.append(f"[{doc_names[0]}]")
            else:
                processing_parts.append(f"[{len(doc_names)} docs]")

        initial_items = [f"{action_verb}: {' '.join(processing_parts)}"]
        initial_step_id = "thinking-1"

        yield streaming_service.format_thinking_step(
            step_id=initial_step_id,
            title=initial_title,
            status="in_progress",
            items=initial_items,
        )

        async for sse in _stream_agent_events(
            agent=agent,
            config=config,
            input_data=input_state,
            streaming_service=streaming_service,
            result=stream_result,
            step_prefix="thinking",
            initial_step_id=initial_step_id,
            initial_step_title=initial_title,
            initial_step_items=initial_items,
        ):
            yield sse

        if stream_result.is_interrupted:
            yield streaming_service.format_finish_step()
            yield streaming_service.format_finish()
            yield streaming_service.format_done()
            return

        accumulated_text = stream_result.accumulated_text

        # Generate LLM title for new chats after first response
        # Check if this is the first assistant response by counting existing assistant messages
        from sqlalchemy import func

        from app.db import NewChatMessage, NewChatThread

        assistant_count_result = await session.execute(
            select(func.count(NewChatMessage.id)).filter(
                NewChatMessage.thread_id == chat_id,
                NewChatMessage.role == "assistant",
            )
        )
        assistant_message_count = assistant_count_result.scalar() or 0

        # Only generate title on the first response (no prior assistant messages)
        if assistant_message_count == 0:
            generated_title = None
            try:
                # Generate title using the same LLM
                title_chain = TITLE_GENERATION_PROMPT_TEMPLATE | llm
                # Truncate inputs to avoid context length issues
                truncated_query = user_query[:500]
                truncated_response = accumulated_text[:1000]
                title_result = await title_chain.ainvoke(
                    {
                        "user_query": truncated_query,
                        "assistant_response": truncated_response,
                    }
                )

                # Extract and clean the title
                if title_result and hasattr(title_result, "content"):
                    raw_title = title_result.content.strip()
                    # Validate the title (reasonable length)
                    if raw_title and len(raw_title) <= 100:
                        # Remove any quotes or extra formatting
                        generated_title = raw_title.strip("\"'")
            except Exception:
                generated_title = None

            # Only update if LLM succeeded (keep truncated prompt title as fallback)
            if generated_title:
                # Fetch thread and update title
                thread_result = await session.execute(
                    select(NewChatThread).filter(NewChatThread.id == chat_id)
                )
                thread = thread_result.scalars().first()
                if thread:
                    thread.title = generated_title
                    await session.commit()

                    # Notify frontend of the title update
                    yield streaming_service.format_thread_title_update(
                        chat_id, generated_title
                    )

        # Finish the step and message
        yield streaming_service.format_finish_step()
        yield streaming_service.format_finish()
        yield streaming_service.format_done()

    except Exception as e:
        # Handle any errors
        import traceback

        error_message = f"Error during chat: {e!s}"
        print(f"[stream_new_chat] {error_message}")
        print(f"[stream_new_chat] Exception type: {type(e).__name__}")
        print(f"[stream_new_chat] Traceback:\n{traceback.format_exc()}")

        yield streaming_service.format_error(error_message)
        yield streaming_service.format_finish_step()
        yield streaming_service.format_finish()
        yield streaming_service.format_done()

    finally:
        # Clear AI responding state for live collaboration.
        # The original session may be broken (client disconnect / CancelledError
        # can corrupt the underlying DB connection), so we try a rollback first
        # and fall back to a fresh session if the original is unusable.
        try:
            await session.rollback()
            await clear_ai_responding(session, chat_id)
        except Exception:
            try:
                async with async_session_maker() as fresh_session:
                    await clear_ai_responding(fresh_session, chat_id)
            except Exception:
                logging.getLogger(__name__).warning(
                    "Failed to clear AI responding state for thread %s", chat_id
                )

        _try_persist_and_delete_sandbox(chat_id, stream_result.sandbox_files)


async def stream_resume_chat(
    chat_id: int,
    search_space_id: int,
    decisions: list[dict],
    session: AsyncSession,
    user_id: str | None = None,
    llm_config_id: int = -1,
    thread_visibility: ChatVisibility | None = None,
) -> AsyncGenerator[str, None]:
    streaming_service = VercelStreamingService()
    stream_result = StreamResult()

    try:
        if user_id:
            await set_ai_responding(session, chat_id, UUID(user_id))

        agent_config: AgentConfig | None = None
        if llm_config_id >= 0:
            agent_config = await load_agent_config(
                session=session,
                config_id=llm_config_id,
                search_space_id=search_space_id,
            )
            if not agent_config:
                yield streaming_service.format_error(
                    f"Failed to load NewLLMConfig with id {llm_config_id}"
                )
                yield streaming_service.format_done()
                return
            llm = create_chat_litellm_from_agent_config(agent_config)
        else:
            llm_config = load_llm_config_from_yaml(llm_config_id=llm_config_id)
            if not llm_config:
                yield streaming_service.format_error(
                    f"Failed to load LLM config with id {llm_config_id}"
                )
                yield streaming_service.format_done()
                return
            llm = create_chat_litellm_from_config(llm_config)
            agent_config = AgentConfig.from_yaml_config(llm_config)

        if not llm:
            yield streaming_service.format_error("Failed to create LLM instance")
            yield streaming_service.format_done()
            return

        connector_service = ConnectorService(session, search_space_id=search_space_id)

        from app.db import SearchSourceConnectorType

        firecrawl_api_key = None
        webcrawler_connector = await connector_service.get_connector_by_type(
            SearchSourceConnectorType.WEBCRAWLER_CONNECTOR, search_space_id
        )
        if webcrawler_connector and webcrawler_connector.config:
            firecrawl_api_key = webcrawler_connector.config.get("FIRECRAWL_API_KEY")

        checkpointer = await get_checkpointer()

        sandbox_backend = None
        from app.agents.new_chat.sandbox import (
            get_or_create_sandbox,
            is_sandbox_enabled,
        )

        if is_sandbox_enabled():
            try:
                sandbox_backend = await get_or_create_sandbox(chat_id)
            except Exception as sandbox_err:
                logging.getLogger(__name__).warning(
                    "Sandbox creation failed, continuing without execute tool: %s",
                    sandbox_err,
                )

        visibility = thread_visibility or ChatVisibility.PRIVATE

        agent = await create_surfsense_deep_agent(
            llm=llm,
            search_space_id=search_space_id,
            db_session=session,
            connector_service=connector_service,
            checkpointer=checkpointer,
            user_id=user_id,
            thread_id=chat_id,
            agent_config=agent_config,
            firecrawl_api_key=firecrawl_api_key,
            thread_visibility=visibility,
            sandbox_backend=sandbox_backend,
        )

        # Release the transaction before streaming (same rationale as stream_new_chat).
        await session.commit()

        from langgraph.types import Command

        config = {
            "configurable": {"thread_id": str(chat_id)},
            "recursion_limit": 80,
        }

        yield streaming_service.format_message_start()
        yield streaming_service.format_start_step()

        async for sse in _stream_agent_events(
            agent=agent,
            config=config,
            input_data=Command(resume={"decisions": decisions}),
            streaming_service=streaming_service,
            result=stream_result,
            step_prefix="thinking-resume",
        ):
            yield sse
        if stream_result.is_interrupted:
            yield streaming_service.format_finish_step()
            yield streaming_service.format_finish()
            yield streaming_service.format_done()
            return

        yield streaming_service.format_finish_step()
        yield streaming_service.format_finish()
        yield streaming_service.format_done()

    except Exception as e:
        import traceback

        error_message = f"Error during resume: {e!s}"
        print(f"[stream_resume_chat] {error_message}")
        print(f"[stream_resume_chat] Traceback:\n{traceback.format_exc()}")
        yield streaming_service.format_error(error_message)
        yield streaming_service.format_finish_step()
        yield streaming_service.format_finish()
        yield streaming_service.format_done()

    finally:
        try:
            await session.rollback()
            await clear_ai_responding(session, chat_id)
        except Exception:
            try:
                async with async_session_maker() as fresh_session:
                    await clear_ai_responding(fresh_session, chat_id)
            except Exception:
                logging.getLogger(__name__).warning(
                    "Failed to clear AI responding state for thread %s", chat_id
                )

        _try_persist_and_delete_sandbox(chat_id, stream_result.sandbox_files)
