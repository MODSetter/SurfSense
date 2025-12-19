"""
Streaming task for the new SurfSense deep agent chat.

This module streams responses from the deep agent using the Vercel AI SDK
Data Stream Protocol (SSE format).
"""

from collections.abc import AsyncGenerator
from uuid import UUID

from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.chat_deepagent import (
    create_chat_litellm_from_config,
    create_surfsense_deep_agent,
    load_llm_config_from_yaml,
)
from app.services.connector_service import ConnectorService
from app.services.new_streaming_service import VercelStreamingService


async def stream_new_chat(
    user_query: str,
    user_id: str | UUID,
    search_space_id: int,
    chat_id: int,
    session: AsyncSession,
    llm_config_id: int = -1,
) -> AsyncGenerator[str, None]:
    """
    Stream chat responses from the new SurfSense deep agent.

    This uses the Vercel AI SDK Data Stream Protocol (SSE format) for streaming.
    The chat_id is used as LangGraph's thread_id for memory/checkpointing,
    so chat history is automatically managed by LangGraph.

    Args:
        user_query: The user's query
        user_id: The user's ID (can be UUID object or string)
        search_space_id: The search space ID
        chat_id: The chat ID (used as LangGraph thread_id for memory)
        session: The database session
        llm_config_id: The LLM configuration ID (default: -1 for first global config)

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

        # Create the deep agent
        agent = create_surfsense_deep_agent(
            llm=llm,
            search_space_id=search_space_id,
            db_session=session,
            connector_service=connector_service,
        )

        # Build input with just the current user query
        # Chat history is managed by LangGraph via thread_id
        input_state = {
            "messages": [HumanMessage(content=user_query)],
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

            elif event_type == "on_tool_end":
                run_id = event.get("run_id", "")
                tool_output = event.get("data", {}).get("output", "")

                tool_call_id = f"call_{run_id[:32]}" if run_id else "call_unknown"

                # Don't stream the full output (can be very large), just acknowledge
                yield streaming_service.format_tool_output_available(
                    tool_call_id,
                    {"status": "completed", "result_length": len(str(tool_output))},
                )

                yield streaming_service.format_terminal_info(
                    "Knowledge base search completed", "success"
                )

            # Handle chain/agent end to close any open text blocks
            elif event_type in ("on_chain_end", "on_agent_end"):
                if current_text_id is not None:
                    yield streaming_service.format_text_end(current_text_id)
                    current_text_id = None

        # Ensure text block is closed
        if current_text_id is not None:
            yield streaming_service.format_text_end(current_text_id)

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
