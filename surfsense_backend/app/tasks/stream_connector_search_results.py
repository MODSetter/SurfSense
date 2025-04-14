import json
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, AsyncGenerator, Dict, Any
import asyncio
import re

from app.utils.connector_service import ConnectorService
from app.utils.research_service import ResearchService
from app.utils.streaming_service import StreamingService
from app.utils.reranker_service import RerankerService
from app.utils.query_service import QueryService
from app.config import config
from app.utils.document_converters import convert_chunks_to_langchain_documents

async def stream_connector_search_results(
    user_query: str, 
    user_id: int, 
    search_space_id: int, 
    session: AsyncSession, 
    research_mode: str, 
    selected_connectors: List[str]
) -> AsyncGenerator[str, None]:
    """
    Stream connector search results to the client
    
    Args:
        user_query: The user's query
        user_id: The user's ID
        search_space_id: The search space ID
        session: The database session
        research_mode: The research mode
        selected_connectors: List of selected connectors
        
    Yields:
        str: Formatted response strings
    """
    # Initialize services
    connector_service = ConnectorService(session)
    streaming_service = StreamingService()
    
    # Reformulate the user query using the strategic LLM
    yield streaming_service.add_terminal_message("Reformulating your query for better results...", "info")
    reformulated_query = await QueryService.reformulate_query(user_query)
    yield streaming_service.add_terminal_message(f"Searching for: {reformulated_query}", "success")
    
    reranker_service = RerankerService.get_reranker_instance(config)
    
    all_raw_documents = []  # Store all raw documents before reranking
    all_sources = []
    TOP_K = 20
    
    if research_mode == "GENERAL":
        TOP_K = 20
    elif research_mode == "DEEP":
        TOP_K = 40
    elif research_mode == "DEEPER":
        TOP_K = 60
    

    # Process each selected connector
    for connector in selected_connectors:
        if connector == "YOUTUBE_VIDEO":
            # Send terminal message about starting search
            yield streaming_service.add_terminal_message("Starting to search for youtube videos...")
            
            # Search for YouTube videos using reformulated query
            result_object, youtube_chunks = await connector_service.search_youtube(
                user_query=reformulated_query,
                user_id=user_id,
                search_space_id=search_space_id,
                top_k=TOP_K
            )
            
            # Send terminal message about search results
            yield streaming_service.add_terminal_message(
                f"Found {len(result_object['sources'])} relevant YouTube videos",
                "success"
            )
            
            # Update sources
            all_sources.append(result_object)
            yield streaming_service.update_sources(all_sources)
            
            # Add documents to collection
            all_raw_documents.extend(youtube_chunks)
            
            
        # Extension Docs
        if connector == "EXTENSION":
            # Send terminal message about starting search
            yield streaming_service.add_terminal_message("Starting to search for extension...")
            
            # Search for crawled URLs using reformulated query
            result_object, extension_chunks = await connector_service.search_extension(
                user_query=reformulated_query,
                user_id=user_id,
                search_space_id=search_space_id,
                top_k=TOP_K
            )
            
            # Send terminal message about search results
            yield streaming_service.add_terminal_message(
                f"Found {len(result_object['sources'])} relevant extension documents",
                "success"
            )
            
            # Update sources
            all_sources.append(result_object)
            yield streaming_service.update_sources(all_sources)
            
            # Add documents to collection
            all_raw_documents.extend(extension_chunks)
            
            
        # Crawled URLs
        if connector == "CRAWLED_URL":
            # Send terminal message about starting search
            yield streaming_service.add_terminal_message("Starting to search for crawled URLs...")
            
            # Search for crawled URLs using reformulated query
            result_object, crawled_urls_chunks = await connector_service.search_crawled_urls(
                user_query=reformulated_query,
                user_id=user_id,
                search_space_id=search_space_id,
                top_k=TOP_K
            )
            
            # Send terminal message about search results
            yield streaming_service.add_terminal_message(
                f"Found {len(result_object['sources'])} relevant crawled URLs",
                "success"
            )
            
            # Update sources
            all_sources.append(result_object)
            yield streaming_service.update_sources(all_sources)
            
            # Add documents to collection
            all_raw_documents.extend(crawled_urls_chunks)
           

        # Files
        if connector == "FILE":
            # Send terminal message about starting search
            yield streaming_service.add_terminal_message("Starting to search for files...")
            
            # Search for files using reformulated query
            result_object, files_chunks = await connector_service.search_files(
                user_query=reformulated_query,
                user_id=user_id,
                search_space_id=search_space_id,
                top_k=TOP_K
            )

            # Send terminal message about search results
            yield streaming_service.add_terminal_message(
                f"Found {len(result_object['sources'])} relevant files",
                "success"
            )

            # Update sources
            all_sources.append(result_object)
            yield streaming_service.update_sources(all_sources) 

            # Add documents to collection
            all_raw_documents.extend(files_chunks)
            
        # Tavily Connector
        if connector == "TAVILY_API":
            # Send terminal message about starting search
            yield streaming_service.add_terminal_message("Starting to search with Tavily API...")
            
            # Search using Tavily API with reformulated query
            result_object, tavily_chunks = await connector_service.search_tavily(
                user_query=reformulated_query,
                user_id=user_id,
                top_k=TOP_K
            )
            
            # Send terminal message about search results
            yield streaming_service.add_terminal_message(
                f"Found {len(result_object['sources'])} relevant results from Tavily",
                "success"
            )
            
            # Update sources
            all_sources.append(result_object)
            yield streaming_service.update_sources(all_sources)
            
            # Add documents to collection
            all_raw_documents.extend(tavily_chunks)
        
        # Slack Connector
        if connector == "SLACK_CONNECTOR":
            # Send terminal message about starting search
            yield streaming_service.add_terminal_message("Starting to search for slack connector...")   
            
            # Search using Slack API with reformulated query
            result_object, slack_chunks = await connector_service.search_slack(
                user_query=reformulated_query,
                user_id=user_id,
                search_space_id=search_space_id,
                top_k=TOP_K
            )
            
            # Send terminal message about search results
            yield streaming_service.add_terminal_message(
                f"Found {len(result_object['sources'])} relevant results from Slack",
                "success"
            )
            
            # Update sources
            all_sources.append(result_object)
            yield streaming_service.update_sources(all_sources)
            
            # Add documents to collection
            all_raw_documents.extend(slack_chunks)
            
            
        # Notion Connector
        if connector == "NOTION_CONNECTOR":
            # Send terminal message about starting search
            yield streaming_service.add_terminal_message("Starting to search for notion connector...")  
            
            # Search using Notion API with reformulated query
            result_object, notion_chunks = await connector_service.search_notion(
                user_query=reformulated_query,
                user_id=user_id,
                search_space_id=search_space_id,
                top_k=TOP_K
            )
            
            # Send terminal message about search results
            yield streaming_service.add_terminal_message(
                f"Found {len(result_object['sources'])} relevant results from Notion",
                "success"
            )
            
            # Update sources
            all_sources.append(result_object)
            yield streaming_service.update_sources(all_sources)
            
            # Add documents to collection
            all_raw_documents.extend(notion_chunks)
            
            
        # Github Connector
        if connector == "GITHUB_CONNECTOR":
            # Send terminal message about starting search
            yield streaming_service.add_terminal_message("Starting to search for GitHub connector...")  
            print("Starting to search for GitHub connector...")
            # Search using Github API with reformulated query
            result_object, github_chunks = await connector_service.search_github(
                user_query=reformulated_query,
                user_id=user_id,
                search_space_id=search_space_id,
                top_k=TOP_K
            )
            
            # Send terminal message about search results
            yield streaming_service.add_terminal_message(
                f"Found {len(result_object['sources'])} relevant results from Github",
                "success"
            )
            
            # Update sources
            all_sources.append(result_object)
            yield streaming_service.update_sources(all_sources)
            
            # Add documents to collection
            all_raw_documents.extend(github_chunks)
            
            
    

    # If we have documents to research
    if all_raw_documents:
        # Rerank all documents if reranker is available
        if reranker_service:
            yield streaming_service.add_terminal_message("Reranking documents for better relevance...", "info")
            
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
                } for i, doc in enumerate(all_raw_documents)
            ]
            
            # Rerank documents using the reformulated query
            reranked_docs = reranker_service.rerank_documents(reformulated_query, reranker_input_docs)
            
            # Sort by score in descending order
            reranked_docs.sort(key=lambda x: x.get("score", 0), reverse=True)
            
           
            
            # Convert back to langchain documents format
            from langchain.schema import Document as LangchainDocument
            all_langchain_documents_to_research = [
                LangchainDocument(
                    page_content= f"""<document><metadata><source_id>{doc.get("document", {}).get("id", "")}</source_id></metadata><content>{doc.get("content", "")}</content></document>""",
                    metadata={
                        # **doc.get("document", {}).get("metadata", {}),
                        # "score": doc.get("score", 0.0),
                        # "rank": doc.get("rank", 0),
                        # "document_id": doc.get("document", {}).get("id", ""),
                        # "document_title": doc.get("document", {}).get("title", ""),
                        # "document_type": doc.get("document", {}).get("document_type", ""),
                        # # Explicitly set source_id for citation purposes
                        "source_id": str(doc.get("document", {}).get("id", ""))
                    }
                ) for doc in reranked_docs
            ]
            
            yield streaming_service.add_terminal_message(f"Reranked {len(all_langchain_documents_to_research)} documents", "success")
        else:
            # Use raw documents if no reranker is available
            all_langchain_documents_to_research = convert_chunks_to_langchain_documents(all_raw_documents)
        
        # Send terminal message about starting research
        yield streaming_service.add_terminal_message("Starting to research...", "info")
        
        # Create a buffer to collect report content
        report_buffer = []
        

        # Use the streaming research method
        yield streaming_service.add_terminal_message("Generating report...", "info")
        
        # Create a wrapper to handle the streaming
        class StreamHandler:
            def __init__(self):
                self.queue = asyncio.Queue()
                
            async def handle_progress(self, data):
                result = None
                if data.get("type") == "logs":
                    # Handle log messages
                    result = streaming_service.add_terminal_message(data.get("output", ""), "info")
                elif data.get("type") == "report":
                    # Handle report content
                    content = data.get("output", "")
                    
                    # Fix incorrect citation formats using regex
                    
                    # More specific pattern to match only numeric citations in markdown-style links
                    # This matches patterns like ([1](https://github.com/...)) but not general links like ([Click here](https://...))
                    pattern = r'\(\[(\d+)\]\((https?://[^\)]+)\)\)'
                    
                    # Replace with just [X] where X is the number
                    content = re.sub(pattern, r'[\1]', content)
                    
                    # Also match other incorrect formats like ([1]) and convert to [1]
                    # Only match if the content inside brackets is a number
                    content = re.sub(r'\(\[(\d+)\]\)', r'[\1]', content)
                    
                    report_buffer.append(content)
                    # Update the answer with the accumulated content
                    result = streaming_service.update_answer(report_buffer)
                
                if result:
                    await self.queue.put(result)
                return result
                
            async def get_next(self):
                try:
                    return await self.queue.get()
                except Exception as e:
                    print(f"Error getting next item from queue: {e}")
                    return None
                
            def task_done(self):
                self.queue.task_done()
        
        # Create the stream handler
        stream_handler = StreamHandler()
        
        # Start the research process in a separate task
        research_task = asyncio.create_task(
            ResearchService.stream_research(
                user_query=reformulated_query,
                documents=all_langchain_documents_to_research,
                on_progress=stream_handler.handle_progress,
                research_mode=research_mode
            )
        )
        
        # Stream results as they become available
        while not research_task.done() or not stream_handler.queue.empty():
            try:
                # Get the next result with a timeout
                result = await asyncio.wait_for(stream_handler.get_next(), timeout=0.1)
                stream_handler.task_done()
                yield result
            except asyncio.TimeoutError:
                # No result available yet, check if the research task is done
                if research_task.done():
                    # If the queue is empty and the task is done, we're finished
                    if stream_handler.queue.empty():
                        break
        
        # Get the final report
        try:
            final_report = await research_task
            
            # Send terminal message about research completion
            yield streaming_service.add_terminal_message("Research completed", "success")
            
            # Update the answer with the final report
            final_report_lines = final_report.split('\n')
            yield streaming_service.update_answer(final_report_lines)
        except Exception as e:
            # Handle any exceptions
            yield streaming_service.add_terminal_message(f"Error during research: {str(e)}", "error")
        
        # Send completion message
        yield streaming_service.format_completion()
