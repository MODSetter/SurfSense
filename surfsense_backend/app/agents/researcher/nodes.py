import asyncio
import json
from typing import Any, Dict, List

from app.config import config as app_config
from app.db import async_session_maker
from app.utils.connector_service import ConnectorService
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from .configuration import Configuration
from .prompts import get_answer_outline_system_prompt
from .state import State
from .sub_section_writer.graph import graph as sub_section_writer_graph

from langgraph.types import StreamWriter


class Section(BaseModel):
    """A section in the answer outline."""
    section_id: int = Field(..., description="The zero-based index of the section")
    section_title: str = Field(..., description="The title of the section")
    questions: List[str] = Field(..., description="Questions to research for this section")

class AnswerOutline(BaseModel):
    """The complete answer outline with all sections."""
    answer_outline: List[Section] = Field(..., description="List of sections in the answer outline")

async def write_answer_outline(state: State, config: RunnableConfig, writer: StreamWriter) -> Dict[str, Any]:
    """
    Create a structured answer outline based on the user query.
    
    This node takes the user query and number of sections from the configuration and uses
    an LLM to generate a comprehensive outline with logical sections and research questions
    for each section.
    
    Returns:
        Dict containing the answer outline in the "answer_outline" key for state update.
    """
    streaming_service = state.streaming_service
    
    streaming_service.only_update_terminal("Generating answer outline...")
    writer({"yeild_value": streaming_service._format_annotations()})
    # Get configuration from runnable config
    configuration = Configuration.from_runnable_config(config)
    user_query = configuration.user_query
    num_sections = configuration.num_sections
    
    streaming_service.only_update_terminal(f"Planning research approach for query: {user_query[:100]}...")
    writer({"yeild_value": streaming_service._format_annotations()})
    
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
    
    streaming_service.only_update_terminal("Designing structured outline with AI...")
    writer({"yeild_value": streaming_service._format_annotations()})
    
    # Create messages for the LLM
    messages = [
        SystemMessage(content=get_answer_outline_system_prompt()),
        HumanMessage(content=human_message_content)
    ]
    
    # Call the LLM directly without using structured output
    streaming_service.only_update_terminal("Processing answer structure...")
    writer({"yeild_value": streaming_service._format_annotations()})
    
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
            
            total_questions = sum(len(section.questions) for section in answer_outline.answer_outline)
            streaming_service.only_update_terminal(f"Successfully generated outline with {len(answer_outline.answer_outline)} sections and {total_questions} research questions")
            writer({"yeild_value": streaming_service._format_annotations()})
            
            print(f"Successfully generated answer outline with {len(answer_outline.answer_outline)} sections")
            
            # Return state update
            return {"answer_outline": answer_outline}
        else:
            # If JSON structure not found, raise a clear error
            error_message = f"Could not find valid JSON in LLM response. Raw response: {content}"
            streaming_service.only_update_terminal(error_message, "error")
            writer({"yeild_value": streaming_service._format_annotations()})
            raise ValueError(error_message)
            
    except (json.JSONDecodeError, ValueError) as e:
        # Log the error and re-raise it
        error_message = f"Error parsing LLM response: {str(e)}"
        streaming_service.only_update_terminal(error_message, "error")
        writer({"yeild_value": streaming_service._format_annotations()})
        
        print(f"Error parsing LLM response: {str(e)}")
        print(f"Raw response: {response.content}")
        raise

async def fetch_relevant_documents(
    research_questions: List[str],
    user_id: str,
    search_space_id: int,
    db_session: AsyncSession,
    connectors_to_search: List[str],
    writer: StreamWriter = None,
    state: State = None,
    top_k: int = 10,
    connector_service: ConnectorService = None
) -> List[Dict[str, Any]]:
    """
    Fetch relevant documents for research questions using the provided connectors.
    
    Args:
        research_questions: List of research questions to find documents for
        user_id: The user ID
        search_space_id: The search space ID
        db_session: The database session
        connectors_to_search: List of connectors to search
        writer: StreamWriter for sending progress updates
        state: The current state containing the streaming service
        top_k: Number of top results to retrieve per connector per question
        
    Returns:
        List of relevant documents
    """
    # Initialize services
    # connector_service = ConnectorService(db_session)
    
    # Only use streaming if both writer and state are provided
    streaming_service = state.streaming_service if state is not None else None

    # Stream initial status update
    if streaming_service and writer:
        streaming_service.only_update_terminal(f"Starting research on {len(research_questions)} questions using {len(connectors_to_search)} connectors...")
        writer({"yeild_value": streaming_service._format_annotations()})

    all_raw_documents = []  # Store all raw documents
    all_sources = []  # Store all sources
    
    for i, user_query in enumerate(research_questions):
        # Stream question being researched
        if streaming_service and writer:
            streaming_service.only_update_terminal(f"Researching question {i+1}/{len(research_questions)}: {user_query[:100]}...")
            writer({"yeild_value": streaming_service._format_annotations()})
            
        # Use original research question as the query
        reformulated_query = user_query
        
        # Process each selected connector
        for connector in connectors_to_search:
            # Stream connector being searched
            if streaming_service and writer:
                streaming_service.only_update_terminal(f"Searching {connector} for relevant information...")
                writer({"yeild_value": streaming_service._format_annotations()})
                
            try:
                if connector == "YOUTUBE_VIDEO":
                    source_object, youtube_chunks = await connector_service.search_youtube(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k
                    )
                    
                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(youtube_chunks)
                    
                    # Stream found document count
                    if streaming_service and writer:
                        streaming_service.only_update_terminal(f"Found {len(youtube_chunks)} YouTube chunks relevant to the query")
                        writer({"yeild_value": streaming_service._format_annotations()})
                    
                elif connector == "EXTENSION":
                    source_object, extension_chunks = await connector_service.search_extension(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k
                    )
                    
                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(extension_chunks)
                    
                    # Stream found document count
                    if streaming_service and writer:
                        streaming_service.only_update_terminal(f"Found {len(extension_chunks)} extension chunks relevant to the query")
                        writer({"yeild_value": streaming_service._format_annotations()})
                    
                elif connector == "CRAWLED_URL":
                    source_object, crawled_urls_chunks = await connector_service.search_crawled_urls(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k
                    )
                    
                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(crawled_urls_chunks)
                    
                    # Stream found document count
                    if streaming_service and writer:
                        streaming_service.only_update_terminal(f"Found {len(crawled_urls_chunks)} crawled URL chunks relevant to the query")
                        writer({"yeild_value": streaming_service._format_annotations()})
                    
                elif connector == "FILE":
                    source_object, files_chunks = await connector_service.search_files(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k
                    )
                    
                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(files_chunks)
                    
                    # Stream found document count
                    if streaming_service and writer:
                        streaming_service.only_update_terminal(f"Found {len(files_chunks)} file chunks relevant to the query")
                        writer({"yeild_value": streaming_service._format_annotations()})
                    
                    
                elif connector == "SLACK_CONNECTOR":
                    source_object, slack_chunks = await connector_service.search_slack(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k
                    )
                    
                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(slack_chunks)
                    
                    # Stream found document count
                    if streaming_service and writer:
                        streaming_service.only_update_terminal(f"Found {len(slack_chunks)} Slack messages relevant to the query")
                        writer({"yeild_value": streaming_service._format_annotations()})
                    
                elif connector == "NOTION_CONNECTOR":
                    source_object, notion_chunks = await connector_service.search_notion(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k
                    )
                    
                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(notion_chunks)
                    
                    # Stream found document count
                    if streaming_service and writer:
                        streaming_service.only_update_terminal(f"Found {len(notion_chunks)} Notion pages/blocks relevant to the query")
                        writer({"yeild_value": streaming_service._format_annotations()})
                    
                elif connector == "GITHUB_CONNECTOR":
                    source_object, github_chunks = await connector_service.search_github(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k
                    )
                    
                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(github_chunks)
                    
                    # Stream found document count
                    if streaming_service and writer:
                        streaming_service.only_update_terminal(f"Found {len(github_chunks)} GitHub files/issues relevant to the query")
                        writer({"yeild_value": streaming_service._format_annotations()})
                    
                elif connector == "LINEAR_CONNECTOR":
                    source_object, linear_chunks = await connector_service.search_linear(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k
                    )
                    
                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(linear_chunks)
                    
                    # Stream found document count
                    if streaming_service and writer:
                        streaming_service.only_update_terminal(f"Found {len(linear_chunks)} Linear issues relevant to the query")
                        writer({"yeild_value": streaming_service._format_annotations()})
                        
                elif connector == "TAVILY_API":
                    source_object, tavily_chunks = await connector_service.search_tavily(
                        user_query=reformulated_query,
                        user_id=user_id,
                        top_k=top_k
                    )
                    
                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(tavily_chunks)
                    
                    # Stream found document count
                    if streaming_service and writer:
                        streaming_service.only_update_terminal(f"Found {len(tavily_chunks)} web search results relevant to the query")
                        writer({"yeild_value": streaming_service._format_annotations()})
                        
                elif connector == "LINKUP_API":
                    if top_k > 10:
                        linkup_mode = "deep"
                    else:
                        linkup_mode = "standard"
                        
                    source_object, linkup_chunks = await connector_service.search_linkup(
                        user_query=reformulated_query,
                        user_id=user_id,
                        mode=linkup_mode
                    )   
                    
                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(linkup_chunks) 
                    
                    # Stream found document count
                    if streaming_service and writer:
                        streaming_service.only_update_terminal(f"Found {len(linkup_chunks)} Linkup chunks relevant to the query")
                        writer({"yeild_value": streaming_service._format_annotations()})
                    

            except Exception as e:
                error_message = f"Error searching connector {connector}: {str(e)}"
                print(error_message)
                
                # Stream error message
                if streaming_service and writer:
                    streaming_service.only_update_terminal(error_message, "error")
                    writer({"yeild_value": streaming_service._format_annotations()})
                
                # Continue with other connectors on error
                continue
    
    # Deduplicate source objects by ID before streaming
    deduplicated_sources = []
    seen_source_keys = set()
    
    for source_obj in all_sources:
        # Use combination of source ID and type as a unique identifier
        # This ensures we don't accidentally deduplicate sources from different connectors
        source_id = source_obj.get('id')
        source_type = source_obj.get('type')
        
        if source_id and source_type:
            source_key = f"{source_type}_{source_id}"
            if source_key not in seen_source_keys:
                seen_source_keys.add(source_key)
                deduplicated_sources.append(source_obj)
        else:
            # If there's no ID or type, just add it to be safe
            deduplicated_sources.append(source_obj)
    
    # Stream info about deduplicated sources
    if streaming_service and writer:
        streaming_service.only_update_terminal(f"Collected {len(deduplicated_sources)} unique sources across all connectors")
        writer({"yeild_value": streaming_service._format_annotations()})
        
    # After all sources are collected and deduplicated, stream them
    if streaming_service and writer:
        streaming_service.only_update_sources(deduplicated_sources)
        writer({"yeild_value": streaming_service._format_annotations()})
    
    # Deduplicate raw documents based on chunk_id or content
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
    
    # Stream info about deduplicated documents
    if streaming_service and writer:
        streaming_service.only_update_terminal(f"Found {len(deduplicated_docs)} unique document chunks after deduplication")
        writer({"yeild_value": streaming_service._format_annotations()})
    
    # Return deduplicated documents
    return deduplicated_docs

async def process_sections(state: State, config: RunnableConfig, writer: StreamWriter) -> Dict[str, Any]:
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
    streaming_service = state.streaming_service
    
    streaming_service.only_update_terminal(f"Starting to process research sections...")
    writer({"yeild_value": streaming_service._format_annotations()})
    
    print(f"Processing sections from outline: {answer_outline is not None}")
    
    if not answer_outline:
        streaming_service.only_update_terminal("Error: No answer outline was provided. Cannot generate report.", "error")
        writer({"yeild_value": streaming_service._format_annotations()})
        return {
            "final_written_report": "No answer outline was provided. Cannot generate final report."
        }
    
    # Collect all questions from all sections
    all_questions = []
    for section in answer_outline.answer_outline:
        all_questions.extend(section.questions)
    
    print(f"Collected {len(all_questions)} questions from all sections")
    streaming_service.only_update_terminal(f"Found {len(all_questions)} research questions across {len(answer_outline.answer_outline)} sections")
    writer({"yeild_value": streaming_service._format_annotations()})
    
    # Fetch relevant documents once for all questions
    streaming_service.only_update_terminal("Searching for relevant information across all connectors...")
    writer({"yeild_value": streaming_service._format_annotations()})
    
    if configuration.num_sections == 1:
        TOP_K = 10
    elif configuration.num_sections == 3:
        TOP_K = 20
    elif configuration.num_sections == 6:
        TOP_K = 30
    
    relevant_documents = []
    async with async_session_maker() as db_session:
        try:
            # Create connector service inside the db_session scope
            connector_service = ConnectorService(db_session)
            
            relevant_documents = await fetch_relevant_documents(
                research_questions=all_questions,
                user_id=configuration.user_id,
                search_space_id=configuration.search_space_id,
                db_session=db_session,
                connectors_to_search=configuration.connectors_to_search,
                writer=writer,
                state=state,
                top_k=TOP_K,
                connector_service=connector_service
            )
        except Exception as e:
            error_message = f"Error fetching relevant documents: {str(e)}"
            print(error_message)
            streaming_service.only_update_terminal(error_message, "error")
            writer({"yeild_value": streaming_service._format_annotations()})
            # Log the error and continue with an empty list of documents
            # This allows the process to continue, but the report might lack information
            relevant_documents = []
            # Consider adding more robust error handling or reporting if needed
    
    print(f"Fetched {len(relevant_documents)} relevant documents for all sections")
    streaming_service.only_update_terminal(f"Starting to draft {len(answer_outline.answer_outline)} sections using {len(relevant_documents)} relevant document chunks")
    writer({"yeild_value": streaming_service._format_annotations()})
    
    # Create tasks to process each section in parallel with the same document set
    section_tasks = []
    streaming_service.only_update_terminal("Creating processing tasks for each section...")
    writer({"yeild_value": streaming_service._format_annotations()})
    
    for section in answer_outline.answer_outline:
        section_tasks.append(
            process_section_with_documents(
                section_title=section.section_title,
                section_questions=section.questions,
                user_query=configuration.user_query,
                user_id=configuration.user_id,
                search_space_id=configuration.search_space_id,
                relevant_documents=relevant_documents,
                state=state,
                writer=writer
            )
        )
    
    # Run all section processing tasks in parallel
    print(f"Running {len(section_tasks)} section processing tasks in parallel")
    streaming_service.only_update_terminal(f"Processing {len(section_tasks)} sections simultaneously...")
    writer({"yeild_value": streaming_service._format_annotations()})
    
    section_results = await asyncio.gather(*section_tasks, return_exceptions=True)
    
    # Handle any exceptions in the results
    streaming_service.only_update_terminal("Combining section results into final report...")
    writer({"yeild_value": streaming_service._format_annotations()})
    
    processed_results = []
    for i, result in enumerate(section_results):
        if isinstance(result, Exception):
            section_title = answer_outline.answer_outline[i].section_title
            error_message = f"Error processing section '{section_title}': {str(result)}"
            print(error_message)
            streaming_service.only_update_terminal(error_message, "error")
            writer({"yeild_value": streaming_service._format_annotations()})
            processed_results.append(error_message)
        else:
            processed_results.append(result)
    
    # Combine the results into a final report with section titles
    final_report = []
    for i, (section, content) in enumerate(zip(answer_outline.answer_outline, processed_results)):
        # Skip adding the section header since the content already contains the title
        final_report.append(content)
        final_report.append("\n")  

    
    # Join all sections with newlines
    final_written_report = "\n".join(final_report)
    print(f"Generated final report with {len(final_report)} parts")
    
    streaming_service.only_update_terminal("Final research report generated successfully!")
    writer({"yeild_value": streaming_service._format_annotations()})
    
    if hasattr(state, 'streaming_service') and state.streaming_service:
        # Convert the final report to the expected format for UI:
        # A list of strings where empty strings represent line breaks
        formatted_report = []
        for section in final_report:
            if section == "\n":
                # Add an empty string for line breaks
                formatted_report.append("")
            else:
                # Split any multiline content by newlines and add each line
                section_lines = section.split("\n")
                formatted_report.extend(section_lines)
        
        state.streaming_service.only_update_answer(formatted_report)
        writer({"yeild_value": state.streaming_service._format_annotations()})

    
    return {
        "final_written_report": final_written_report
    }

async def process_section_with_documents(
    section_title: str, 
    section_questions: List[str],
    user_id: str, 
    search_space_id: int, 
    relevant_documents: List[Dict[str, Any]],
    user_query: str,
    state: State = None,
    writer: StreamWriter = None
) -> str:
    """
    Process a single section using pre-fetched documents.
    
    Args:
        section_title: The title of the section
        section_questions: List of research questions for this section
        user_id: The user ID
        search_space_id: The search space ID
        relevant_documents: Pre-fetched documents to use for this section
        state: The current state
        writer: StreamWriter for sending progress updates
        
    Returns:
        The written section content
    """
    try:
        # Use the provided documents
        documents_to_use = relevant_documents
        
        # Send status update via streaming if available
        if state and state.streaming_service and writer:
            state.streaming_service.only_update_terminal(f"Writing section: {section_title} with {len(section_questions)} research questions")
            writer({"yeild_value": state.streaming_service._format_annotations()})
        
        # Fallback if no documents found
        if not documents_to_use:
            print(f"No relevant documents found for section: {section_title}")
            if state and state.streaming_service and writer:
                state.streaming_service.only_update_terminal(f"Warning: No relevant documents found for section: {section_title}", "warning")
                writer({"yeild_value": state.streaming_service._format_annotations()})
                
            documents_to_use = [
                {"content": f"No specific information was found for: {question}"}
                for question in section_questions
            ]
        
        # Create a new database session for this section
        async with async_session_maker() as db_session:
            # Call the sub_section_writer graph with the appropriate config
            config = {
                "configurable": {
                    "sub_section_title": section_title,
                    "sub_section_questions": section_questions,
                    "user_query": user_query,
                    "relevant_documents": documents_to_use,
                    "user_id": user_id,
                    "search_space_id": search_space_id
                }
            }
            
            # Create the initial state with db_session
            sub_state = {"db_session": db_session}
            
            # Invoke the sub-section writer graph
            print(f"Invoking sub_section_writer for: {section_title}")
            if state and state.streaming_service and writer:
                state.streaming_service.only_update_terminal(f"Analyzing information and drafting content for section: {section_title}")
                writer({"yeild_value": state.streaming_service._format_annotations()})
                
            result = await sub_section_writer_graph.ainvoke(sub_state, config)
            
            # Return the final answer from the sub_section_writer
            final_answer = result.get("final_answer", "No content was generated for this section.")
            
            # Send section content update via streaming if available
            if state and state.streaming_service and writer:
                state.streaming_service.only_update_terminal(f"Completed writing section: {section_title}")
                writer({"yeild_value": state.streaming_service._format_annotations()})
                
            return final_answer
    except Exception as e:
        print(f"Error processing section '{section_title}': {str(e)}")
        
        # Send error update via streaming if available
        if state and state.streaming_service and writer:
            state.streaming_service.only_update_terminal(f"Error processing section '{section_title}': {str(e)}", "error")
            writer({"yeild_value": state.streaming_service._format_annotations()})
            
        return f"Error processing section: {section_title}. Details: {str(e)}"

