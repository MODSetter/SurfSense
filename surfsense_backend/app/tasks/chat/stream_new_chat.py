"""
Streaming task for the new SurfSense deep agent chat.

This module streams responses from the deep agent using the Vercel AI SDK
Data Stream Protocol (SSE format).
"""

import json
from collections.abc import AsyncGenerator
from uuid import UUID

from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.chat_deepagent import create_surfsense_deep_agent
from app.agents.new_chat.checkpointer import get_checkpointer
from app.agents.new_chat.llm_config import (
    create_chat_litellm_from_config,
    load_llm_config_from_yaml,
)
from app.schemas.new_chat import ChatAttachment, ChatMessage
from app.services.connector_service import ConnectorService
from app.services.new_streaming_service import VercelStreamingService


def format_attachments_as_context(attachments: list[ChatAttachment]) -> str:
    """Format attachments as context for the agent."""
    if not attachments:
        return ""

    context_parts = ["<user_attachments>"]
    for i, attachment in enumerate(attachments, 1):
        context_parts.append(
            f"<attachment index='{i}' name='{attachment.name}' type='{attachment.type}'>"
        )
        context_parts.append(f"<![CDATA[{attachment.content}]]>")
        context_parts.append("</attachment>")
    context_parts.append("</user_attachments>")

    return "\n".join(context_parts)


async def stream_new_chat(
    user_query: str,
    user_id: str | UUID,
    search_space_id: int,
    chat_id: int,
    session: AsyncSession,
    llm_config_id: int = -1,
    messages: list[ChatMessage] | None = None,
    attachments: list[ChatAttachment] | None = None,
) -> AsyncGenerator[str, None]:
    """
    Stream chat responses from the new SurfSense deep agent.

    This uses the Vercel AI SDK Data Stream Protocol (SSE format) for streaming.
    The chat_id is used as LangGraph's thread_id for memory/checkpointing.
    Message history can be passed from the frontend for context.

    Args:
        user_query: The user's query
        user_id: The user's ID (can be UUID object or string)
        search_space_id: The search space ID
        chat_id: The chat ID (used as LangGraph thread_id for memory)
        session: The database session
        llm_config_id: The LLM configuration ID (default: -1 for first global config)
        messages: Optional chat history from frontend (list of ChatMessage)

    Yields:
        str: SSE formatted response strings
    """
    streaming_service = VercelStreamingService()

    # Convert UUID to string if needed
    str(user_id) if isinstance(user_id, UUID) else user_id

    # Track the current text block for streaming (defined early for exception handling)
    current_text_id: str | None = None

    try:
        # Load LLM config
        llm_config = load_llm_config_from_yaml(llm_config_id=llm_config_id)
        if not llm_config:
            yield streaming_service.format_error(
                f"Failed to load LLM config with id {llm_config_id}"
            )
            yield streaming_service.format_done()
            return

        # Create ChatLiteLLM instance
        llm = create_chat_litellm_from_config(llm_config)
        if not llm:
            yield streaming_service.format_error("Failed to create LLM instance")
            yield streaming_service.format_done()
            return

        # Create connector service
        connector_service = ConnectorService(session, search_space_id=search_space_id)

        # Get the PostgreSQL checkpointer for persistent conversation memory
        checkpointer = await get_checkpointer()

        # Create the deep agent with checkpointer with podcast capability
        agent = create_surfsense_deep_agent(
            llm=llm,
            search_space_id=search_space_id,
            db_session=session,
            connector_service=connector_service,
            checkpointer=checkpointer,
            user_id=str(user_id),
            enable_podcast=True,
        )

        # Build input with message history from frontend
        langchain_messages = []

        # Format the user query with attachment context if any
        final_query = user_query
        if attachments:
            attachment_context = format_attachments_as_context(attachments)
            final_query = (
                f"{attachment_context}\n\n<user_query>{user_query}</user_query>"
            )

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

        # Configure LangGraph with thread_id for memory
        config = {
            "configurable": {
                "thread_id": str(chat_id),
            }
        }

        # Start the message stream
        yield streaming_service.format_message_start()
        yield streaming_service.format_start_step()

        # Reset text tracking for this stream
        accumulated_text = ""

        # Track thinking steps for chain-of-thought display
        thinking_step_counter = 0
        # Map run_id -> step_id for tool calls so we can update them on completion
        tool_step_ids: dict[str, str] = {}
        # Track the last active step so we can mark it complete at the end
        last_active_step_id: str | None = None
        last_active_step_title: str = ""
        last_active_step_items: list[str] = []
        # Track which steps have been completed to avoid duplicate completions
        completed_step_ids: set[str] = set()
        # Track if we just finished a tool (text flows silently after tools)
        just_finished_tool: bool = False

        def next_thinking_step_id() -> str:
            nonlocal thinking_step_counter
            thinking_step_counter += 1
            return f"thinking-{thinking_step_counter}"

        def complete_current_step() -> str | None:
            """Complete the current active step and return the completion event, if any."""
            nonlocal last_active_step_id, last_active_step_title, last_active_step_items
            if last_active_step_id and last_active_step_id not in completed_step_ids:
                completed_step_ids.add(last_active_step_id)
                return streaming_service.format_thinking_step(
                    step_id=last_active_step_id,
                    title=last_active_step_title,
                    status="completed",
                    items=last_active_step_items if last_active_step_items else None,
                )
            return None

        # Initial thinking step - analyzing the request
        analyze_step_id = next_thinking_step_id()
        last_active_step_id = analyze_step_id
        last_active_step_title = "Understanding your request"
        last_active_step_items = [f"Processing: {user_query[:80]}{'...' if len(user_query) > 80 else ''}"]
        yield streaming_service.format_thinking_step(
            step_id=analyze_step_id,
            title="Understanding your request",
            status="in_progress",
            items=last_active_step_items,
        )

        # Stream the agent response with thread config for memory
        async for event in agent.astream_events(
            input_state, config=config, version="v2"
        ):
            event_type = event.get("event", "")

            # Handle chat model stream events (text streaming)
            if event_type == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content"):
                    content = chunk.content
                    if content and isinstance(content, str):
                        # Start a new text block if needed
                        if current_text_id is None:
                            # Complete any previous step
                            completion_event = complete_current_step()
                            if completion_event:
                                yield completion_event

                            if just_finished_tool:
                                # We just finished a tool - don't create a step here,
                                # text will flow silently after tools.
                                # Clear the active step tracking.
                                last_active_step_id = None
                                last_active_step_title = ""
                                last_active_step_items = []
                                just_finished_tool = False
                            else:
                                # Normal text generation (not after a tool)
                                gen_step_id = next_thinking_step_id()
                                last_active_step_id = gen_step_id
                                last_active_step_title = "Generating response"
                                last_active_step_items = []
                                yield streaming_service.format_thinking_step(
                                    step_id=gen_step_id,
                                    title="Generating response",
                                    status="in_progress",
                                )

                            current_text_id = streaming_service.generate_text_id()
                            yield streaming_service.format_text_start(current_text_id)

                        # Stream the text delta
                        yield streaming_service.format_text_delta(
                            current_text_id, content
                        )
                        accumulated_text += content

            # Handle tool calls
            elif event_type == "on_tool_start":
                tool_name = event.get("name", "unknown_tool")
                run_id = event.get("run_id", "")
                tool_input = event.get("data", {}).get("input", {})

                # End current text block if any
                if current_text_id is not None:
                    yield streaming_service.format_text_end(current_text_id)
                    current_text_id = None

                # Complete any previous step EXCEPT "Synthesizing response"
                # (we want to reuse the Synthesizing step after tools complete)
                if last_active_step_title != "Synthesizing response":
                    completion_event = complete_current_step()
                    if completion_event:
                        yield completion_event

                # Reset the just_finished_tool flag since we're starting a new tool
                just_finished_tool = False

                # Create thinking step for the tool call and store it for later update
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
                    last_active_step_items = [f"Query: {query[:100]}{'...' if len(query) > 100 else ''}"]
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
                    last_active_step_items = [f"URL: {url[:80]}{'...' if len(url) > 80 else ''}"]
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
                        tool_input.get("title", "")
                        if isinstance(tool_input, dict)
                        else ""
                    )
                    last_active_step_title = "Displaying image"
                    last_active_step_items = [
                        f"Image: {title[:50] if title else src[:50]}{'...' if len(title or src) > 50 else ''}"
                    ]
                    yield streaming_service.format_thinking_step(
                        step_id=tool_step_id,
                        title="Displaying image",
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
                    last_active_step_items = [f"URL: {url[:80]}{'...' if len(url) > 80 else ''}"]
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
                    # Get content length for context
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
                else:
                    last_active_step_title = f"Using {tool_name.replace('_', ' ')}"
                    last_active_step_items = []
                    yield streaming_service.format_thinking_step(
                        step_id=tool_step_id,
                        title=last_active_step_title,
                        status="in_progress",
                    )

                # Stream tool info
                tool_call_id = (
                    f"call_{run_id[:32]}"
                    if run_id
                    else streaming_service.generate_tool_call_id()
                )
                yield streaming_service.format_tool_input_start(tool_call_id, tool_name)
                yield streaming_service.format_tool_input_available(
                    tool_call_id,
                    tool_name,
                    tool_input
                    if isinstance(tool_input, dict)
                    else {"input": tool_input},
                )

                # Send terminal info about the tool call
                if tool_name == "search_knowledge_base":
                    query = (
                        tool_input.get("query", "")
                        if isinstance(tool_input, dict)
                        else str(tool_input)
                    )
                    yield streaming_service.format_terminal_info(
                        f"Searching knowledge base: {query[:100]}{'...' if len(query) > 100 else ''}",
                        "info",
                    )
                elif tool_name == "link_preview":
                    url = (
                        tool_input.get("url", "")
                        if isinstance(tool_input, dict)
                        else str(tool_input)
                    )
                    yield streaming_service.format_terminal_info(
                        f"Fetching link preview: {url[:80]}{'...' if len(url) > 80 else ''}",
                        "info",
                    )
                elif tool_name == "display_image":
                    src = (
                        tool_input.get("src", "")
                        if isinstance(tool_input, dict)
                        else str(tool_input)
                    )
                    yield streaming_service.format_terminal_info(
                        f"Displaying image: {src[:60]}{'...' if len(src) > 60 else ''}",
                        "info",
                    )
                elif tool_name == "scrape_webpage":
                    url = (
                        tool_input.get("url", "")
                        if isinstance(tool_input, dict)
                        else str(tool_input)
                    )
                    yield streaming_service.format_terminal_info(
                        f"Scraping webpage: {url[:70]}{'...' if len(url) > 70 else ''}",
                        "info",
                    )
                elif tool_name == "generate_podcast":
                    title = (
                        tool_input.get("podcast_title", "SurfSense Podcast")
                        if isinstance(tool_input, dict)
                        else "SurfSense Podcast"
                    )
                    yield streaming_service.format_terminal_info(
                        f"Generating podcast: {title}",
                        "info",
                    )

            elif event_type == "on_tool_end":
                run_id = event.get("run_id", "")
                tool_name = event.get("name", "unknown_tool")
                raw_output = event.get("data", {}).get("output", "")

                # Extract content from ToolMessage if needed
                # LangGraph may return a ToolMessage object instead of raw dict
                if hasattr(raw_output, "content"):
                    # It's a ToolMessage object - extract the content
                    content = raw_output.content
                    # If content is a string that looks like JSON, try to parse it
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
                    tool_output = {
                        "result": str(raw_output) if raw_output else "completed"
                    }

                tool_call_id = f"call_{run_id[:32]}" if run_id else "call_unknown"

                # Get the original tool step ID to update it (not create a new one)
                original_step_id = tool_step_ids.get(run_id, f"thinking-unknown-{run_id[:8]}")

                # Mark the tool thinking step as completed using the SAME step ID
                # Also add to completed set so we don't try to complete it again
                completed_step_ids.add(original_step_id)
                if tool_name == "search_knowledge_base":
                    # Get result count if available
                    result_info = "Search completed"
                    if isinstance(tool_output, dict):
                        result_len = tool_output.get("result_length", 0)
                        if result_len > 0:
                            result_info = f"Found relevant information ({result_len} chars)"
                    # Include original query in completed items
                    completed_items = [*last_active_step_items, result_info]
                    yield streaming_service.format_thinking_step(
                        step_id=original_step_id,
                        title="Searching knowledge base",
                        status="completed",
                        items=completed_items,
                    )
                elif tool_name == "link_preview":
                    # Build completion items based on link preview result
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
                    # Build completion items for image display
                    if isinstance(tool_output, dict):
                        title = tool_output.get("title", "")
                        alt = tool_output.get("alt", "Image")
                        display_name = title or alt
                        completed_items = [
                            *last_active_step_items,
                            f"Showing: {display_name[:50]}{'...' if len(display_name) > 50 else ''}",
                        ]
                    else:
                        completed_items = [*last_active_step_items, "Image displayed"]
                    yield streaming_service.format_thinking_step(
                        step_id=original_step_id,
                        title="Displaying image",
                        status="completed",
                        items=completed_items,
                    )
                elif tool_name == "scrape_webpage":
                    # Build completion items for webpage scraping
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
                    # Build detailed completion items based on podcast status
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
                else:
                    yield streaming_service.format_thinking_step(
                        step_id=original_step_id,
                        title=f"Using {tool_name.replace('_', ' ')}",
                        status="completed",
                        items=last_active_step_items,
                    )

                # Mark that we just finished a tool - "Synthesizing response" will be created
                # when text actually starts flowing (not immediately)
                just_finished_tool = True
                # Clear the active step since the tool is done
                last_active_step_id = None
                last_active_step_title = ""
                last_active_step_items = []

                # Handle different tool outputs
                if tool_name == "generate_podcast":
                    # Stream the full podcast result so frontend can render the audio player
                    yield streaming_service.format_tool_output_available(
                        tool_call_id,
                        tool_output
                        if isinstance(tool_output, dict)
                        else {"result": tool_output},
                    )
                    # Send appropriate terminal message based on status
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
                    # Stream the full link preview result so frontend can render the MediaCard
                    yield streaming_service.format_tool_output_available(
                        tool_call_id,
                        tool_output
                        if isinstance(tool_output, dict)
                        else {"result": tool_output},
                    )
                    # Send appropriate terminal message
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
                    # Stream the full image result so frontend can render the Image component
                    yield streaming_service.format_tool_output_available(
                        tool_call_id,
                        tool_output
                        if isinstance(tool_output, dict)
                        else {"result": tool_output},
                    )
                    # Send terminal message
                    if isinstance(tool_output, dict):
                        title = tool_output.get("title") or tool_output.get("alt", "Image")
                        yield streaming_service.format_terminal_info(
                            f"Image displayed: {title[:40]}{'...' if len(title) > 40 else ''}",
                            "success",
                        )
                elif tool_name == "scrape_webpage":
                    # Stream the scrape result so frontend can render the Article component
                    # Note: We send metadata for display, but content goes to LLM for processing
                    if isinstance(tool_output, dict):
                        # Create a display-friendly output (without full content for the card)
                        display_output = {
                            k: v for k, v in tool_output.items() if k != "content"
                        }
                        # But keep a truncated content preview
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
                    # Send terminal message
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
                    # Don't stream the full output for search (can be very large), just acknowledge
                    yield streaming_service.format_tool_output_available(
                        tool_call_id,
                        {"status": "completed", "result_length": len(str(tool_output))},
                    )
                    yield streaming_service.format_terminal_info(
                        "Knowledge base search completed", "success"
                    )
                else:
                    # Default handling for other tools
                    yield streaming_service.format_tool_output_available(
                        tool_call_id,
                        {"status": "completed", "result_length": len(str(tool_output))},
                    )
                    yield streaming_service.format_terminal_info(
                        f"Tool {tool_name} completed", "success"
                    )

            # Handle chain/agent end to close any open text blocks
            elif event_type in ("on_chain_end", "on_agent_end"):
                if current_text_id is not None:
                    yield streaming_service.format_text_end(current_text_id)
                    current_text_id = None

        # Ensure text block is closed
        if current_text_id is not None:
            yield streaming_service.format_text_end(current_text_id)

        # Mark the last active thinking step as completed using the same title
        completion_event = complete_current_step()
        if completion_event:
            yield completion_event

        # Finish the step and message
        yield streaming_service.format_finish_step()
        yield streaming_service.format_finish()
        yield streaming_service.format_done()

    except Exception as e:
        # Handle any errors
        error_message = f"Error during chat: {e!s}"
        print(f"[stream_new_chat] {error_message}")

        # Close any open text block
        if current_text_id is not None:
            yield streaming_service.format_text_end(current_text_id)

        yield streaming_service.format_error(error_message)
        yield streaming_service.format_finish_step()
        yield streaming_service.format_finish()
        yield streaming_service.format_done()
