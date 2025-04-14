import json
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.retriver.chunks_hybrid_search import ChucksHybridSearchRetriever
from app.db import SearchSourceConnector, SearchSourceConnectorType
from tavily import TavilyClient


class ConnectorService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.retriever = ChucksHybridSearchRetriever(session)
        self.source_id_counter = 1
    
    async def search_crawled_urls(self, user_query: str, user_id: str, search_space_id: int, top_k: int = 20) -> tuple:
        """
        Search for crawled URLs and return both the source information and langchain documents
        
        Returns:
            tuple: (sources_info, langchain_documents)
        """
        crawled_urls_chunks = await self.retriever.hybrid_search(
            query_text=user_query,
            top_k=top_k,
            user_id=user_id,
            search_space_id=search_space_id,
            document_type="CRAWLED_URL"
        )

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        for i, chunk in enumerate(crawled_urls_chunks):
            # Fix for UI
            crawled_urls_chunks[i]['document']['id'] = self.source_id_counter
            # Extract document metadata
            document = chunk.get('document', {})
            metadata = document.get('metadata', {})

            # Create a source entry
            source = {
                "id":  self.source_id_counter,
                "title": document.get('title', 'Untitled Document'),
                "description": metadata.get('og:description', metadata.get('ogDescription', chunk.get('content', '')[:100])),
                "url": metadata.get('url', '')
            }

            self.source_id_counter += 1
            sources_list.append(source)
        
        # Create result object
        result_object = {
            "id": 1,
            "name": "Crawled URLs",
            "type": "CRAWLED_URL",
            "sources": sources_list,
        }
        
        return result_object, crawled_urls_chunks
    
    async def search_files(self, user_query: str, user_id: str, search_space_id: int, top_k: int = 20) -> tuple:
        """
        Search for files and return both the source information and langchain documents
        
        Returns:
            tuple: (sources_info, langchain_documents)
        """
        files_chunks = await self.retriever.hybrid_search(
            query_text=user_query,
            top_k=top_k,
            user_id=user_id,
            search_space_id=search_space_id,
            document_type="FILE"
        )

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        for i, chunk in enumerate(files_chunks):
            # Fix for UI
            files_chunks[i]['document']['id'] = self.source_id_counter
            # Extract document metadata
            document = chunk.get('document', {})
            metadata = document.get('metadata', {})

            # Create a source entry
            source = {
                "id":  self.source_id_counter,
                "title": document.get('title', 'Untitled Document'),
                "description": metadata.get('og:description', metadata.get('ogDescription', chunk.get('content', '')[:100])),
                "url": metadata.get('url', '')
            }

            self.source_id_counter += 1
            sources_list.append(source)
        
        # Create result object
        result_object = {
            "id": 2,
            "name": "Files",
            "type": "FILE",
            "sources": sources_list,
        }
        
        return result_object, files_chunks
    
    async def get_connector_by_type(self, user_id: str, connector_type: SearchSourceConnectorType) -> Optional[SearchSourceConnector]:
        """
        Get a connector by type for a specific user
        
        Args:
            user_id: The user's ID
            connector_type: The connector type to retrieve
            
        Returns:
            Optional[SearchSourceConnector]: The connector if found, None otherwise
        """
        result = await self.session.execute(
            select(SearchSourceConnector)
            .filter(
                SearchSourceConnector.user_id == user_id,
                SearchSourceConnector.connector_type == connector_type
            )
        )
        return result.scalars().first()
    
    async def search_tavily(self, user_query: str, user_id: str, top_k: int = 20) -> tuple:
        """
        Search using Tavily API and return both the source information and documents
        
        Args:
            user_query: The user's query
            user_id: The user's ID
            top_k: Maximum number of results to return
            
        Returns:
            tuple: (sources_info, documents)
        """
        # Get Tavily connector configuration
        tavily_connector = await self.get_connector_by_type(user_id, SearchSourceConnectorType.TAVILY_API)
        
        if not tavily_connector:
            # Return empty results if no Tavily connector is configured
            return {
                "id": 3,
                "name": "Tavily Search",
                "type": "TAVILY_API",
                "sources": [],
            }, []
        
        # Initialize Tavily client with API key from connector config
        tavily_api_key = tavily_connector.config.get("TAVILY_API_KEY")
        tavily_client = TavilyClient(api_key=tavily_api_key)
        
        # Perform search with Tavily
        try:
            response = tavily_client.search(
                query=user_query,
                max_results=top_k,
                search_depth="advanced"  # Use advanced search for better results
            )
            
            # Extract results from Tavily response
            tavily_results = response.get("results", [])
            
            # Process each result and create sources directly without deduplication
            sources_list = []
            documents = []
            
            for i, result in enumerate(tavily_results):
                
                # Create a source entry
                source = {
                    "id": self.source_id_counter,
                    "title": result.get("title", "Tavily Result"),
                    "description": result.get("content", "")[:100],
                    "url": result.get("url", "")
                }
                sources_list.append(source)
                
                # Create a document entry
                document = {
                    "chunk_id": f"tavily_chunk_{i}",
                    "content": result.get("content", ""),
                    "score": result.get("score", 0.0),
                    "document": {
                        "id": self.source_id_counter,
                        "title": result.get("title", "Tavily Result"),
                        "document_type": "TAVILY_API",
                        "metadata": {
                            "url": result.get("url", ""),
                            "published_date": result.get("published_date", ""),
                            "source": "TAVILY_API"
                        }
                    }
                }
                documents.append(document)
                self.source_id_counter += 1

            # Create result object
            result_object = {
                "id": 3,
                "name": "Tavily Search",
                "type": "TAVILY_API",
                "sources": sources_list,
            }
            
            return result_object, documents
            
        except Exception as e:
            # Log the error and return empty results
            print(f"Error searching with Tavily: {str(e)}")
            return {
                "id": 3,
                "name": "Tavily Search",
                "type": "TAVILY_API",
                "sources": [],
            }, []
    
    async def search_slack(self, user_query: str, user_id: str, search_space_id: int, top_k: int = 20) -> tuple:
        """
        Search for slack and return both the source information and langchain documents
        
        Returns:
            tuple: (sources_info, langchain_documents)
        """
        slack_chunks = await self.retriever.hybrid_search(
            query_text=user_query,
            top_k=top_k,
            user_id=user_id,
            search_space_id=search_space_id,
            document_type="SLACK_CONNECTOR"
        )

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        for i, chunk in enumerate(slack_chunks):
            # Fix for UI
            slack_chunks[i]['document']['id'] = self.source_id_counter
            # Extract document metadata
            document = chunk.get('document', {})
            metadata = document.get('metadata', {})

            # Create a mapped source entry with Slack-specific metadata
            channel_name = metadata.get('channel_name', 'Unknown Channel')
            channel_id = metadata.get('channel_id', '')
            message_date = metadata.get('start_date', '')
            
            # Create a more descriptive title for Slack messages
            title = f"Slack: {channel_name}"
            if message_date:
                title += f" ({message_date})"
                
            # Create a more descriptive description for Slack messages
            description = chunk.get('content', '')[:100]
            if len(description) == 100:
                description += "..."
                
            # For URL, we can use a placeholder or construct a URL to the Slack channel if available
            url = ""
            if channel_id:
                url = f"https://slack.com/app_redirect?channel={channel_id}"

            source = {
                "id": self.source_id_counter,
                "title": title,
                "description": description,
                "url": url,
            }

            self.source_id_counter += 1
            sources_list.append(source)
        
        # Create result object
        result_object = {
            "id": 4,
            "name": "Slack",
            "type": "SLACK_CONNECTOR",
            "sources": sources_list,
        }
        
        return result_object, slack_chunks
        
    async def search_notion(self, user_query: str, user_id: str, search_space_id: int, top_k: int = 20) -> tuple:
        """
        Search for Notion pages and return both the source information and langchain documents
        
        Args:
            user_query: The user's query
            user_id: The user's ID
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            
        Returns:
            tuple: (sources_info, langchain_documents)
        """
        notion_chunks = await self.retriever.hybrid_search(
            query_text=user_query,
            top_k=top_k,
            user_id=user_id,
            search_space_id=search_space_id,
            document_type="NOTION_CONNECTOR"
        )

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        for i, chunk in enumerate(notion_chunks):
            # Fix for UI
            notion_chunks[i]['document']['id'] = self.source_id_counter
            
            # Extract document metadata
            document = chunk.get('document', {})
            metadata = document.get('metadata', {})

            # Create a mapped source entry with Notion-specific metadata
            page_title = metadata.get('page_title', 'Untitled Page')
            page_id = metadata.get('page_id', '')
            indexed_at = metadata.get('indexed_at', '')
            
            # Create a more descriptive title for Notion pages
            title = f"Notion: {page_title}"
            if indexed_at:
                title += f" (indexed: {indexed_at})"
                
            # Create a more descriptive description for Notion pages
            description = chunk.get('content', '')[:100]
            if len(description) == 100:
                description += "..."
                
            # For URL, we can use a placeholder or construct a URL to the Notion page if available
            url = ""
            if page_id:
                # Notion page URLs follow this format
                url = f"https://notion.so/{page_id.replace('-', '')}"

            source = {
                "id": self.source_id_counter,
                "title": title,
                "description": description,
                "url": url,
            }

            self.source_id_counter += 1
            sources_list.append(source)
        
        # Create result object
        result_object = {
            "id": 5,
            "name": "Notion",
            "type": "NOTION_CONNECTOR",
            "sources": sources_list,
        }
        
        return result_object, notion_chunks
    
    async def search_extension(self, user_query: str, user_id: str, search_space_id: int, top_k: int = 20) -> tuple:
        """
        Search for extension data and return both the source information and langchain documents
        
        Args:
            user_query: The user's query
            user_id: The user's ID
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            
        Returns:
            tuple: (sources_info, langchain_documents)
        """
        extension_chunks = await self.retriever.hybrid_search(
            query_text=user_query,
            top_k=top_k,
            user_id=user_id,
            search_space_id=search_space_id,
            document_type="EXTENSION"
        )

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        for i, chunk in enumerate(extension_chunks):
            # Fix for UI
            extension_chunks[i]['document']['id'] = self.source_id_counter
            
            # Extract document metadata
            document = chunk.get('document', {})
            metadata = document.get('metadata', {})

            # Extract extension-specific metadata
            webpage_title = metadata.get('VisitedWebPageTitle', 'Untitled Page')
            webpage_url = metadata.get('VisitedWebPageURL', '')
            visit_date = metadata.get('VisitedWebPageDateWithTimeInISOString', '')
            visit_duration = metadata.get('VisitedWebPageVisitDurationInMilliseconds', '')
            browsing_session_id = metadata.get('BrowsingSessionId', '')
            
            # Create a more descriptive title for extension data
            title = webpage_title
            if visit_date:
                # Format the date for display (simplified)
                try:
                    # Just extract the date part for display
                    formatted_date = visit_date.split('T')[0] if 'T' in visit_date else visit_date
                    title += f" (visited: {formatted_date})"
                except:
                    # Fallback if date parsing fails
                    title += f" (visited: {visit_date})"
                
            # Create a more descriptive description for extension data
            description = chunk.get('content', '')[:100]
            if len(description) == 100:
                description += "..."
                
            # Add visit duration if available
            if visit_duration:
                try:
                    duration_seconds = int(visit_duration) / 1000
                    if duration_seconds < 60:
                        duration_text = f"{duration_seconds:.1f} seconds"
                    else:
                        duration_text = f"{duration_seconds/60:.1f} minutes"
                    
                    if description:
                        description += f" | Duration: {duration_text}"
                except:
                    # Fallback if duration parsing fails
                    pass

            source = {
                "id": self.source_id_counter,
                "title": title,
                "description": description,
                "url": webpage_url
            }

            self.source_id_counter += 1
            sources_list.append(source)
        
        # Create result object
        result_object = {
            "id": 6,
            "name": "Extension",
            "type": "EXTENSION",
            "sources": sources_list,
        }
        
        return result_object, extension_chunks
    
    async def search_youtube(self, user_query: str, user_id: str, search_space_id: int, top_k: int = 20) -> tuple:
        """
        Search for YouTube videos and return both the source information and langchain documents
        
        Args:
            user_query: The user's query
            user_id: The user's ID
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            
        Returns:
            tuple: (sources_info, langchain_documents)
        """
        youtube_chunks = await self.retriever.hybrid_search(
            query_text=user_query,
            top_k=top_k,
            user_id=user_id,
            search_space_id=search_space_id,
            document_type="YOUTUBE_VIDEO"
        )

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        for i, chunk in enumerate(youtube_chunks):
            # Fix for UI
            youtube_chunks[i]['document']['id'] = self.source_id_counter
            
            # Extract document metadata
            document = chunk.get('document', {})
            metadata = document.get('metadata', {})

            # Extract YouTube-specific metadata
            video_title = metadata.get('video_title', 'Untitled Video')
            video_id = metadata.get('video_id', '')
            channel_name = metadata.get('channel_name', '')
            published_date = metadata.get('published_date', '')
            
            # Create a more descriptive title for YouTube videos
            title = video_title
            if channel_name:
                title += f" - {channel_name}"
                
            # Create a more descriptive description for YouTube videos
            description = metadata.get('description', chunk.get('content', '')[:100])
            if len(description) == 100:
                description += "..."
                
            # For URL, construct a URL to the YouTube video
            url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""

            source = {
                "id": self.source_id_counter,
                "title": title,
                "description": description,
                "url": url,
                "video_id": video_id,  # Additional field for YouTube videos
                "channel_name": channel_name  # Additional field for YouTube videos
            }

            self.source_id_counter += 1
            sources_list.append(source)
        
        # Create result object
        result_object = {
            "id": 7,  # Assign a unique ID for the YouTube connector
            "name": "YouTube Videos",
            "type": "YOUTUBE_VIDEO",
            "sources": sources_list,
        }
        
        return result_object, youtube_chunks