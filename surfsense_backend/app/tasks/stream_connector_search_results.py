from collections.abc import AsyncGenerator
import asyncio
import json
import logging
import os
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.researcher.configuration import SearchMode
from app.agents.researcher.graph import graph as researcher_graph
from app.agents.researcher.state import State
from app.services.streaming_service import StreamingService
from app.services.grammar_check import auto_grammar_check

logger = logging.getLogger(__name__)


async def stream_connector_search_results(
    user_query: str,
    user_id: str | UUID,
    search_space_id: int,
    session: AsyncSession,
    research_mode: str,
    selected_connectors: list[str],
    langchain_chat_history: list[Any],
    search_mode_str: str,
    document_ids_to_add_in_context: list[int],
    language: str | None = None,
    top_k: int = 10,
) -> AsyncGenerator[str, None]:
    """
    Stream connector search results to the client

    Args:
        user_query: The user's query
        user_id: The user's ID (can be UUID object or string)
        search_space_id: The search space ID
        session: The database session
        research_mode: The research mode
        selected_connectors: List of selected connectors

    Yields:
        str: Formatted response strings
    """
    streaming_service = StreamingService()

    try:
        # Convert UUID to string if needed
        user_id_str = str(user_id) if isinstance(user_id, UUID) else user_id

        if search_mode_str == "CHUNKS":
            search_mode = SearchMode.CHUNKS
        elif search_mode_str == "DOCUMENTS":
            search_mode = SearchMode.DOCUMENTS

        # Sample configuration
        config = {
            "configurable": {
                "user_query": user_query,
                "connectors_to_search": selected_connectors,
                "user_id": user_id_str,
                "search_space_id": search_space_id,
                "search_mode": search_mode,
                "document_ids_to_add_in_context": document_ids_to_add_in_context,
                "language": language,  # Add language to the configuration
                "top_k": top_k,  # Add top_k to the configuration
            }
        }
        # print(f"Researcher configuration: {config['configurable']}")  # Debug print
        # Initialize state with database session and streaming service
        initial_state = State(
            db_session=session,
            streaming_service=streaming_service,
            chat_history=langchain_chat_history,
        )

        # Run the graph directly
        print("\nRunning the complete researcher workflow...")

        # Collect response text for grammar checking
        response_chunks = []

        # Add timeout for the entire streaming process (2 minutes)
        try:
            async with asyncio.timeout(120):  # 2 minute timeout
                # Use streaming with config parameter
                async for chunk in researcher_graph.astream(
                    initial_state,
                    config=config,
                    stream_mode="custom",
                ):
                    if isinstance(chunk, dict) and "yield_value" in chunk:
                        # Collect text chunks for grammar checking
                        yield_value = chunk["yield_value"]
                        yield yield_value

                        # Try to extract text from the chunk
                        try:
                            # Parse the chunk to extract text
                            # Format is like "0:"text"\n" for text chunks
                            if yield_value.startswith("0:"):
                                text_json = yield_value[2:].strip()
                                if text_json:
                                    text = json.loads(text_json)
                                    response_chunks.append(text)
                        except Exception:
                            # Ignore parsing errors, not all chunks contain text
                            pass
        except asyncio.TimeoutError:
            logger.error("Stream generation timed out after 2 minutes")
            yield streaming_service.format_error("Response generation timed out. Please try again with a simpler query.")

        # Run grammar check asynchronously with timeout
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        try:
            # Combine response chunks
            full_response = "".join(response_chunks)

            if full_response.strip():
                # Run grammar check with timeout
                grammar_result = await asyncio.wait_for(
                    auto_grammar_check(user_query, full_response, ollama_url),
                    timeout=8.0
                )

                # If grammar check returned a result, stream it
                if grammar_result:
                    logger.info(f"Grammar check completed for language: {grammar_result.get('language_code', 'unknown')}")
                    yield streaming_service.format_grammar_check_delta(grammar_result)

        except asyncio.TimeoutError:
            logger.warning("Grammar check timed out")
        except Exception as e:
            logger.warning(f"Grammar check failed: {e}")

    except Exception as e:
        logger.error(f"Stream error: {e}", exc_info=True)
        yield streaming_service.format_error(f"An error occurred while generating the response: {str(e)}")

    finally:
        # CRITICAL: Always send completion signal, even if there was an error
        yield streaming_service.format_completion()
        logger.info("Stream completed")
