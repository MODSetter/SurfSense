from .configuration import Configuration
from langchain_core.runnables import RunnableConfig
from .state import State
from typing import Any, Dict
from app.utils.connector_service import ConnectorService
from app.utils.reranker_service import RerankerService
from app.config import config as app_config
from .prompts import citation_system_prompt
from langchain_core.messages import HumanMessage, SystemMessage

async def fetch_relevant_documents(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """
    Fetch relevant documents for the sub-section using specified connectors.
    
    This node retrieves documents from various data sources based on the sub-questions
    derived from the sub-section title. It searches across all selected connectors
    (YouTube, Extension, Crawled URLs, Files, Tavily API, Slack, Notion) and reranks
    the results to provide the most relevant information for the agent workflow.
    
    Returns:
        Dict containing the reranked documents in the "relevant_documents_fetched" key.
    """
    # Get configuration
    configuration = Configuration.from_runnable_config(config)
    
    # Extract state parameters
    db_session = state.db_session
    
    # Extract config parameters
    user_id = configuration.user_id
    search_space_id = configuration.search_space_id
    TOP_K = configuration.top_k
    
    # Initialize services
    connector_service = ConnectorService(db_session)
    reranker_service = RerankerService.get_reranker_instance(app_config)

    all_raw_documents = []  # Store all raw documents before reranking
    
    for user_query in configuration.sub_questions:
        # Reformulate query (optional, consider if needed for each sub-question)
        # reformulated_query = await QueryService.reformulate_query(user_query)
        reformulated_query = user_query # Using original sub-question for now
        
        # Process each selected connector
        for connector in configuration.connectors_to_search:
            if connector == "YOUTUBE_VIDEO":
                _, youtube_chunks = await connector_service.search_youtube(
                    user_query=reformulated_query,
                    user_id=user_id,
                    search_space_id=search_space_id,
                    top_k=TOP_K
                )
                all_raw_documents.extend(youtube_chunks)
                
            elif connector == "EXTENSION":
                _, extension_chunks = await connector_service.search_extension(
                    user_query=reformulated_query,
                    user_id=user_id,
                    search_space_id=search_space_id,
                    top_k=TOP_K
                )
                all_raw_documents.extend(extension_chunks)
                
            elif connector == "CRAWLED_URL":
                _, crawled_urls_chunks = await connector_service.search_crawled_urls(
                    user_query=reformulated_query,
                    user_id=user_id,
                    search_space_id=search_space_id,
                    top_k=TOP_K
                )
                all_raw_documents.extend(crawled_urls_chunks)
                
            elif connector == "FILE":
                _, files_chunks = await connector_service.search_files(
                    user_query=reformulated_query,
                    user_id=user_id,
                    search_space_id=search_space_id,
                    top_k=TOP_K
                )
                all_raw_documents.extend(files_chunks)
                
            elif connector == "TAVILY_API":
                _, tavily_chunks = await connector_service.search_tavily(
                    user_query=reformulated_query,
                    user_id=user_id,
                    top_k=TOP_K
                )
                all_raw_documents.extend(tavily_chunks)
                
            elif connector == "SLACK_CONNECTOR":
                _, slack_chunks = await connector_service.search_slack(
                    user_query=reformulated_query,
                    user_id=user_id,
                    search_space_id=search_space_id,
                    top_k=TOP_K
                )
                all_raw_documents.extend(slack_chunks)
                
            elif connector == "NOTION_CONNECTOR":
                _, notion_chunks = await connector_service.search_notion(
                    user_query=reformulated_query,
                    user_id=user_id,
                    search_space_id=search_space_id,
                    top_k=TOP_K
                )
                all_raw_documents.extend(notion_chunks)
    
    # If we have documents and a reranker is available, rerank them
    # Deduplicate documents based on chunk_id or content to avoid processing duplicates
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
    
    # Use deduplicated documents for reranking
    reranked_docs = deduplicated_docs
    if deduplicated_docs and reranker_service:
        # Use the main sub_section_title for reranking context
        rerank_query = configuration.sub_section_title
        
        # Convert documents to format expected by reranker
        reranker_input_docs = [
            {
                "chunk_id": doc.get("chunk_id", f"chunk_{i}"),
                "content": doc.get("content", ""),
                "score": doc.get("score", 0.0),
                "document": {
                    "id": doc.get("document", {}).get("id", ""),
                    "title": doc.get("document", {}).get("title", ""),
                    "document_type": doc.get("document", {}).get("document_type", ""),
                    "metadata": doc.get("document", {}).get("metadata", {})
                }
            } for i, doc in enumerate(deduplicated_docs)
        ]
        
        # Rerank documents using the main title query
        reranked_docs = reranker_service.rerank_documents(rerank_query, reranker_input_docs)
        
        # Sort by score in descending order
        reranked_docs.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    # Update state with fetched documents
    return {
        "relevant_documents_fetched": reranked_docs
    }



async def write_sub_section(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """
    Write the sub-section using the fetched documents.
    
    This node takes the relevant documents fetched in the previous node and uses
    an LLM to generate a comprehensive answer to the sub-section questions with
    proper citations. The citations follow IEEE format using source IDs from the
    documents.
    
    Returns:
        Dict containing the final answer in the "final_answer" key.
    """
    
    # Get configuration and relevant documents
    configuration = Configuration.from_runnable_config(config)
    documents = state.relevant_documents_fetched
    
    # Initialize LLM
    llm = app_config.fast_llm_instance
    
    # If no documents were found, return a message indicating this
    if not documents or len(documents) == 0:
        return {
            "final_answer": "No relevant documents were found to answer this question. Please try refining your search or providing more specific questions."
        }
    
    # Prepare documents for citation formatting
    formatted_documents = []
    for i, doc in enumerate(documents):
        # Extract content and metadata
        content = doc.get("content", "")
        doc_info = doc.get("document", {})
        document_id = doc_info.get("id", f"{i+1}")  # Use document ID or index+1 as source_id
        
        # Format document according to the citation system prompt's expected format
        formatted_doc = f"""
        <document>
            <metadata>
                <source_id>{document_id}</source_id>
            </metadata>
            <content>
                {content}
            </content>
        </document>
        """
        formatted_documents.append(formatted_doc)
    
    # Create the query that combines the section title and questions
    # section_title = configuration.sub_section_title
    questions = "\n".join([f"- {q}" for q in configuration.sub_questions])
    documents_text = "\n".join(formatted_documents)
    
    # Construct a clear, structured query for the LLM
    human_message_content = f"""
    Please write a comprehensive answer for the title: 
    
    Address the following questions:
    <questions>
        {questions}
    </questions>

    Use the provided documents as your source material and cite them properly using the IEEE citation format [X] where X is the source_id.
    <documents>
        {documents_text}
    </documents>
    """
    
    # Create messages for the LLM
    messages = [
        SystemMessage(content=citation_system_prompt),
        HumanMessage(content=human_message_content)
    ]
    
    # Call the LLM and get the response
    response = await llm.ainvoke(messages)
    final_answer = response.content
    
    return {
        "final_answer": final_answer
    }

