from typing import Any, AsyncGenerator, List, Union
from uuid import UUID

from app.agents.researcher.graph import graph as researcher_graph
from app.agents.researcher.state import State
from app.services.streaming_service import StreamingService
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.researcher.configuration import SearchMode


async def stream_connector_search_results(
    user_query: str, 
    user_id: Union[str, UUID], 
    search_space_id: int, 
    session: AsyncSession, 
    research_mode: str, 
    selected_connectors: List[str],
    langchain_chat_history: List[Any],
    search_mode_str: str,
    document_ids_to_add_in_context: List[int]
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
    
    if research_mode == "REPORT_GENERAL":
        NUM_SECTIONS = 1
    elif research_mode == "REPORT_DEEP":
        NUM_SECTIONS = 3
    elif research_mode == "REPORT_DEEPER":
        NUM_SECTIONS = 6
    else:
        # Default fallback
        NUM_SECTIONS = 1
    
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
            "num_sections": NUM_SECTIONS,
            "connectors_to_search": selected_connectors,
            "user_id": user_id_str,
            "search_space_id": search_space_id,
            "search_mode": search_mode,
            "research_mode": research_mode,
            "document_ids_to_add_in_context": document_ids_to_add_in_context
        }
    }
    # Initialize state with database session and streaming service
    initial_state = State(
        db_session=session,
        streaming_service=streaming_service,
        chat_history=langchain_chat_history
    )
    
    # Run the graph directly
    print("\nRunning the complete researcher workflow...")
    
    # Use streaming with config parameter
    async for chunk in researcher_graph.astream(
        initial_state,
        config=config,
        stream_mode="custom",
    ):
        # If the chunk contains a 'yeild_value' key, print its value
        # Note: there's a typo in 'yeild_value' in the code, but we need to match it
        if isinstance(chunk, dict) and 'yeild_value' in chunk:
            yield chunk['yeild_value']
    
    yield streaming_service.format_completion()