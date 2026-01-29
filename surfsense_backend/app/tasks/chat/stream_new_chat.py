"""
Streaming task for the new SurfSense deep agent chat.

This module streams responses from the deep agent using the Vercel AI SDK
Data Stream Protocol (SSE format).

Supports loading LLM configurations from:
- YAML files (negative IDs for global configs)
- NewLLMConfig database table (positive IDs for user-created configs with prompt settings)
"""

import json
from collections.abc import AsyncGenerator
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
from app.db import Document, SurfsenseDocsDocument
from app.schemas.new_chat import ChatAttachment
from app.services.chat_session_state_service import (
    clear_ai_responding,
    set_ai_responding,
)
from app.services.connector_service import ConnectorService
from app.services.new_streaming_service import VercelStreamingService
from app.utils.content_utils import bootstrap_history_from_db


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


async def stream_new_chat(
    user_query: str,
    search_space_id: int,
    chat_id: int,
    session: AsyncSession,
    user_id: str | None = None,
    llm_config_id: int = -1,
    attachments: list[ChatAttachment] | None = None,
    mentioned_document_ids: list[int] | None = None,
    mentioned_surfsense_doc_ids: list[int] | None = None,
    checkpoint_id: str | None = None,
    needs_history_bootstrap: bool = False,
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
        attachments: Optional attachments with extracted content
        needs_history_bootstrap: If True, load message history from DB (for cloned chats)
        mentioned_document_ids: Optional list of document IDs mentioned with @ in the chat
        mentioned_surfsense_doc_ids: Optional list of SurfSense doc IDs mentioned with @ in the chat
        checkpoint_id: Optional checkpoint ID to rewind/fork from (for edit/reload operations)

    Yields:
        str: SSE formatted response strings
    """
    streaming_service = VercelStreamingService()

    # Track the current text block for streaming (defined early for exception handling)
    current_text_id: str | None = None

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

        # Create the deep agent with checkpointer and configurable prompts
        agent = await create_surfsense_deep_agent(
            llm=llm,
            search_space_id=search_space_id,
            db_session=session,
            connector_service=connector_service,
            checkpointer=checkpointer,
            user_id=user_id,  # Pass user ID for memory tools
            thread_id=chat_id,  # Pass chat ID for podcast association
            agent_config=agent_config,  # Pass prompt configuration
            firecrawl_api_key=firecrawl_api_key,  # Pass Firecrawl API key if configured
        )

        # Build input with message history
        langchain_messages = []

        # Bootstrap history for cloned chats (no LangGraph checkpoint exists yet)
        if needs_history_bootstrap:
            langchain_messages = await bootstrap_history_from_db(session, chat_id)

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

        # Format the user query with context (attachments + mentioned documents + surfsense docs)
        final_query = user_query
        context_parts = []

        if attachments:
            context_parts.append(format_attachments_as_context(attachments))

        if mentioned_documents:
            context_parts.append(
                format_mentioned_documents_as_context(mentioned_documents)
            )

        if mentioned_surfsense_docs:
            context_parts.append(
                format_mentioned_surfsense_docs_as_context(mentioned_surfsense_docs)
            )

        if context_parts:
            context = "\n\n".join(context_parts)
            final_query = f"{context}\n\n<user_query>{user_query}</user_query>"

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
        # Track write_todos calls to show "Creating plan" vs "Updating plan"
        # Disabled for now
        # write_todos_call_count: int = 0

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

        # Determine step title and action verb based on context
        if attachments and (mentioned_documents or mentioned_surfsense_docs):
            last_active_step_title = "Analyzing your content"
            action_verb = "Reading"
        elif attachments:
            last_active_step_title = "Reading your content"
            action_verb = "Reading"
        elif mentioned_documents or mentioned_surfsense_docs:
            last_active_step_title = "Analyzing referenced content"
            action_verb = "Analyzing"
        else:
            last_active_step_title = "Understanding your request"
            action_verb = "Processing"

        # Build the message with inline context about attachments/documents
        processing_parts = []

        # Add the user query
        query_text = user_query[:80] + ("..." if len(user_query) > 80 else "")
        processing_parts.append(query_text)

        # Add file attachment names inline
        if attachments:
            attachment_names = []
            for attachment in attachments:
                name = attachment.name
                if len(name) > 30:
                    name = name[:27] + "..."
                attachment_names.append(name)
            if len(attachment_names) == 1:
                processing_parts.append(f"[{attachment_names[0]}]")
            else:
                processing_parts.append(f"[{len(attachment_names)} files]")

        # Add mentioned document names inline
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

        # Add mentioned SurfSense docs inline
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

        last_active_step_items = [f"{action_verb}: {' '.join(processing_parts)}"]

        yield streaming_service.format_thinking_step(
            step_id=analyze_step_id,
            title=last_active_step_title,
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
                                # Clear the active step tracking - text flows without a dedicated step
                                last_active_step_id = None
                                last_active_step_title = ""
                                last_active_step_items = []
                                just_finished_tool = False

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
                        tool_input.get("title", "")
                        if isinstance(tool_input, dict)
                        else ""
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
                # elif tool_name == "write_todos":  # Disabled for now
                #     # Track write_todos calls for better messaging
                #     write_todos_call_count += 1
                #     todos = (
                #         tool_input.get("todos", [])
                #         if isinstance(tool_input, dict)
                #         else []
                #     )
                #     todo_count = len(todos) if isinstance(todos, list) else 0

                #     if write_todos_call_count == 1:
                #         # First call - creating the plan
                #         last_active_step_title = "Creating plan"
                #         last_active_step_items = [f"Defining {todo_count} tasks..."]
                #     else:
                #         # Subsequent calls - updating the plan
                #         # Try to provide context about what's being updated
                #         in_progress_count = (
                #             sum(
                #                 1
                #                 for t in todos
                #                 if isinstance(t, dict)
                #                 and t.get("status") == "in_progress"
                #             )
                #             if isinstance(todos, list)
                #             else 0
                #         )
                #         completed_count = (
                #             sum(
                #                 1
                #                 for t in todos
                #                 if isinstance(t, dict)
                #                 and t.get("status") == "completed"
                #             )
                #             if isinstance(todos, list)
                #             else 0
                #         )

                #         last_active_step_title = "Updating progress"
                #         last_active_step_items = (
                #             [
                #                 f"Progress: {completed_count}/{todo_count} completed",
                #                 f"In progress: {in_progress_count} tasks",
                #             ]
                #             if completed_count > 0
                #             else [f"Working on {todo_count} tasks"]
                #         )

                #     yield streaming_service.format_thinking_step(
                #         step_id=tool_step_id,
                #         title=last_active_step_title,
                #         status="in_progress",
                #         items=last_active_step_items,
                #     )
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
                # elif tool_name == "ls":
                #     last_active_step_title = "Exploring files"
                #     last_active_step_items = []
                #     yield streaming_service.format_thinking_step(
                #         step_id=tool_step_id,
                #         title="Exploring files",
                #         status="in_progress",
                #         items=None,
                #     )
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

            elif event_type == "on_tool_end":
                run_id = event.get("run_id", "")
                tool_name = event.get("name", "unknown_tool")
                raw_output = event.get("data", {}).get("output", "")

                # Handle deepagents' write_todos Command object specially
                # Disabled for now
                # if tool_name == "write_todos" and hasattr(raw_output, "update"):
                #     # deepagents returns a Command object - extract todos directly
                #     tool_output = extract_todos_from_deepagents(raw_output)
                # elif hasattr(raw_output, "content"):
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
                original_step_id = tool_step_ids.get(
                    run_id, f"thinking-unknown-{run_id[:8]}"
                )

                # Mark the tool thinking step as completed using the SAME step ID
                # Also add to completed set so we don't try to complete it again
                completed_step_ids.add(original_step_id)
                if tool_name == "search_knowledge_base":
                    # Get result count if available
                    result_info = "Search completed"
                    if isinstance(tool_output, dict):
                        result_len = tool_output.get("result_length", 0)
                        if result_len > 0:
                            result_info = (
                                f"Found relevant information ({result_len} chars)"
                            )
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
                    # Build completion items for image analysis
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
                # elif tool_name == "write_todos":  # Disabled for now
                #     # Build completion items for planning/updating
                #     if isinstance(tool_output, dict):
                #         todos = tool_output.get("todos", [])
                #         todo_count = len(todos) if isinstance(todos, list) else 0
                #         completed_count = (
                #             sum(
                #                 1
                #                 for t in todos
                #                 if isinstance(t, dict)
                #                 and t.get("status") == "completed"
                #             )
                #             if isinstance(todos, list)
                #             else 0
                #         )
                #         in_progress_count = (
                #             sum(
                #                 1
                #                 for t in todos
                #                 if isinstance(t, dict)
                #                 and t.get("status") == "in_progress"
                #             )
                #             if isinstance(todos, list)
                #             else 0
                #         )

                #         # Use context-aware completion message
                #         if last_active_step_title == "Creating plan":
                #             completed_items = [f"Created {todo_count} tasks"]
                #         else:
                #             # Updating progress - show stats
                #             completed_items = [
                #                 f"Progress: {completed_count}/{todo_count} completed",
                #             ]
                #             if in_progress_count > 0:
                #                 # Find the currently in-progress task name
                #                 in_progress_task = next(
                #                     (
                #                         t.get("content", "")[:40]
                #                         for t in todos
                #                         if isinstance(t, dict)
                #                         and t.get("status") == "in_progress"
                #                     ),
                #                     None,
                #                 )
                #                 if in_progress_task:
                #                     completed_items.append(
                #                         f"Current: {in_progress_task}..."
                #                     )
                #     else:
                #         completed_items = ["Plan updated"]
                #     yield streaming_service.format_thinking_step(
                #         step_id=original_step_id,
                #         title=last_active_step_title,
                #         status="completed",
                #         items=completed_items,
                #     )
                elif tool_name == "ls":
                    # Build completion items showing file names found
                    if isinstance(tool_output, dict):
                        result = tool_output.get("result", "")
                    elif isinstance(tool_output, str):
                        result = tool_output
                    else:
                        result = str(tool_output) if tool_output else ""

                    # Parse file paths and extract just the file names
                    file_names = []
                    if result:
                        # The ls tool returns paths, extract just the file/folder names
                        for line in result.strip().split("\n"):
                            line = line.strip()
                            if line:
                                # Get just the filename from the path
                                name = line.rstrip("/").split("/")[-1]
                                if name and len(name) <= 40:
                                    file_names.append(name)
                                elif name:
                                    file_names.append(name[:37] + "...")

                    # Build display items - wrap file names in brackets for icon rendering
                    if file_names:
                        if len(file_names) <= 5:
                            # Wrap each file name in brackets for styled tile rendering
                            completed_items = [f"[{name}]" for name in file_names]
                        else:
                            # Show first few with brackets and count
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
                        title = tool_output.get("title") or tool_output.get(
                            "alt", "Image"
                        )
                        yield streaming_service.format_terminal_info(
                            f"Image analyzed: {title[:40]}{'...' if len(title) > 40 else ''}",
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
                # elif tool_name == "write_todos":  # Disabled for now
                #     # Stream the full write_todos result so frontend can render the Plan component
                #     yield streaming_service.format_tool_output_available(
                #         tool_call_id,
                #         tool_output
                #         if isinstance(tool_output, dict)
                #         else {"result": tool_output},
                #     )
                #     # Send terminal message with plan info
                #     if isinstance(tool_output, dict):
                #         todos = tool_output.get("todos", [])
                #         todo_count = len(todos) if isinstance(todos, list) else 0
                #         yield streaming_service.format_terminal_info(
                #             f"Plan created ({todo_count} tasks)",
                #             "success",
                #         )
                #     else:
                #         yield streaming_service.format_terminal_info(
                #             "Plan created",
                #             "success",
                #         )
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
        import traceback

        error_message = f"Error during chat: {e!s}"
        print(f"[stream_new_chat] {error_message}")
        print(f"[stream_new_chat] Exception type: {type(e).__name__}")
        print(f"[stream_new_chat] Traceback:\n{traceback.format_exc()}")

        # Close any open text block
        if current_text_id is not None:
            yield streaming_service.format_text_end(current_text_id)

        yield streaming_service.format_error(error_message)
        yield streaming_service.format_finish_step()
        yield streaming_service.format_finish()
        yield streaming_service.format_done()

    finally:
        # Clear AI responding state for live collaboration
        await clear_ai_responding(session, chat_id)
