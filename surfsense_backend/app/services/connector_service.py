import asyncio
from typing import Any
from urllib.parse import urljoin

import httpx
from linkup import LinkupClient
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from tavily import TavilyClient

from app.agents.researcher.configuration import SearchMode
from app.db import (
    Chunk,
    Document,
    SearchSourceConnector,
    SearchSourceConnectorType,
    SearchSpace,
)
from app.retriver.chunks_hybrid_search import ChucksHybridSearchRetriever
from app.retriver.documents_hybrid_search import DocumentHybridSearchRetriever


class ConnectorService:
    def __init__(self, session: AsyncSession, user_id: str | None = None):
        self.session = session
        self.chunk_retriever = ChucksHybridSearchRetriever(session)
        self.document_retriever = DocumentHybridSearchRetriever(session)
        self.user_id = user_id
        self.source_id_counter = (
            100000  # High starting value to avoid collisions with existing IDs
        )
        self.counter_lock = (
            asyncio.Lock()
        )  # Lock to protect counter in multithreaded environments

    async def initialize_counter(self):
        """
        Initialize the source_id_counter based on the total number of chunks for the user.
        This ensures unique IDs across different sessions.
        """
        if self.user_id:
            try:
                # Count total chunks for documents belonging to this user

                result = await self.session.execute(
                    select(func.count(Chunk.id))
                    .join(Document)
                    .join(SearchSpace)
                    .filter(SearchSpace.user_id == self.user_id)
                )
                chunk_count = result.scalar() or 0
                self.source_id_counter = chunk_count + 1
                print(
                    f"Initialized source_id_counter to {self.source_id_counter} for user {self.user_id}"
                )
            except Exception as e:
                print(f"Error initializing source_id_counter: {e!s}")
                # Fallback to default value
                self.source_id_counter = 1

    async def search_crawled_urls(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        top_k: int = 20,
        search_mode: SearchMode = SearchMode.CHUNKS,
    ) -> tuple:
        """
        Search for crawled URLs and return both the source information and langchain documents

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        if search_mode == SearchMode.CHUNKS:
            crawled_urls_chunks = await self.chunk_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="CRAWLED_URL",
            )
        elif search_mode == SearchMode.DOCUMENTS:
            crawled_urls_chunks = await self.document_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="CRAWLED_URL",
            )
            # Transform document retriever results to match expected format
            crawled_urls_chunks = self._transform_document_results(crawled_urls_chunks)

        # Early return if no results
        if not crawled_urls_chunks:
            return {
                "id": 1,
                "name": "Crawled URLs",
                "type": "CRAWLED_URL",
                "sources": [],
            }, []

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        async with self.counter_lock:
            for _i, chunk in enumerate(crawled_urls_chunks):
                # Extract document metadata
                document = chunk.get("document", {})
                metadata = document.get("metadata", {})

                # Create a source entry
                source = {
                    "id": chunk.get("chunk_id", self.source_id_counter),
                    "title": document.get("title", "Untitled Document"),
                    "description": metadata.get(
                        "og:description",
                        metadata.get("ogDescription", chunk.get("content", "")),
                    ),
                    "url": metadata.get("url", ""),
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

    async def search_files(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        top_k: int = 20,
        search_mode: SearchMode = SearchMode.CHUNKS,
    ) -> tuple:
        """
        Search for files and return both the source information and langchain documents

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        if search_mode == SearchMode.CHUNKS:
            files_chunks = await self.chunk_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="FILE",
            )
        elif search_mode == SearchMode.DOCUMENTS:
            files_chunks = await self.document_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="FILE",
            )
            # Transform document retriever results to match expected format
            files_chunks = self._transform_document_results(files_chunks)

        # Early return if no results
        if not files_chunks:
            return {
                "id": 2,
                "name": "Files",
                "type": "FILE",
                "sources": [],
            }, []

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        async with self.counter_lock:
            for _i, chunk in enumerate(files_chunks):
                # Extract document metadata
                document = chunk.get("document", {})
                metadata = document.get("metadata", {})

                # Create a source entry
                source = {
                    "id": chunk.get("chunk_id", self.source_id_counter),
                    "title": document.get("title", "Untitled Document"),
                    "description": metadata.get(
                        "og:description",
                        metadata.get("ogDescription", chunk.get("content", "")),
                    ),
                    "url": metadata.get("url", ""),
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

    def _transform_document_results(
        self, document_results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Transform results from document_retriever.hybrid_search() to match the format
        expected by the processing code.

        Args:
            document_results: Results from document_retriever.hybrid_search()

        Returns:
            List of transformed results in the format expected by the processing code
        """
        transformed_results = []
        for doc in document_results:
            transformed_results.append(
                {
                    "chunk_id": doc.get("document_id"),
                    "document": {
                        "id": doc.get("document_id"),
                        "title": doc.get("title", "Untitled Document"),
                        "document_type": doc.get("document_type"),
                        "metadata": doc.get("metadata", {}),
                    },
                    "content": doc.get("chunks_content", doc.get("content", "")),
                    "score": doc.get("score", 0.0),
                }
            )
        return transformed_results

    async def get_connector_by_type(
        self,
        user_id: str,
        connector_type: SearchSourceConnectorType,
        search_space_id: int | None = None,
    ) -> SearchSourceConnector | None:
        """
        Get a connector by type for a specific user and optionally a search space

        Args:
            user_id: The user's ID
            connector_type: The connector type to retrieve
            search_space_id: Optional search space ID to filter by

        Returns:
            Optional[SearchSourceConnector]: The connector if found, None otherwise
        """
        query = select(SearchSourceConnector).filter(
            SearchSourceConnector.user_id == user_id,
            SearchSourceConnector.connector_type == connector_type,
        )

        if search_space_id is not None:
            query = query.filter(
                SearchSourceConnector.search_space_id == search_space_id
            )

        result = await self.session.execute(query)
        return result.scalars().first()

    async def search_tavily(
        self, user_query: str, user_id: str, search_space_id: int, top_k: int = 20
    ) -> tuple:
        """
        Search using Tavily API and return both the source information and documents

        Args:
            user_query: The user's query
            user_id: The user's ID
            search_space_id: The search space ID
            top_k: Maximum number of results to return

        Returns:
            tuple: (sources_info, documents)
        """
        # Get Tavily connector configuration
        tavily_connector = await self.get_connector_by_type(
            user_id, SearchSourceConnectorType.TAVILY_API, search_space_id
        )

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
                search_depth="advanced",  # Use advanced search for better results
            )

            # Extract results from Tavily response
            tavily_results = response.get("results", [])

            # Early return if no results
            if not tavily_results:
                return {
                    "id": 3,
                    "name": "Tavily Search",
                    "type": "TAVILY_API",
                    "sources": [],
                }, []

            # Process each result and create sources directly without deduplication
            sources_list = []
            documents = []

            async with self.counter_lock:
                for _i, result in enumerate(tavily_results):
                    # Create a source entry
                    source = {
                        "id": self.source_id_counter,
                        "title": result.get("title", "Tavily Result"),
                        "description": result.get("content", ""),
                        "url": result.get("url", ""),
                    }
                    sources_list.append(source)

                    # Create a document entry
                    document = {
                        "chunk_id": self.source_id_counter,
                        "content": result.get("content", ""),
                        "score": result.get("score", 0.0),
                        "document": {
                            "id": self.source_id_counter,
                            "title": result.get("title", "Tavily Result"),
                            "document_type": "TAVILY_API",
                            "metadata": {
                                "url": result.get("url", ""),
                                "published_date": result.get("published_date", ""),
                                "source": "TAVILY_API",
                            },
                        },
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
            print(f"Error searching with Tavily: {e!s}")
            return {
                "id": 3,
                "name": "Tavily Search",
                "type": "TAVILY_API",
                "sources": [],
            }, []

    async def search_searxng(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        top_k: int = 20,
    ) -> tuple:
        """
        Search using a configured SearxNG instance and return both sources and documents.
        """
        searx_connector = await self.get_connector_by_type(
            user_id, SearchSourceConnectorType.SEARXNG_API, search_space_id
        )

        if not searx_connector:
            return {
                "id": 11,
                "name": "SearxNG Search",
                "type": "SEARXNG_API",
                "sources": [],
            }, []

        config = searx_connector.config or {}
        host = config.get("SEARXNG_HOST")

        if not host:
            print("SearxNG connector is missing SEARXNG_HOST configuration")
            return {
                "id": 11,
                "name": "SearxNG Search",
                "type": "SEARXNG_API",
                "sources": [],
            }, []

        api_key = config.get("SEARXNG_API_KEY")
        engines = config.get("SEARXNG_ENGINES")
        categories = config.get("SEARXNG_CATEGORIES")
        language = config.get("SEARXNG_LANGUAGE")
        safesearch = config.get("SEARXNG_SAFESEARCH")

        def _parse_bool(value: Any, default: bool = True) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"true", "1", "yes", "on"}:
                    return True
                if lowered in {"false", "0", "no", "off"}:
                    return False
            return default

        verify_ssl = _parse_bool(config.get("SEARXNG_VERIFY_SSL", True))

        safesearch_value: int | None = None
        if isinstance(safesearch, str):
            safesearch_clean = safesearch.strip()
            if safesearch_clean.isdigit():
                safesearch_value = int(safesearch_clean)
        elif isinstance(safesearch, int | float):
            safesearch_value = int(safesearch)

        if safesearch_value is not None and not (0 <= safesearch_value <= 2):
            safesearch_value = None

        def _format_list(value: Any) -> str | None:
            if value is None:
                return None
            if isinstance(value, str):
                value = value.strip()
                return value or None
            if isinstance(value, list | tuple | set):
                cleaned = [str(item).strip() for item in value if str(item).strip()]
                return ",".join(cleaned) if cleaned else None
            return str(value)

        params: dict[str, Any] = {
            "q": user_query,
            "format": "json",
            "language": language or "",
            "limit": max(1, min(top_k, 50)),
        }

        engines_param = _format_list(engines)
        if engines_param:
            params["engines"] = engines_param

        categories_param = _format_list(categories)
        if categories_param:
            params["categories"] = categories_param

        if safesearch_value is not None:
            params["safesearch"] = safesearch_value

        if not params.get("language"):
            params.pop("language")

        headers = {"Accept": "application/json"}
        if api_key:
            headers["X-API-KEY"] = api_key

        searx_endpoint = urljoin(host if host.endswith("/") else f"{host}/", "search")

        try:
            async with httpx.AsyncClient(timeout=20.0, verify=verify_ssl) as client:
                response = await client.get(
                    searx_endpoint,
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"Error searching with SearxNG: {exc!s}")
            return {
                "id": 11,
                "name": "SearxNG Search",
                "type": "SEARXNG_API",
                "sources": [],
            }, []

        try:
            data = response.json()
        except ValueError:
            print("Failed to decode JSON response from SearxNG")
            return {
                "id": 11,
                "name": "SearxNG Search",
                "type": "SEARXNG_API",
                "sources": [],
            }, []

        searx_results = data.get("results", [])
        if not searx_results:
            return {
                "id": 11,
                "name": "SearxNG Search",
                "type": "SEARXNG_API",
                "sources": [],
            }, []

        sources_list: list[dict[str, Any]] = []
        documents: list[dict[str, Any]] = []

        async with self.counter_lock:
            for result in searx_results:
                description = result.get("content") or result.get("snippet") or ""
                if len(description) > 160:
                    description = f"{description}"

                source = {
                    "id": self.source_id_counter,
                    "title": result.get("title", "SearxNG Result"),
                    "description": description,
                    "url": result.get("url", ""),
                }
                sources_list.append(source)

                metadata = {
                    "url": result.get("url", ""),
                    "engines": result.get("engines", []),
                    "category": result.get("category"),
                    "source": "SEARXNG_API",
                }

                document = {
                    "chunk_id": self.source_id_counter,
                    "content": description or result.get("content", ""),
                    "score": result.get("score", 0.0),
                    "document": {
                        "id": self.source_id_counter,
                        "title": result.get("title", "SearxNG Result"),
                        "document_type": "SEARXNG_API",
                        "metadata": metadata,
                    },
                }
                documents.append(document)
                self.source_id_counter += 1

        result_object = {
            "id": 11,
            "name": "SearxNG Search",
            "type": "SEARXNG_API",
            "sources": sources_list,
        }

        return result_object, documents

    async def search_baidu(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        top_k: int = 20,
    ) -> tuple:
        """
        Search using Baidu AI Search API and return both sources and documents.

        Baidu AI Search provides intelligent search with automatic summarization.
        We extract the raw search results (references) from the API response.

        Args:
            user_query: User's search query
            user_id: User ID
            search_space_id: Search space ID
            top_k: Maximum number of results to return

        Returns:
            tuple: (sources_info_dict, documents_list)
        """
        # Get Baidu connector configuration
        baidu_connector = await self.get_connector_by_type(
            user_id, SearchSourceConnectorType.BAIDU_SEARCH_API, search_space_id
        )

        if not baidu_connector:
            return {
                "id": 12,
                "name": "Baidu Search",
                "type": "BAIDU_SEARCH_API",
                "sources": [],
            }, []

        config = baidu_connector.config or {}
        api_key = config.get("BAIDU_API_KEY")

        if not api_key:
            print("ERROR: Baidu connector is missing BAIDU_API_KEY configuration")
            print(f"Connector config: {config}")
            return {
                "id": 12,
                "name": "Baidu Search",
                "type": "BAIDU_SEARCH_API",
                "sources": [],
            }, []

        # Optional configuration parameters
        model = config.get("BAIDU_MODEL", "ernie-3.5-8k")
        search_source = config.get("BAIDU_SEARCH_SOURCE", "baidu_search_v2")
        enable_deep_search = config.get("BAIDU_ENABLE_DEEP_SEARCH", False)

        # Baidu AI Search API endpoint
        baidu_endpoint = "https://qianfan.baidubce.com/v2/ai_search/chat/completions"

        # Prepare request headers
        # Note: Baidu uses X-Appbuilder-Authorization instead of standard Authorization header
        headers = {
            "X-Appbuilder-Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Prepare request payload
        # Calculate resource_type_filter top_k values
        # Baidu v2 supports max 20 per type
        max_per_type = min(top_k, 20)

        payload = {
            "messages": [{"role": "user", "content": user_query}],
            "model": model,
            "search_source": search_source,
            "resource_type_filter": [
                {"type": "web", "top_k": max_per_type},
                {"type": "video", "top_k": max(1, max_per_type // 4)},  # Fewer videos
            ],
            "stream": False,  # Non-streaming for simpler processing
            "enable_deep_search": enable_deep_search,
            "enable_corner_markers": True,  # Enable reference markers
        }

        try:
            # Baidu AI Search may take longer as it performs search + summarization
            # Increase timeout to 90 seconds
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    baidu_endpoint,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            print(f"ERROR: Baidu API request timeout after 90s: {exc!r}")
            print(f"Endpoint: {baidu_endpoint}")
            return {
                "id": 12,
                "name": "Baidu Search",
                "type": "BAIDU_SEARCH_API",
                "sources": [],
            }, []
        except httpx.HTTPStatusError as exc:
            print(f"ERROR: Baidu API HTTP Status Error: {exc.response.status_code}")
            print(f"Response text: {exc.response.text[:500]}")
            print(f"Request URL: {exc.request.url}")
            return {
                "id": 12,
                "name": "Baidu Search",
                "type": "BAIDU_SEARCH_API",
                "sources": [],
            }, []
        except httpx.RequestError as exc:
            print(f"ERROR: Baidu API Request Error: {type(exc).__name__}: {exc!r}")
            print(f"Endpoint: {baidu_endpoint}")
            return {
                "id": 12,
                "name": "Baidu Search",
                "type": "BAIDU_SEARCH_API",
                "sources": [],
            }, []
        except Exception as exc:
            print(
                f"ERROR: Unexpected error calling Baidu API: {type(exc).__name__}: {exc!r}"
            )
            print(f"Endpoint: {baidu_endpoint}")
            print(f"Payload: {payload}")
            return {
                "id": 12,
                "name": "Baidu Search",
                "type": "BAIDU_SEARCH_API",
                "sources": [],
            }, []

        try:
            data = response.json()
        except ValueError as e:
            print(f"ERROR: Failed to decode JSON response from Baidu AI Search: {e}")
            print(f"Response status: {response.status_code}")
            print(f"Response text: {response.text[:500]}")  # First 500 chars
            return {
                "id": 12,
                "name": "Baidu Search",
                "type": "BAIDU_SEARCH_API",
                "sources": [],
            }, []

        # Extract references (search results) from the response
        baidu_references = data.get("references", [])

        if "code" in data or "message" in data:
            print(
                f"WARNING: Baidu API returned error - Code: {data.get('code')}, Message: {data.get('message')}"
            )

        if not baidu_references:
            print("WARNING: No references found in Baidu API response")
            print(f"Response keys: {list(data.keys())}")
            return {
                "id": 12,
                "name": "Baidu Search",
                "type": "BAIDU_SEARCH_API",
                "sources": [],
            }, []

        sources_list: list[dict[str, Any]] = []
        documents: list[dict[str, Any]] = []

        async with self.counter_lock:
            for reference in baidu_references:
                # Extract basic fields
                title = reference.get("title", "Baidu Search Result")
                url = reference.get("url", "")
                content = reference.get("content", "")
                date = reference.get("date", "")
                ref_type = reference.get("type", "web")  # web, image, video

                # Create a source entry
                source = {
                    "id": self.source_id_counter,
                    "title": title,
                    "description": content[:300]
                    if content
                    else "",  # Limit description length
                    "url": url,
                }
                sources_list.append(source)

                # Prepare metadata
                metadata = {
                    "url": url,
                    "date": date,
                    "type": ref_type,
                    "source": "BAIDU_SEARCH_API",
                    "web_anchor": reference.get("web_anchor", ""),
                    "website": reference.get("website", ""),
                }

                # Add type-specific metadata
                if ref_type == "image" and reference.get("image"):
                    metadata["image"] = reference["image"]
                elif ref_type == "video" and reference.get("video"):
                    metadata["video"] = reference["video"]

                # Create a document entry
                document = {
                    "chunk_id": self.source_id_counter,
                    "content": content,
                    "score": 1.0,  # Baidu doesn't provide relevance scores
                    "document": {
                        "id": self.source_id_counter,
                        "title": title,
                        "document_type": "BAIDU_SEARCH_API",
                        "metadata": metadata,
                    },
                }
                documents.append(document)
                self.source_id_counter += 1

        result_object = {
            "id": 12,
            "name": "Baidu Search",
            "type": "BAIDU_SEARCH_API",
            "sources": sources_list,
        }

        return result_object, documents

    async def search_slack(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        top_k: int = 20,
        search_mode: SearchMode = SearchMode.CHUNKS,
    ) -> tuple:
        """
        Search for slack and return both the source information and langchain documents

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        if search_mode == SearchMode.CHUNKS:
            slack_chunks = await self.chunk_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="SLACK_CONNECTOR",
            )
        elif search_mode == SearchMode.DOCUMENTS:
            slack_chunks = await self.document_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="SLACK_CONNECTOR",
            )
            # Transform document retriever results to match expected format
            slack_chunks = self._transform_document_results(slack_chunks)

        # Early return if no results
        if not slack_chunks:
            return {
                "id": 4,
                "name": "Slack",
                "type": "SLACK_CONNECTOR",
                "sources": [],
            }, []

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        async with self.counter_lock:
            for _i, chunk in enumerate(slack_chunks):
                # Extract document metadata
                document = chunk.get("document", {})
                metadata = document.get("metadata", {})

                # Create a mapped source entry with Slack-specific metadata
                channel_name = metadata.get("channel_name", "Unknown Channel")
                channel_id = metadata.get("channel_id", "")
                message_date = metadata.get("start_date", "")

                # Create a more descriptive title for Slack messages
                title = f"Slack: {channel_name}"
                if message_date:
                    title += f" ({message_date})"

                # Create a more descriptive description for Slack messages
                description = chunk.get("content", "")

                # For URL, we can use a placeholder or construct a URL to the Slack channel if available
                url = ""
                if channel_id:
                    url = f"https://slack.com/app_redirect?channel={channel_id}"

                source = {
                    "id": chunk.get("chunk_id", self.source_id_counter),
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

    async def search_notion(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        top_k: int = 20,
        search_mode: SearchMode = SearchMode.CHUNKS,
    ) -> tuple:
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
        if search_mode == SearchMode.CHUNKS:
            notion_chunks = await self.chunk_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="NOTION_CONNECTOR",
            )
        elif search_mode == SearchMode.DOCUMENTS:
            notion_chunks = await self.document_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="NOTION_CONNECTOR",
            )
            # Transform document retriever results to match expected format
            notion_chunks = self._transform_document_results(notion_chunks)

        # Early return if no results
        if not notion_chunks:
            return {
                "id": 5,
                "name": "Notion",
                "type": "NOTION_CONNECTOR",
                "sources": [],
            }, []

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        async with self.counter_lock:
            for _i, chunk in enumerate(notion_chunks):
                # Extract document metadata
                document = chunk.get("document", {})
                metadata = document.get("metadata", {})

                # Create a mapped source entry with Notion-specific metadata
                page_title = metadata.get("page_title", "Untitled Page")
                page_id = metadata.get("page_id", "")
                indexed_at = metadata.get("indexed_at", "")

                # Create a more descriptive title for Notion pages
                title = f"Notion: {page_title}"
                if indexed_at:
                    title += f" (indexed: {indexed_at})"

                # Create a more descriptive description for Notion pages
                description = chunk.get("content", "")
                if len(description) == 100:
                    description += "..."

                # For URL, we can use a placeholder or construct a URL to the Notion page if available
                url = ""
                if page_id:
                    # Notion page URLs follow this format
                    url = f"https://notion.so/{page_id.replace('-', '')}"

                source = {
                    "id": chunk.get("chunk_id", self.source_id_counter),
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

    async def search_extension(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        top_k: int = 20,
        search_mode: SearchMode = SearchMode.CHUNKS,
    ) -> tuple:
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
        if search_mode == SearchMode.CHUNKS:
            extension_chunks = await self.chunk_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="EXTENSION",
            )
        elif search_mode == SearchMode.DOCUMENTS:
            extension_chunks = await self.document_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="EXTENSION",
            )
            # Transform document retriever results to match expected format
            extension_chunks = self._transform_document_results(extension_chunks)

        # Early return if no results
        if not extension_chunks:
            return {
                "id": 6,
                "name": "Extension",
                "type": "EXTENSION",
                "sources": [],
            }, []

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        async with self.counter_lock:
            for _, chunk in enumerate(extension_chunks):
                # Extract document metadata
                document = chunk.get("document", {})
                metadata = document.get("metadata", {})

                # Extract extension-specific metadata
                webpage_title = metadata.get("VisitedWebPageTitle", "Untitled Page")
                webpage_url = metadata.get("VisitedWebPageURL", "")
                visit_date = metadata.get("VisitedWebPageDateWithTimeInISOString", "")
                visit_duration = metadata.get(
                    "VisitedWebPageVisitDurationInMilliseconds", ""
                )
                _browsing_session_id = metadata.get("BrowsingSessionId", "")

                # Create a more descriptive title for extension data
                title = webpage_title
                if visit_date:
                    # Format the date for display (simplified)
                    try:
                        # Just extract the date part for display
                        formatted_date = (
                            visit_date.split("T")[0]
                            if "T" in visit_date
                            else visit_date
                        )
                        title += f" (visited: {formatted_date})"
                    except Exception:
                        # Fallback if date parsing fails
                        title += f" (visited: {visit_date})"

                # Create a more descriptive description for extension data
                description = chunk.get("content", "")
                if len(description) == 100:
                    description += "..."

                # Add visit duration if available
                if visit_duration:
                    try:
                        duration_seconds = int(visit_duration) / 1000
                        if duration_seconds < 60:
                            duration_text = f"{duration_seconds:.1f} seconds"
                        else:
                            duration_text = f"{duration_seconds / 60:.1f} minutes"

                        if description:
                            description += f" | Duration: {duration_text}"
                    except Exception:
                        # Fallback if duration parsing fails
                        pass

                source = {
                    "id": chunk.get("chunk_id", self.source_id_counter),
                    "title": title,
                    "description": description,
                    "url": webpage_url,
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

    async def search_youtube(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        top_k: int = 20,
        search_mode: SearchMode = SearchMode.CHUNKS,
    ) -> tuple:
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
        if search_mode == SearchMode.CHUNKS:
            youtube_chunks = await self.chunk_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="YOUTUBE_VIDEO",
            )
        elif search_mode == SearchMode.DOCUMENTS:
            youtube_chunks = await self.document_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="YOUTUBE_VIDEO",
            )
            # Transform document retriever results to match expected format
            youtube_chunks = self._transform_document_results(youtube_chunks)

        # Early return if no results
        if not youtube_chunks:
            return {
                "id": 7,
                "name": "YouTube Videos",
                "type": "YOUTUBE_VIDEO",
                "sources": [],
            }, []

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        async with self.counter_lock:
            for _i, chunk in enumerate(youtube_chunks):
                # Extract document metadata
                document = chunk.get("document", {})
                metadata = document.get("metadata", {})

                # Extract YouTube-specific metadata
                video_title = metadata.get("video_title", "Untitled Video")
                video_id = metadata.get("video_id", "")
                channel_name = metadata.get("channel_name", "")
                # published_date = metadata.get('published_date', '')

                # Create a more descriptive title for YouTube videos
                title = video_title
                if channel_name:
                    title += f" - {channel_name}"

                # Create a more descriptive description for YouTube videos
                description = metadata.get("description", chunk.get("content", ""))
                if len(description) == 100:
                    description += "..."

                # For URL, construct a URL to the YouTube video
                url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""

                source = {
                    "id": chunk.get("chunk_id", self.source_id_counter),
                    "title": title,
                    "description": description,
                    "url": url,
                    "video_id": video_id,  # Additional field for YouTube videos
                    "channel_name": channel_name,  # Additional field for YouTube videos
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

    async def search_github(
        self,
        user_query: str,
        user_id: int,
        search_space_id: int,
        top_k: int = 20,
        search_mode: SearchMode = SearchMode.CHUNKS,
    ) -> tuple:
        """
        Search for GitHub documents and return both the source information and langchain documents

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        if search_mode == SearchMode.CHUNKS:
            github_chunks = await self.chunk_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="GITHUB_CONNECTOR",
            )
        elif search_mode == SearchMode.DOCUMENTS:
            github_chunks = await self.document_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="GITHUB_CONNECTOR",
            )
            # Transform document retriever results to match expected format
            github_chunks = self._transform_document_results(github_chunks)

        # Early return if no results
        if not github_chunks:
            return {
                "id": 8,
                "name": "GitHub",
                "type": "GITHUB_CONNECTOR",
                "sources": [],
            }, []

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        async with self.counter_lock:
            for _i, chunk in enumerate(github_chunks):
                # Extract document metadata
                document = chunk.get("document", {})
                metadata = document.get("metadata", {})

                # Create a source entry
                source = {
                    "id": chunk.get("chunk_id", self.source_id_counter),
                    "title": document.get(
                        "title", "GitHub Document"
                    ),  # Use specific title if available
                    "description": metadata.get(
                        "description", chunk.get("content", "")
                    ),  # Use description or content preview
                    "url": metadata.get("url", ""),  # Use URL if available in metadata
                }

                self.source_id_counter += 1
                sources_list.append(source)

        # Create result object
        result_object = {
            "id": 8,
            "name": "GitHub",
            "type": "GITHUB_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, github_chunks

    async def search_linear(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        top_k: int = 20,
        search_mode: SearchMode = SearchMode.CHUNKS,
    ) -> tuple:
        """
        Search for Linear issues and comments and return both the source information and langchain documents

        Args:
            user_query: The user's query
            user_id: The user's ID
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        if search_mode == SearchMode.CHUNKS:
            linear_chunks = await self.chunk_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="LINEAR_CONNECTOR",
            )
        elif search_mode == SearchMode.DOCUMENTS:
            linear_chunks = await self.document_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="LINEAR_CONNECTOR",
            )
            # Transform document retriever results to match expected format
            linear_chunks = self._transform_document_results(linear_chunks)

        # Early return if no results
        if not linear_chunks:
            return {
                "id": 9,
                "name": "Linear Issues",
                "type": "LINEAR_CONNECTOR",
                "sources": [],
            }, []

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        async with self.counter_lock:
            for _i, chunk in enumerate(linear_chunks):
                # Extract document metadata
                document = chunk.get("document", {})
                metadata = document.get("metadata", {})

                # Extract Linear-specific metadata
                issue_identifier = metadata.get("issue_identifier", "")
                issue_title = metadata.get("issue_title", "Untitled Issue")
                issue_state = metadata.get("state", "")
                comment_count = metadata.get("comment_count", 0)

                # Create a more descriptive title for Linear issues
                title = f"Linear: {issue_identifier} - {issue_title}"
                if issue_state:
                    title += f" ({issue_state})"

                # Create a more descriptive description for Linear issues
                description = chunk.get("content", "")
                if len(description) == 100:
                    description += "..."

                # Add comment count info to description
                if comment_count:
                    if description:
                        description += f" | Comments: {comment_count}"
                    else:
                        description = f"Comments: {comment_count}"

                # For URL, we could construct a URL to the Linear issue if we have the workspace info
                # For now, use a generic placeholder
                url = ""
                if issue_identifier:
                    # This is a generic format, may need to be adjusted based on actual Linear workspace
                    url = f"https://linear.app/issue/{issue_identifier}"

                source = {
                    "id": chunk.get("chunk_id", self.source_id_counter),
                    "title": title,
                    "description": description,
                    "url": url,
                    "issue_identifier": issue_identifier,
                    "state": issue_state,
                    "comment_count": comment_count,
                }

                self.source_id_counter += 1
                sources_list.append(source)

        # Create result object
        result_object = {
            "id": 9,  # Assign a unique ID for the Linear connector
            "name": "Linear Issues",
            "type": "LINEAR_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, linear_chunks

    async def search_jira(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        top_k: int = 20,
        search_mode: SearchMode = SearchMode.CHUNKS,
    ) -> tuple:
        """
        Search for Jira issues and comments and return both the source information and langchain documents

        Args:
            user_query: The user's query
            user_id: The user's ID
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            search_mode: Search mode (CHUNKS or DOCUMENTS)

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        if search_mode == SearchMode.CHUNKS:
            jira_chunks = await self.chunk_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="JIRA_CONNECTOR",
            )
        elif search_mode == SearchMode.DOCUMENTS:
            jira_chunks = await self.document_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="JIRA_CONNECTOR",
            )
            # Transform document retriever results to match expected format
            jira_chunks = self._transform_document_results(jira_chunks)

        # Early return if no results
        if not jira_chunks:
            return {
                "id": 30,
                "name": "Jira Issues",
                "type": "JIRA_CONNECTOR",
                "sources": [],
            }, []

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        async with self.counter_lock:
            for _i, chunk in enumerate(jira_chunks):
                # Extract document metadata
                document = chunk.get("document", {})
                metadata = document.get("metadata", {})

                # Extract Jira-specific metadata
                issue_key = metadata.get("issue_key", "")
                issue_title = metadata.get("issue_title", "Untitled Issue")
                status = metadata.get("status", "")
                priority = metadata.get("priority", "")
                issue_type = metadata.get("issue_type", "")
                comment_count = metadata.get("comment_count", 0)

                # Create a more descriptive title for Jira issues
                title = f"Jira: {issue_key} - {issue_title}"
                if status:
                    title += f" ({status})"

                # Create a more descriptive description for Jira issues
                description = chunk.get("content", "")
                if len(description) == 100:
                    description += "..."

                # Add priority and type info to description
                info_parts = []
                if priority:
                    info_parts.append(f"Priority: {priority}")
                if issue_type:
                    info_parts.append(f"Type: {issue_type}")
                if comment_count:
                    info_parts.append(f"Comments: {comment_count}")

                if info_parts:
                    if description:
                        description += f" | {' | '.join(info_parts)}"
                    else:
                        description = " | ".join(info_parts)

                # For URL, we could construct a URL to the Jira issue if we have the base URL
                # For now, use a generic placeholder
                url = ""
                if issue_key and metadata.get("base_url"):
                    url = f"{metadata.get('base_url')}/browse/{issue_key}"

                source = {
                    "id": chunk.get("chunk_id", self.source_id_counter),
                    "title": title,
                    "description": description,
                    "url": url,
                    "issue_key": issue_key,
                    "status": status,
                    "priority": priority,
                    "issue_type": issue_type,
                    "comment_count": comment_count,
                }

                self.source_id_counter += 1
                sources_list.append(source)

        # Create result object
        result_object = {
            "id": 10,  # Assign a unique ID for the Jira connector
            "name": "Jira Issues",
            "type": "JIRA_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, jira_chunks

    async def search_google_calendar(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        top_k: int = 20,
        search_mode: SearchMode = SearchMode.CHUNKS,
    ) -> tuple:
        """
        Search for Google Calendar events and return both the source information and langchain documents

        Args:
            user_query: The user's query
            user_id: The user's ID
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            search_mode: Search mode (CHUNKS or DOCUMENTS)

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        if search_mode == SearchMode.CHUNKS:
            calendar_chunks = await self.chunk_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="GOOGLE_CALENDAR_CONNECTOR",
            )
        elif search_mode == SearchMode.DOCUMENTS:
            calendar_chunks = await self.document_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="GOOGLE_CALENDAR_CONNECTOR",
            )
            # Transform document retriever results to match expected format
            calendar_chunks = self._transform_document_results(calendar_chunks)

        # Early return if no results
        if not calendar_chunks:
            return {
                "id": 31,
                "name": "Google Calendar Events",
                "type": "GOOGLE_CALENDAR_CONNECTOR",
                "sources": [],
            }, []

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        async with self.counter_lock:
            for _i, chunk in enumerate(calendar_chunks):
                # Extract document metadata
                document = chunk.get("document", {})
                metadata = document.get("metadata", {})

                # Extract Google Calendar-specific metadata
                event_id = metadata.get("event_id", "")
                event_summary = metadata.get("event_summary", "Untitled Event")
                calendar_id = metadata.get("calendar_id", "")
                start_time = metadata.get("start_time", "")
                end_time = metadata.get("end_time", "")
                location = metadata.get("location", "")

                # Create a more descriptive title for calendar events
                title = f"Calendar: {event_summary}"
                if start_time:
                    # Format the start time for display
                    try:
                        if "T" in start_time:
                            from datetime import datetime

                            start_dt = datetime.fromisoformat(
                                start_time.replace("Z", "+00:00")
                            )
                            formatted_time = start_dt.strftime("%Y-%m-%d %H:%M")
                            title += f" ({formatted_time})"
                        else:
                            title += f" ({start_time})"
                    except Exception:
                        title += f" ({start_time})"

                # Create a more descriptive description for calendar events
                description = chunk.get("content", "")

                # Add event info to description
                info_parts = []
                if location:
                    info_parts.append(f"Location: {location}")
                if calendar_id and calendar_id != "primary":
                    info_parts.append(f"Calendar: {calendar_id}")
                if end_time:
                    info_parts.append(f"End: {end_time}")

                if info_parts:
                    if description:
                        description += f" | {' | '.join(info_parts)}"
                    else:
                        description = " | ".join(info_parts)

                # For URL, we could construct a URL to the Google Calendar event
                url = ""
                if event_id and calendar_id:
                    # Google Calendar event URL format
                    url = f"https://calendar.google.com/calendar/event?eid={event_id}"

                source = {
                    "id": chunk.get("chunk_id", self.source_id_counter),
                    "title": title,
                    "description": description,
                    "url": url,
                    "event_id": event_id,
                    "event_summary": event_summary,
                    "calendar_id": calendar_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "location": location,
                }

                self.source_id_counter += 1
                sources_list.append(source)

        # Create result object
        result_object = {
            "id": 31,  # Assign a unique ID for the Google Calendar connector
            "name": "Google Calendar Events",
            "type": "GOOGLE_CALENDAR_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, calendar_chunks

    async def search_airtable(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        top_k: int = 20,
        search_mode: SearchMode = SearchMode.CHUNKS,
    ) -> tuple:
        """
        Search for Airtable records and return both the source information and langchain documents

        Args:
            user_query: The user's query
            user_id: The user's ID
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            search_mode: Search mode (CHUNKS or DOCUMENTS)

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        if search_mode == SearchMode.CHUNKS:
            airtable_chunks = await self.chunk_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="AIRTABLE_CONNECTOR",
            )
        elif search_mode == SearchMode.DOCUMENTS:
            airtable_chunks = await self.document_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="AIRTABLE_CONNECTOR",
            )
            # Transform document retriever results to match expected format
            airtable_chunks = self._transform_document_results(airtable_chunks)

        # Early return if no results
        if not airtable_chunks:
            return {
                "id": 32,
                "name": "Airtable Records",
                "type": "AIRTABLE_CONNECTOR",
                "sources": [],
            }, []

        # Process chunks to create sources
        sources_list = []
        async with self.counter_lock:
            for _i, chunk in enumerate(airtable_chunks):
                # Extract document metadata
                document = chunk.get("document", {})
                metadata = document.get("metadata", {})

                # Extract Airtable-specific metadata
                record_id = metadata.get("record_id", "")
                created_time = metadata.get("created_time", "")

                # Create a more descriptive title for Airtable records
                title = f"Airtable Record: {record_id}"

                # Create a more descriptive description for Airtable records
                description = f"Created: {created_time}"

                source = {
                    "id": chunk.get("chunk_id", self.source_id_counter),
                    "title": title,
                    "description": description,
                    "url": "",  # TODO: Add URL to Airtable record
                    "record_id": record_id,
                    "created_time": created_time,
                }

                self.source_id_counter += 1
                sources_list.append(source)

        result_object = {
            "id": 32,
            "name": "Airtable Records",
            "type": "AIRTABLE_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, airtable_chunks

    async def search_google_gmail(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        top_k: int = 20,
        search_mode: SearchMode = SearchMode.CHUNKS,
    ) -> tuple:
        """
        Search for Gmail messages and return both the source information and langchain documents

        Args:
            user_query: The user's query
            user_id: The user's ID
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            search_mode: Search mode (CHUNKS or DOCUMENTS)

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        if search_mode == SearchMode.CHUNKS:
            gmail_chunks = await self.chunk_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="GOOGLE_GMAIL_CONNECTOR",
            )
        elif search_mode == SearchMode.DOCUMENTS:
            gmail_chunks = await self.document_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="GOOGLE_GMAIL_CONNECTOR",
            )
            # Transform document retriever results to match expected format
            gmail_chunks = self._transform_document_results(gmail_chunks)

        # Early return if no results
        if not gmail_chunks:
            return {
                "id": 32,
                "name": "Gmail Messages",
                "type": "GOOGLE_GMAIL_CONNECTOR",
                "sources": [],
            }, []

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        async with self.counter_lock:
            for _i, chunk in enumerate(gmail_chunks):
                # Extract document metadata
                document = chunk.get("document", {})
                metadata = document.get("metadata", {})

                # Extract Gmail-specific metadata
                message_id = metadata.get("message_id", "")
                subject = metadata.get("subject", "No Subject")
                sender = metadata.get("sender", "Unknown Sender")
                date_str = metadata.get("date", "")
                thread_id = metadata.get("thread_id", "")

                # Create a more descriptive title for Gmail messages
                title = f"Email: {subject}"
                if sender:
                    # Extract just the email address or name from sender
                    import re

                    sender_match = re.search(r"<([^>]+)>", sender)
                    if sender_match:
                        sender_email = sender_match.group(1)
                        title += f" (from {sender_email})"
                    else:
                        title += f" (from {sender})"

                # Create a more descriptive description for Gmail messages
                description = chunk.get("content", "")

                # Add message info to description
                info_parts = []
                if date_str:
                    info_parts.append(f"Date: {date_str}")
                if thread_id:
                    info_parts.append(f"Thread: {thread_id}")

                if info_parts:
                    if description:
                        description += f" | {' | '.join(info_parts)}"
                    else:
                        description = " | ".join(info_parts)

                # For URL, we could construct a URL to the Gmail message
                url = ""
                if message_id:
                    # Gmail message URL format
                    url = f"https://mail.google.com/mail/u/0/#inbox/{message_id}"

                source = {
                    "id": chunk.get("chunk_id", self.source_id_counter),
                    "title": title,
                    "description": description,
                    "url": url,
                    "message_id": message_id,
                    "subject": subject,
                    "sender": sender,
                    "date": date_str,
                    "thread_id": thread_id,
                }

                self.source_id_counter += 1
                sources_list.append(source)

        # Create result object
        result_object = {
            "id": 32,  # Assign a unique ID for the Gmail connector
            "name": "Gmail Messages",
            "type": "GOOGLE_GMAIL_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, gmail_chunks

    async def search_confluence(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        top_k: int = 20,
        search_mode: SearchMode = SearchMode.CHUNKS,
    ) -> tuple:
        """
        Search for Confluence pages and return both the source information and langchain documents

        Args:
            user_query: The user's query
            user_id: The user's ID
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            search_mode: Search mode (CHUNKS or DOCUMENTS)

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        if search_mode == SearchMode.CHUNKS:
            confluence_chunks = await self.chunk_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="CONFLUENCE_CONNECTOR",
            )
        elif search_mode == SearchMode.DOCUMENTS:
            confluence_chunks = await self.document_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="CONFLUENCE_CONNECTOR",
            )
            # Transform document retriever results to match expected format
            confluence_chunks = self._transform_document_results(confluence_chunks)

        # Early return if no results
        if not confluence_chunks:
            return {
                "id": 40,
                "name": "Confluence",
                "type": "CONFLUENCE_CONNECTOR",
                "sources": [],
            }, []

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        async with self.counter_lock:
            for _i, chunk in enumerate(confluence_chunks):
                # Extract document metadata
                document = chunk.get("document", {})
                metadata = document.get("metadata", {})

                # Extract Confluence-specific metadata
                page_title = metadata.get("page_title", "Untitled Page")
                page_id = metadata.get("page_id", "")
                space_key = metadata.get("space_key", "")

                # Create a more descriptive title for Confluence pages
                title = f"Confluence: {page_title}"
                if space_key:
                    title += f" ({space_key})"

                # Create a more descriptive description for Confluence pages
                description = chunk.get("content", "")

                # For URL, we can use a placeholder or construct a URL to the Confluence page if available
                url = ""  # TODO: Add base_url to metadata
                if page_id:
                    url = f"{metadata.get('base_url')}/pages/{page_id}"

                source = {
                    "id": chunk.get("chunk_id", self.source_id_counter),
                    "title": title,
                    "description": description,
                    "url": url,
                }

                self.source_id_counter += 1
                sources_list.append(source)

        # Create result object
        result_object = {
            "id": 40,
            "name": "Confluence",
            "type": "CONFLUENCE_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, confluence_chunks

    async def search_clickup(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        top_k: int = 20,
        search_mode: SearchMode = SearchMode.CHUNKS,
    ) -> tuple:
        """
        Search for ClickUp tasks and return both the source information and langchain documents

        Args:
            user_query: The user's query
            user_id: The user's ID
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            search_mode: Search mode (CHUNKS or DOCUMENTS)

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        if search_mode == SearchMode.CHUNKS:
            clickup_chunks = await self.chunk_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="CLICKUP_CONNECTOR",
            )
        elif search_mode == SearchMode.DOCUMENTS:
            clickup_chunks = await self.document_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="CLICKUP_CONNECTOR",
            )
            # Transform document retriever results to match expected format
            clickup_chunks = self._transform_document_results(clickup_chunks)

        # Early return if no results
        if not clickup_chunks:
            return {
                "id": 31,
                "name": "ClickUp Tasks",
                "type": "CLICKUP_CONNECTOR",
                "sources": [],
            }, []

        sources_list = []

        for chunk in clickup_chunks:
            # Extract document metadata
            document = chunk.get("document", {})
            metadata = document.get("metadata", {})

            # Extract ClickUp task information from metadata
            task_name = metadata.get("task_name", "Unknown Task")
            task_id = metadata.get("task_id", "")
            task_url = metadata.get("task_url", "")
            task_status = metadata.get("task_status", "Unknown")
            task_priority = metadata.get("task_priority", "Unknown")
            task_assignees = metadata.get("task_assignees", [])
            task_due_date = metadata.get("task_due_date", "")
            task_list_name = metadata.get("task_list_name", "")
            task_space_name = metadata.get("task_space_name", "")

            # Create description from task details
            description_parts = []
            if task_status:
                description_parts.append(f"Status: {task_status}")
            if task_priority:
                description_parts.append(f"Priority: {task_priority}")
            if task_assignees:
                assignee_names = [
                    assignee.get("username", "Unknown") for assignee in task_assignees
                ]
                description_parts.append(f"Assignees: {', '.join(assignee_names)}")
            if task_due_date:
                description_parts.append(f"Due: {task_due_date}")
            if task_list_name:
                description_parts.append(f"List: {task_list_name}")
            if task_space_name:
                description_parts.append(f"Space: {task_space_name}")

            description = (
                " | ".join(description_parts) if description_parts else "ClickUp Task"
            )

            source = {
                "id": chunk.get("chunk_id", self.source_id_counter),
                "title": task_name,
                "description": description,
                "url": task_url,
                "task_id": task_id,
                "status": task_status,
                "priority": task_priority,
                "assignees": task_assignees,
                "due_date": task_due_date,
                "list_name": task_list_name,
                "space_name": task_space_name,
            }

            self.source_id_counter += 1
            sources_list.append(source)

        # Create result object
        result_object = {
            "id": 31,  # Assign a unique ID for the ClickUp connector
            "name": "ClickUp Tasks",
            "type": "CLICKUP_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, clickup_chunks

    async def search_linkup(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        mode: str = "standard",
    ) -> tuple:
        """
        Search using Linkup API and return both the source information and documents

        Args:
            user_query: The user's query
            user_id: The user's ID
            search_space_id: The search space ID
            mode: Search depth mode, can be "standard" or "deep"

        Returns:
            tuple: (sources_info, documents)
        """
        # Get Linkup connector configuration
        linkup_connector = await self.get_connector_by_type(
            user_id, SearchSourceConnectorType.LINKUP_API, search_space_id
        )

        if not linkup_connector:
            # Return empty results if no Linkup connector is configured
            return {
                "id": 10,
                "name": "Linkup Search",
                "type": "LINKUP_API",
                "sources": [],
            }, []

        # Initialize Linkup client with API key from connector config
        linkup_api_key = linkup_connector.config.get("LINKUP_API_KEY")
        linkup_client = LinkupClient(api_key=linkup_api_key)

        # Perform search with Linkup
        try:
            response = linkup_client.search(
                query=user_query,
                depth=mode,  # Use the provided mode ("standard" or "deep")
                output_type="searchResults",  # Default to search results
            )

            # Extract results from Linkup response - access as attribute instead of using .get()
            linkup_results = response.results if hasattr(response, "results") else []

            # Only proceed if we have results
            if not linkup_results:
                return {
                    "id": 10,
                    "name": "Linkup Search",
                    "type": "LINKUP_API",
                    "sources": [],
                }, []

            # Process each result and create sources directly without deduplication
            sources_list = []
            documents = []

            async with self.counter_lock:
                for _i, result in enumerate(linkup_results):
                    # Only process results that have content
                    if not hasattr(result, "content") or not result.content:
                        continue

                    # Create a source entry
                    source = {
                        "id": self.source_id_counter,
                        "title": (
                            result.name if hasattr(result, "name") else "Linkup Result"
                        ),
                        "description": (
                            result.content if hasattr(result, "content") else ""
                        ),
                        "url": result.url if hasattr(result, "url") else "",
                    }
                    sources_list.append(source)

                    # Create a document entry
                    document = {
                        "chunk_id": self.source_id_counter,
                        "content": result.content if hasattr(result, "content") else "",
                        "score": 1.0,  # Default score since not provided by Linkup
                        "document": {
                            "id": self.source_id_counter,
                            "title": (
                                result.name
                                if hasattr(result, "name")
                                else "Linkup Result"
                            ),
                            "document_type": "LINKUP_API",
                            "metadata": {
                                "url": result.url if hasattr(result, "url") else "",
                                "type": result.type if hasattr(result, "type") else "",
                                "source": "LINKUP_API",
                            },
                        },
                    }
                    documents.append(document)
                    self.source_id_counter += 1

            # Create result object
            result_object = {
                "id": 10,
                "name": "Linkup Search",
                "type": "LINKUP_API",
                "sources": sources_list,
            }

            return result_object, documents

        except Exception as e:
            # Log the error and return empty results
            print(f"Error searching with Linkup: {e!s}")
            return {
                "id": 10,
                "name": "Linkup Search",
                "type": "LINKUP_API",
                "sources": [],
            }, []

    async def search_discord(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        top_k: int = 20,
        search_mode: SearchMode = SearchMode.CHUNKS,
    ) -> tuple:
        """
        Search for Discord messages and return both the source information and langchain documents

        Args:
            user_query: The user's query
            user_id: The user's ID
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        if search_mode == SearchMode.CHUNKS:
            discord_chunks = await self.chunk_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="DISCORD_CONNECTOR",
            )
        elif search_mode == SearchMode.DOCUMENTS:
            discord_chunks = await self.document_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="DISCORD_CONNECTOR",
            )
            # Transform document retriever results to match expected format
            discord_chunks = self._transform_document_results(discord_chunks)

        # Early return if no results
        if not discord_chunks:
            return {
                "id": 11,
                "name": "Discord",
                "type": "DISCORD_CONNECTOR",
                "sources": [],
            }, []

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        async with self.counter_lock:
            for _, chunk in enumerate(discord_chunks):
                # Extract document metadata
                document = chunk.get("document", {})
                metadata = document.get("metadata", {})

                # Create a mapped source entry with Discord-specific metadata
                channel_name = metadata.get("channel_name", "Unknown Channel")
                channel_id = metadata.get("channel_id", "")
                message_date = metadata.get("start_date", "")

                # Create a more descriptive title for Discord messages
                title = f"Discord: {channel_name}"
                if message_date:
                    title += f" ({message_date})"

                # Create a more descriptive description for Discord messages
                description = chunk.get("content", "")

                url = ""
                guild_id = metadata.get("guild_id", "")
                if guild_id and channel_id:
                    url = f"https://discord.com/channels/{guild_id}/{channel_id}"
                elif channel_id:
                    # Fallback for DM channels or when guild_id is not available
                    url = f"https://discord.com/channels/@me/{channel_id}"

                source = {
                    "id": chunk.get("chunk_id", self.source_id_counter),
                    "title": title,
                    "description": description,
                    "url": url,
                }

                self.source_id_counter += 1
                sources_list.append(source)

        # Create result object
        result_object = {
            "id": 11,
            "name": "Discord",
            "type": "DISCORD_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, discord_chunks

    async def search_luma(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        top_k: int = 20,
        search_mode: SearchMode = SearchMode.CHUNKS,
    ) -> tuple:
        """
        Search for Luma events and return both the source information and langchain documents

        Args:
            user_query: The user's query
            user_id: The user's ID
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            search_mode: Search mode (CHUNKS or DOCUMENTS)

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        if search_mode == SearchMode.CHUNKS:
            luma_chunks = await self.chunk_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="LUMA_CONNECTOR",
            )
        elif search_mode == SearchMode.DOCUMENTS:
            luma_chunks = await self.document_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="LUMA_CONNECTOR",
            )
            # Transform document retriever results to match expected format
            luma_chunks = self._transform_document_results(luma_chunks)

        # Early return if no results
        if not luma_chunks:
            return {
                "id": 33,
                "name": "Luma Events",
                "type": "LUMA_CONNECTOR",
                "sources": [],
            }, []

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        async with self.counter_lock:
            for _i, chunk in enumerate(luma_chunks):
                # Extract document metadata
                document = chunk.get("document", {})
                metadata = document.get("metadata", {})

                # Extract Luma-specific metadata
                event_id = metadata.get("event_id", "")
                event_name = metadata.get("event_name", "Untitled Event")
                event_url = metadata.get("event_url", "")
                start_time = metadata.get("start_time", "")
                end_time = metadata.get("end_time", "")
                location_name = metadata.get("location_name", "")
                location_address = metadata.get("location_address", "")
                meeting_url = metadata.get("meeting_url", "")
                timezone = metadata.get("timezone", "")
                visibility = metadata.get("visibility", "")

                # Create a more descriptive title for Luma events
                title = f"Luma: {event_name}"
                if start_time:
                    # Format the start time for display
                    try:
                        if "T" in start_time:
                            from datetime import datetime

                            start_dt = datetime.fromisoformat(
                                start_time.replace("Z", "+00:00")
                            )
                            formatted_time = start_dt.strftime("%Y-%m-%d %H:%M")
                            title += f" ({formatted_time})"
                        else:
                            title += f" ({start_time})"
                    except Exception:
                        title += f" ({start_time})"

                description = chunk.get("content", "")

                # Add event info to description
                info_parts = []
                if location_name:
                    info_parts.append(f"Venue: {location_name}")
                elif location_address:
                    info_parts.append(f"Location: {location_address}")

                if meeting_url:
                    info_parts.append("Online Event")

                if end_time:
                    try:
                        if "T" in end_time:
                            from datetime import datetime

                            end_dt = datetime.fromisoformat(
                                end_time.replace("Z", "+00:00")
                            )
                            formatted_end = end_dt.strftime("%Y-%m-%d %H:%M")
                            info_parts.append(f"Ends: {formatted_end}")
                        else:
                            info_parts.append(f"Ends: {end_time}")
                    except Exception:
                        info_parts.append(f"Ends: {end_time}")

                if timezone:
                    info_parts.append(f"TZ: {timezone}")

                if visibility:
                    info_parts.append(f"Visibility: {visibility.title()}")

                if info_parts:
                    if description:
                        description += f" | {' | '.join(info_parts)}"
                    else:
                        description = " | ".join(info_parts)

                # Use the Luma event URL if available
                url = event_url if event_url else ""

                source = {
                    "id": chunk.get("chunk_id", self.source_id_counter),
                    "title": title,
                    "description": description,
                    "url": url,
                    "event_id": event_id,
                    "event_name": event_name,
                    "start_time": start_time,
                    "end_time": end_time,
                    "location_name": location_name,
                    "location_address": location_address,
                    "meeting_url": meeting_url,
                    "timezone": timezone,
                    "visibility": visibility,
                }

                self.source_id_counter += 1
                sources_list.append(source)

        # Create result object
        result_object = {
            "id": 33,  # Assign a unique ID for the Luma connector
            "name": "Luma Events",
            "type": "LUMA_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, luma_chunks

    async def search_elasticsearch(
        self,
        user_query: str,
        user_id: str,
        search_space_id: int,
        top_k: int = 20,
        search_mode: SearchMode = SearchMode.CHUNKS,
    ) -> tuple:
        """
        Search for Elasticsearch documents and return both the source information and langchain documents

        Args:
            user_query: The user's query
            user_id: The user's ID
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            search_mode: Search mode (CHUNKS or DOCUMENTS)

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        if search_mode == SearchMode.CHUNKS:
            elasticsearch_chunks = await self.chunk_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="ELASTICSEARCH_CONNECTOR",
            )
        elif search_mode == SearchMode.DOCUMENTS:
            elasticsearch_chunks = await self.document_retriever.hybrid_search(
                query_text=user_query,
                top_k=top_k,
                user_id=user_id,
                search_space_id=search_space_id,
                document_type="ELASTICSEARCH_CONNECTOR",
            )
            # Transform document retriever results to match expected format
            elasticsearch_chunks = self._transform_document_results(
                elasticsearch_chunks
            )

        # Early return if no results
        if not elasticsearch_chunks:
            return {
                "id": 34,
                "name": "Elasticsearch",
                "type": "ELASTICSEARCH_CONNECTOR",
                "sources": [],
            }, []

        # Process each chunk and create sources directly without deduplication
        sources_list = []
        async with self.counter_lock:
            for _i, chunk in enumerate(elasticsearch_chunks):
                # Extract document metadata
                document = chunk.get("document", {})
                metadata = document.get("metadata", {})

                # Extract Elasticsearch-specific metadata
                es_id = metadata.get("elasticsearch_id", "")
                es_index = metadata.get("elasticsearch_index", "")
                es_score = metadata.get("elasticsearch_score", "")

                # Create a more descriptive title for Elasticsearch documents
                title = document.get("title", "Elasticsearch Document")
                if es_index:
                    title = f"{title} (Index: {es_index})"

                # Create a more descriptive description for Elasticsearch documents
                description = chunk.get("content", "")[:150]
                if len(description) == 150:
                    description += "..."

                # Add Elasticsearch info to description
                info_parts = []
                if es_id:
                    info_parts.append(f"ID: {es_id}")
                if es_score:
                    info_parts.append(f"Score: {es_score}")

                if info_parts:
                    if description:
                        description = f"{description} | {' | '.join(info_parts)}"
                    else:
                        description = " | ".join(info_parts)

                # For URL, we could construct a URL to view the document if we have the Elasticsearch UI URL
                url = ""
                # Could be extended to include Kibana or other UI URLs if configured

                source = {
                    "id": chunk.get("chunk_id", self.source_id_counter),
                    "title": title,
                    "description": description,
                    "url": url,
                    "elasticsearch_id": es_id,
                    "elasticsearch_index": es_index,
                    "elasticsearch_score": es_score,
                }

                self.source_id_counter += 1
                sources_list.append(source)

        # Create result object
        result_object = {
            "id": 34,  # Assign a unique ID for the Elasticsearch connector
            "name": "Elasticsearch",
            "type": "ELASTICSEARCH_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, elasticsearch_chunks
