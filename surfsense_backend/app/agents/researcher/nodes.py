from .configuration import Configuration
from langchain_core.runnables import RunnableConfig
from .state import State
from typing import Any, Dict, List
from app.config import config as app_config
from .prompts import get_answer_outline_system_prompt
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
import json
import asyncio
from .sub_section_writer.graph import graph as sub_section_writer_graph
from app.utils.connector_service import ConnectorService
from app.utils.reranker_service import RerankerService
from sqlalchemy.ext.asyncio import AsyncSession
import copy

class Section(BaseModel):
    """A section in the answer outline."""
    section_id: int = Field(..., description="The zero-based index of the section")
    section_title: str = Field(..., description="The title of the section")
    questions: List[str] = Field(..., description="Questions to research for this section")

class AnswerOutline(BaseModel):
    """The complete answer outline with all sections."""
    answer_outline: List[Section] = Field(..., description="List of sections in the answer outline")

async def write_answer_outline(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """
    Create a structured answer outline based on the user query.
    
    This node takes the user query and number of sections from the configuration and uses
    an LLM to generate a comprehensive outline with logical sections and research questions
    for each section.
    
    Returns:
        Dict containing the answer outline in the "answer_outline" key for state update.
    """
    
    # Get configuration from runnable config
    configuration = Configuration.from_runnable_config(config)
    user_query = configuration.user_query
    num_sections = configuration.num_sections
    
    # Initialize LLM
    llm = app_config.strategic_llm_instance
    
    # Create the human message content
    human_message_content = f"""
    Now Please create an answer outline for the following query:
    
    User Query: {user_query}
    Number of Sections: {num_sections}
    
    Remember to format your response as valid JSON exactly matching this structure:
    {{
      "answer_outline": [
        {{
          "section_id": 0,
          "section_title": "Section Title",
          "questions": [
            "Question 1 to research for this section",
            "Question 2 to research for this section"
          ]
        }}
      ]
    }}
    
    Your output MUST be valid JSON in exactly this format. Do not include any other text or explanation.
    """
    
    # Create messages for the LLM
    messages = [
        SystemMessage(content=get_answer_outline_system_prompt()),
        HumanMessage(content=human_message_content)
    ]
    
    # Call the LLM directly without using structured output
    response = await llm.ainvoke(messages)
    
    # Parse the JSON response manually
    try:
        # Extract JSON content from the response
        content = response.content
        
        # Find the JSON in the content (handle case where LLM might add additional text)
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = content[json_start:json_end]
            
            # Parse the JSON string
            parsed_data = json.loads(json_str)
            
            # Convert to Pydantic model
            answer_outline = AnswerOutline(**parsed_data)
            
            print(f"Successfully generated answer outline with {len(answer_outline.answer_outline)} sections")
            
            # Return state update
            return {"answer_outline": answer_outline}
        else:
            # If JSON structure not found, raise a clear error
            raise ValueError(f"Could not find valid JSON in LLM response. Raw response: {content}")
            
    except (json.JSONDecodeError, ValueError) as e:
        # Log the error and re-raise it
        print(f"Error parsing LLM response: {str(e)}")
        print(f"Raw response: {response.content}")
        raise

async def fetch_relevant_documents(
    research_questions: List[str],
    user_id: str,
    search_space_id: int,
    db_session: AsyncSession,
    connectors_to_search: List[str],
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Fetch relevant documents for research questions using the provided connectors.
    
    Args:
        section_title: The title of the section being researched
        research_questions: List of research questions to find documents for
        user_id: The user ID
        search_space_id: The search space ID
        db_session: The database session
        connectors_to_search: List of connectors to search
        top_k: Number of top results to retrieve per connector per question
        
    Returns:
        List of relevant documents
    """
    # Initialize services
    connector_service = ConnectorService(db_session)
    reranker_service = RerankerService.get_reranker_instance(app_config)

    all_raw_documents = []  # Store all raw documents before reranking
    
    for user_query in research_questions:
        # Use original research question as the query
        reformulated_query = user_query
        
        # Process each selected connector
        for connector in connectors_to_search:
            try:
                if connector == "YOUTUBE_VIDEO":
                    _, youtube_chunks = await connector_service.search_youtube(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k
                    )
                    all_raw_documents.extend(youtube_chunks)
                    
                elif connector == "EXTENSION":
                    _, extension_chunks = await connector_service.search_extension(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k
                    )
                    all_raw_documents.extend(extension_chunks)
                    
                elif connector == "CRAWLED_URL":
                    _, crawled_urls_chunks = await connector_service.search_crawled_urls(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k
                    )
                    all_raw_documents.extend(crawled_urls_chunks)
                    
                elif connector == "FILE":
                    _, files_chunks = await connector_service.search_files(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k
                    )
                    all_raw_documents.extend(files_chunks)
                    
                elif connector == "TAVILY_API":
                    _, tavily_chunks = await connector_service.search_tavily(
                        user_query=reformulated_query,
                        user_id=user_id,
                        top_k=top_k
                    )
                    all_raw_documents.extend(tavily_chunks)
                    
                elif connector == "SLACK_CONNECTOR":
                    _, slack_chunks = await connector_service.search_slack(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k
                    )
                    all_raw_documents.extend(slack_chunks)
                    
                elif connector == "NOTION_CONNECTOR":
                    _, notion_chunks = await connector_service.search_notion(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k
                    )
                    all_raw_documents.extend(notion_chunks)
            except Exception as e:
                print(f"Error searching connector {connector}: {str(e)}")
                # Continue with other connectors on error
                continue
    
    # Deduplicate documents based on chunk_id or content
    seen_chunk_ids = set()
    seen_content_hashes = set()
    deduplicated_docs = []
    
    for doc in all_raw_documents:
        chunk_id = doc.get("chunk_id")
        content = doc.get("content", "")
        content_hash = hash(content)
        
        # Skip if we've seen this chunk_id or content before
        if (chunk_id and chunk_id in seen_chunk_ids) or content_hash in seen_content_hashes:
            continue
            
        # Add to our tracking sets and keep this document
        if chunk_id:
            seen_chunk_ids.add(chunk_id)
        seen_content_hashes.add(content_hash)
        deduplicated_docs.append(doc)
    
    return deduplicated_docs

async def process_section(
    section_title: str, 
    user_id: str, 
    search_space_id: int, 
    session_maker,
    research_questions: List[str],
    connectors_to_search: List[str]
) -> str:
    """
    Process a single section by sending it to the sub_section_writer graph.
    
    Args:
        section_title: The title of the section
        user_id: The user ID
        search_space_id: The search space ID
        session_maker: Factory for creating new database sessions
        research_questions: List of research questions for this section
        connectors_to_search: List of connectors to search
        
    Returns:
        The written section content
    """
    try:
        # Create a new database session for this section
        async with session_maker() as db_session:
            # Fetch relevant documents using all research questions for this section
            relevant_documents = await fetch_relevant_documents(
                research_questions=research_questions,
                user_id=user_id,
                search_space_id=search_space_id,
                db_session=db_session,
                connectors_to_search=connectors_to_search
            )
            
            # Fallback if no documents found
            if not relevant_documents:
                print(f"No relevant documents found for section: {section_title}")
                relevant_documents = [
                    {"content": f"No specific information was found for: {question}"}
                    for question in research_questions
                ]
            
            # Call the sub_section_writer graph with the appropriate config
            config = {
                "configurable": {
                    "sub_section_title": section_title,
                    "relevant_documents": relevant_documents,
                    "user_id": user_id,
                    "search_space_id": search_space_id
                }
            }
            
            # Create the initial state with db_session
            state = {"db_session": db_session}
            
            # Invoke the sub-section writer graph
            print(f"Invoking sub_section_writer for: {section_title}")
            result = await sub_section_writer_graph.ainvoke(state, config)
            
            # Return the final answer from the sub_section_writer
            final_answer = result.get("final_answer", "No content was generated for this section.")
            return final_answer
    except Exception as e:
        print(f"Error processing section '{section_title}': {str(e)}")
        return f"Error processing section: {section_title}. Details: {str(e)}"

async def process_sections(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """
    Process all sections in parallel and combine the results.
    
    This node takes the answer outline from the previous step, fetches relevant documents 
    for all questions across all sections once, and then processes each section in parallel 
    using the sub_section_writer graph with the shared document pool.
    
    Returns:
        Dict containing the final written report in the "final_written_report" key.
    """
    # Get configuration and answer outline from state
    configuration = Configuration.from_runnable_config(config)
    answer_outline = state.answer_outline
    
    print(f"Processing sections from outline: {answer_outline is not None}")
    
    if not answer_outline:
        return {
            "final_written_report": "No answer outline was provided. Cannot generate final report."
        }
    
    # Create session maker from the engine or directly use the session
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    # Use the engine if available, otherwise create a new session for each task
    if state.engine:
        session_maker = sessionmaker(
            state.engine, class_=AsyncSession, expire_on_commit=False
        )
    else:
        # Fallback to using the same session (less optimal but will work)
        print("Warning: No engine available. Using same session for all tasks.")
        # Create a mock session maker that returns the same session
        async def mock_session_maker():
            class ContextManager:
                async def __aenter__(self):
                    return state.db_session
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass
            return ContextManager()
        session_maker = mock_session_maker
    
    # Collect all questions from all sections
    all_questions = []
    for section in answer_outline.answer_outline:
        all_questions.extend(section.questions)
    
    print(f"Collected {len(all_questions)} questions from all sections")
    
    # Fetch relevant documents once for all questions
    relevant_documents = []
    async with session_maker() as db_session:

        relevant_documents = await fetch_relevant_documents(
            research_questions=all_questions,
            user_id=configuration.user_id,
            search_space_id=configuration.search_space_id,
            db_session=db_session,
            connectors_to_search=configuration.connectors_to_search
        )
    
    print(f"Fetched {len(relevant_documents)} relevant documents for all sections")
    
    # Create tasks to process each section in parallel with the same document set
    section_tasks = []
    for section in answer_outline.answer_outline:
        section_tasks.append(
            process_section_with_documents(
                section_title=section.section_title,
                section_questions=section.questions,
                user_id=configuration.user_id,
                search_space_id=configuration.search_space_id,
                session_maker=session_maker,
                relevant_documents=relevant_documents
            )
        )
    
    # Run all section processing tasks in parallel
    print(f"Running {len(section_tasks)} section processing tasks in parallel")
    section_results = await asyncio.gather(*section_tasks, return_exceptions=True)
    
    # Handle any exceptions in the results
    processed_results = []
    for i, result in enumerate(section_results):
        if isinstance(result, Exception):
            section_title = answer_outline.answer_outline[i].section_title
            error_message = f"Error processing section '{section_title}': {str(result)}"
            print(error_message)
            processed_results.append(error_message)
        else:
            processed_results.append(result)
    
    # Combine the results into a final report with section titles
    final_report = []
    for i, (section, content) in enumerate(zip(answer_outline.answer_outline, processed_results)):
        section_header = f"## {section.section_title}"
        final_report.append(section_header)
        final_report.append(content)
        final_report.append("\n")  # Add spacing between sections
    
    # Join all sections with newlines
    final_written_report = "\n".join(final_report)
    print(f"Generated final report with {len(final_report)} parts")
    
    return {
        "final_written_report": final_written_report
    }

async def process_section_with_documents(
    section_title: str, 
    section_questions: List[str],
    user_id: str, 
    search_space_id: int, 
    session_maker,
    relevant_documents: List[Dict[str, Any]]
) -> str:
    """
    Process a single section using pre-fetched documents.
    
    Args:
        section_title: The title of the section
        section_questions: List of research questions for this section
        user_id: The user ID
        search_space_id: The search space ID
        session_maker: Factory for creating new database sessions
        relevant_documents: Pre-fetched documents to use for this section
        
    Returns:
        The written section content
    """
    try:
        # Create a new database session for this section
        async with session_maker() as db_session:
            # Use the provided documents
            documents_to_use = relevant_documents
            
            # Fallback if no documents found
            if not documents_to_use:
                print(f"No relevant documents found for section: {section_title}")
                documents_to_use = [
                    {"content": f"No specific information was found for: {question}"}
                    for question in section_questions
                ]
            
            # Call the sub_section_writer graph with the appropriate config
            config = {
                "configurable": {
                    "sub_section_title": section_title,
                    "sub_section_questions": section_questions,
                    "relevant_documents": documents_to_use,
                    "user_id": user_id,
                    "search_space_id": search_space_id
                }
            }
            
            # Create the initial state with db_session
            state = {"db_session": db_session}
            
            # Invoke the sub-section writer graph
            print(f"Invoking sub_section_writer for: {section_title}")
            result = await sub_section_writer_graph.ainvoke(state, config)
            
            # Return the final answer from the sub_section_writer
            final_answer = result.get("final_answer", "No content was generated for this section.")
            return final_answer
    except Exception as e:
        print(f"Error processing section '{section_title}': {str(e)}")
        return f"Error processing section: {section_title}. Details: {str(e)}"

