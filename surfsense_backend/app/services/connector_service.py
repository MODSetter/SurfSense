import asyncio
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from linkup import LinkupClient
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from tavily import TavilyClient

from app.db import (
    Chunk,
    Document,
    SearchSourceConnector,
    SearchSourceConnectorType,
)
from app.retriever.chunks_hybrid_search import ChucksHybridSearchRetriever
from app.retriever.documents_hybrid_search import DocumentHybridSearchRetriever


class ConnectorService:
    def __init__(self, session: AsyncSession, search_space_id: int | None = None):
        self.session = session
        self.chunk_retriever = ChucksHybridSearchRetriever(session)
        self.document_retriever = DocumentHybridSearchRetriever(session)
        self.search_space_id = search_space_id
        self.source_id_counter = (
            100000  # High starting value to avoid collisions with existing IDs
        )
        self.counter_lock = (
            asyncio.Lock()
        )  # Lock to protect counter in multithreaded environments

    async def initialize_counter(self):
        """
        Initialize the source_id_counter based on the total number of chunks for the search space.
        This ensures unique IDs across different sessions.
        """
        if self.search_space_id:
            try:
                # Count total chunks for documents belonging to this search space

                result = await self.session.execute(
                    select(func.count(Chunk.id))
                    .join(Document)
                    .filter(Document.search_space_id == self.search_space_id)
                )
                chunk_count = result.scalar() or 0
                self.source_id_counter = chunk_count + 1
                print(
                    f"Initialized source_id_counter to {self.source_id_counter} for search space {self.search_space_id}"
                )
            except Exception as e:
                print(f"Error initializing source_id_counter: {e!s}")
                # Fallback to default value
                self.source_id_counter = 1

    async def search_crawled_urls(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for crawled URLs and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        crawled_urls_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="CRAWLED_URL",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not crawled_urls_docs:
            return {
                "id": 1,
                "name": "Crawled URLs",
                "type": "CRAWLED_URL",
                "sources": [],
            }, []

        def _title_fn(doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return doc_info.get("title") or metadata.get("title") or "Untitled Document"

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return metadata.get("source") or metadata.get("url") or ""

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = metadata.get("description") or self._chunk_preview(
                chunk.get("content", "")
            )
            info_parts = []
            language = metadata.get("language", "")
            last_crawled_at = metadata.get("last_crawled_at", "")
            if language:
                info_parts.append(f"Language: {language}")
            if last_crawled_at:
                info_parts.append(f"Last crawled: {last_crawled_at}")
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "language": metadata.get("language", ""),
                "last_crawled_at": metadata.get("last_crawled_at", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            crawled_urls_docs,
            title_fn=_title_fn,
            description_fn=_description_fn,
            url_fn=_url_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 1,
            "name": "Crawled URLs",
            "type": "CRAWLED_URL",
            "sources": sources_list,
        }

        return result_object, crawled_urls_docs

    async def search_files(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for files and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        files_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="FILE",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not files_docs:
            return {
                "id": 2,
                "name": "Files",
                "type": "FILE",
                "sources": [],
            }, []

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            return (
                metadata.get("og:description")
                or metadata.get("ogDescription")
                or self._chunk_preview(chunk.get("content", ""))
            )

        sources_list = self._build_chunk_sources_from_documents(
            files_docs,
            description_fn=_description_fn,
            url_fn=lambda _doc_info, metadata: metadata.get("url", "") or "",
        )

        # Create result object
        result_object = {
            "id": 2,
            "name": "Files",
            "type": "FILE",
            "sources": sources_list,
        }

        return result_object, files_docs

    async def _combined_rrf_search(
        self,
        query_text: str,
        search_space_id: int,
        document_type: str,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Perform combined search using both chunk-based and document-based hybrid search,
        then merge results using Reciprocal Rank Fusion (RRF) **at the document level**.

        Returned results are **document-grouped** objects that contain a list of chunks
        with real chunk IDs (used for downstream `[citation:<chunk_id>]`).

        This method:
        1. Runs chunk-level hybrid search (vector + keyword on chunks)
        2. Runs document-level hybrid search (vector + keyword on documents, returns chunks)
        3. Combines results using RRF based on their ranks in each result set
        4. Returns top-k deduplicated results

        Args:
            query_text: The search query text
            search_space_id: The search space ID to search within
            document_type: Document type to filter (e.g., "FILE", "CRAWLED_URL")
            top_k: Number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            List of combined and deduplicated document results
        """
        # RRF constant
        k = 60

        # Get more results from each retriever for better fusion
        retriever_top_k = top_k * 2

        # IMPORTANT:
        # These retrievers share the same AsyncSession. AsyncSession does not permit
        # concurrent awaits that require DB IO on the same session/connection.
        # Running these in parallel can raise:
        # "This session is provisioning a new connection; concurrent operations are not permitted"
        #
        # So we run them sequentially.
        chunk_results = await self.chunk_retriever.hybrid_search(
            query_text=query_text,
            top_k=retriever_top_k,
            search_space_id=search_space_id,
            document_type=document_type,
            start_date=start_date,
            end_date=end_date,
        )
        doc_results = await self.document_retriever.hybrid_search(
            query_text=query_text,
            top_k=retriever_top_k,
            search_space_id=search_space_id,
            document_type=document_type,
            start_date=start_date,
            end_date=end_date,
        )

        # Helper to extract document_id from our doc-grouped result
        def _doc_id(item: dict[str, Any]) -> int | None:
            doc = item.get("document", {})
            did = doc.get("id")
            return int(did) if did is not None else None

        # Build rank maps for RRF calculation (document-level)
        chunk_ranks: dict[int, int] = {}
        for rank, result in enumerate(chunk_results, start=1):
            did = _doc_id(result)
            if did is not None and did not in chunk_ranks:
                chunk_ranks[did] = rank

        doc_ranks: dict[int, int] = {}
        for rank, result in enumerate(doc_results, start=1):
            did = _doc_id(result)
            if did is not None and did not in doc_ranks:
                doc_ranks[did] = rank

        all_doc_ids = set(chunk_ranks.keys()) | set(doc_ranks.keys())

        # Calculate RRF scores for each document
        rrf_scores: dict[int, float] = {}
        for did in all_doc_ids:
            chunk_rank = chunk_ranks.get(did)
            doc_rank = doc_ranks.get(did)
            score = 0.0
            if chunk_rank is not None:
                score += 1.0 / (k + chunk_rank)
            if doc_rank is not None:
                score += 1.0 / (k + doc_rank)
            rrf_scores[did] = score

        # Prefer chunk_results data, fallback to doc_results data
        doc_data: dict[int, dict[str, Any]] = {}
        for result in chunk_results:
            did = _doc_id(result)
            if did is not None and did not in doc_data:
                doc_data[did] = result
        for result in doc_results:
            did = _doc_id(result)
            if did is not None and did not in doc_data:
                doc_data[did] = result

        sorted_doc_ids = sorted(
            all_doc_ids, key=lambda did: rrf_scores[did], reverse=True
        )[:top_k]

        combined_results: list[dict[str, Any]] = []
        for did in sorted_doc_ids:
            if did in doc_data:
                result = doc_data[did].copy()
                result["document_id"] = did
                result["score"] = rrf_scores[did]
                # Preserve chunks list if present
                if "chunks" in doc_data[did]:
                    result["chunks"] = doc_data[did]["chunks"]
                combined_results.append(result)

        return combined_results

    def _get_doc_url(self, metadata: dict[str, Any]) -> str:
        return (
            metadata.get("url")
            or metadata.get("source")
            or metadata.get("page_url")
            or metadata.get("VisitedWebPageURL")
            or ""
        )

    def _chunk_preview(self, text: str, limit: int = 200) -> str:
        if not text:
            return ""
        text = str(text)
        if len(text) <= limit:
            return text
        return text[:limit] + "..."

    def _build_chunk_sources_from_documents(
        self,
        documents: list[dict[str, Any]],
        *,
        title_fn=None,
        description_fn=None,
        url_fn=None,
        extra_fields_fn=None,
    ) -> list[dict[str, Any]]:
        """
        Build a chunk-level `sources` list from document-grouped results.

        Each chunk becomes a source with `id == chunk_id` so the frontend can resolve
        citations like `[citation:<chunk_id>]`.
        """
        sources: list[dict[str, Any]] = []

        for doc in documents:
            doc_info = doc.get("document", {}) or {}
            metadata = doc_info.get("metadata", {}) or {}
            url = url_fn(doc_info, metadata) if url_fn else self._get_doc_url(metadata)
            chunks = doc.get("chunks", []) or []
            display_title = (
                title_fn(doc_info, metadata)
                if title_fn
                else doc_info.get("title", "Untitled Document")
            )
            for chunk in chunks:
                chunk_id = chunk.get("chunk_id")
                chunk_content = chunk.get("content", "")
                description = (
                    description_fn(chunk, doc_info, metadata)
                    if description_fn
                    else self._chunk_preview(chunk_content)
                )
                source = {
                    "id": chunk_id,
                    "title": display_title,
                    "description": description,
                    "url": url,
                }
                if extra_fields_fn:
                    source.update(extra_fields_fn(chunk, doc_info, metadata) or {})
                sources.append(source)
        return sources

    async def get_connector_by_type(
        self,
        connector_type: SearchSourceConnectorType,
        search_space_id: int,
    ) -> SearchSourceConnector | None:
        """
        Get a connector by type for a specific search space

        Args:
            connector_type: The connector type to retrieve
            search_space_id: The search space ID to filter by

        Returns:
            Optional[SearchSourceConnector]: The connector if found, None otherwise
        """
        query = select(SearchSourceConnector).filter(
            SearchSourceConnector.search_space_id == search_space_id,
            SearchSourceConnector.connector_type == connector_type,
        )

        result = await self.session.execute(query)
        return result.scalars().first()

    async def search_tavily(
        self, user_query: str, search_space_id: int, top_k: int = 20
    ) -> tuple:
        """
        Search using Tavily API and return both the source information and documents

        Args:
            user_query: The user's query
            search_space_id: The search space ID
            top_k: Maximum number of results to return

        Returns:
            tuple: (sources_info, documents)
        """
        # Get Tavily connector configuration
        tavily_connector = await self.get_connector_by_type(
            SearchSourceConnectorType.TAVILY_API, search_space_id
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
        search_space_id: int,
        top_k: int = 20,
    ) -> tuple:
        """
        Search using a configured SearxNG instance and return both sources and documents.
        """
        searx_connector = await self.get_connector_by_type(
            SearchSourceConnectorType.SEARXNG_API, search_space_id
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
        search_space_id: int,
        top_k: int = 20,
    ) -> tuple:
        """
        Search using Baidu AI Search API and return both sources and documents.

        Baidu AI Search provides intelligent search with automatic summarization.
        We extract the raw search results (references) from the API response.

        Args:
            user_query: User's search query
            search_space_id: Search space ID
            top_k: Maximum number of results to return

        Returns:
            tuple: (sources_info_dict, documents_list)
        """
        # Get Baidu connector configuration
        baidu_connector = await self.get_connector_by_type(
            SearchSourceConnectorType.BAIDU_SEARCH_API, search_space_id
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
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for slack and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        slack_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="SLACK_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not slack_docs:
            return {
                "id": 4,
                "name": "Slack",
                "type": "SLACK_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            channel_name = metadata.get("channel_name", "Unknown Channel")
            message_date = metadata.get("start_date", "")
            title = f"Slack: {channel_name}"
            if message_date:
                title += f" ({message_date})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            channel_id = metadata.get("channel_id", "")
            return (
                f"https://slack.com/app_redirect?channel={channel_id}"
                if channel_id
                else ""
            )

        sources_list = self._build_chunk_sources_from_documents(
            slack_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=lambda chunk, _doc_info, _metadata: chunk.get("content", ""),
        )

        # Create result object
        result_object = {
            "id": 4,
            "name": "Slack",
            "type": "SLACK_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, slack_docs

    async def search_notion(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Notion pages and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        notion_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="NOTION_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not notion_docs:
            return {
                "id": 5,
                "name": "Notion",
                "type": "NOTION_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            page_title = metadata.get("page_title", "Untitled Page")
            indexed_at = metadata.get("indexed_at", "")
            title = f"Notion: {page_title}"
            if indexed_at:
                title += f" (indexed: {indexed_at})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            page_id = metadata.get("page_id", "")
            return f"https://notion.so/{page_id.replace('-', '')}" if page_id else ""

        sources_list = self._build_chunk_sources_from_documents(
            notion_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=lambda chunk, _doc_info, _metadata: chunk.get("content", ""),
        )

        # Create result object
        result_object = {
            "id": 5,
            "name": "Notion",
            "type": "NOTION_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, notion_docs

    async def search_extension(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for extension data and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        extension_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="EXTENSION",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not extension_docs:
            return {
                "id": 6,
                "name": "Extension",
                "type": "EXTENSION",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            webpage_title = metadata.get("VisitedWebPageTitle", "Untitled Page")
            visit_date = metadata.get("VisitedWebPageDateWithTimeInISOString", "")
            title = webpage_title
            if visit_date:
                try:
                    formatted_date = (
                        visit_date.split("T")[0] if "T" in visit_date else visit_date
                    )
                    title += f" (visited: {formatted_date})"
                except Exception:
                    title += f" (visited: {visit_date})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return metadata.get("VisitedWebPageURL", "") or ""

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = chunk.get("content", "")
            visit_duration = metadata.get(
                "VisitedWebPageVisitDurationInMilliseconds", ""
            )
            if visit_duration:
                try:
                    duration_seconds = int(visit_duration) / 1000
                    duration_text = (
                        f"{duration_seconds:.1f} seconds"
                        if duration_seconds < 60
                        else f"{duration_seconds / 60:.1f} minutes"
                    )
                    description = (description + f" | Duration: {duration_text}").strip(
                        " |"
                    )
                except Exception:
                    pass
            return description

        sources_list = self._build_chunk_sources_from_documents(
            extension_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
        )

        # Create result object
        result_object = {
            "id": 6,
            "name": "Extension",
            "type": "EXTENSION",
            "sources": sources_list,
        }

        return result_object, extension_docs

    async def search_youtube(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for YouTube videos and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        youtube_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="YOUTUBE_VIDEO",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not youtube_docs:
            return {
                "id": 7,
                "name": "YouTube Videos",
                "type": "YOUTUBE_VIDEO",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            video_title = metadata.get("video_title", "Untitled Video")
            channel_name = metadata.get("channel_name", "")
            return f"{video_title} - {channel_name}" if channel_name else video_title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            video_id = metadata.get("video_id", "")
            return f"https://www.youtube.com/watch?v={video_id}" if video_id else ""

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            return metadata.get("description") or chunk.get("content", "")

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "video_id": metadata.get("video_id", ""),
                "channel_name": metadata.get("channel_name", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            youtube_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 7,  # Assign a unique ID for the YouTube connector
            "name": "YouTube Videos",
            "type": "YOUTUBE_VIDEO",
            "sources": sources_list,
        }

        return result_object, youtube_docs

    async def search_github(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for GitHub documents and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        github_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="GITHUB_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not github_docs:
            return {
                "id": 8,
                "name": "GitHub",
                "type": "GITHUB_CONNECTOR",
                "sources": [],
            }, []

        sources_list = self._build_chunk_sources_from_documents(
            github_docs,
            description_fn=lambda chunk, _doc_info, metadata: metadata.get(
                "description"
            )
            or chunk.get("content", ""),
            url_fn=lambda _doc_info, metadata: metadata.get("url", "") or "",
        )

        # Create result object
        result_object = {
            "id": 8,
            "name": "GitHub",
            "type": "GITHUB_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, github_docs

    async def search_linear(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Linear issues and comments and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        linear_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="LINEAR_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not linear_docs:
            return {
                "id": 9,
                "name": "Linear Issues",
                "type": "LINEAR_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            issue_identifier = metadata.get("issue_identifier", "")
            issue_title = metadata.get("issue_title", "Untitled Issue")
            issue_state = metadata.get("state", "")
            title = (
                f"Linear: {issue_identifier} - {issue_title}"
                if issue_identifier
                else f"Linear: {issue_title}"
            )
            if issue_state:
                title += f" ({issue_state})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            issue_identifier = metadata.get("issue_identifier", "")
            return (
                f"https://linear.app/issue/{issue_identifier}"
                if issue_identifier
                else ""
            )

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = chunk.get("content", "")
            comment_count = metadata.get("comment_count", 0)
            if comment_count:
                description = (description + f" | Comments: {comment_count}").strip(
                    " |"
                )
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "issue_identifier": metadata.get("issue_identifier", ""),
                "state": metadata.get("state", ""),
                "comment_count": metadata.get("comment_count", 0),
            }

        sources_list = self._build_chunk_sources_from_documents(
            linear_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 9,  # Assign a unique ID for the Linear connector
            "name": "Linear Issues",
            "type": "LINEAR_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, linear_docs

    async def search_jira(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Jira issues and comments and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        jira_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="JIRA_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not jira_docs:
            return {
                "id": 30,
                "name": "Jira Issues",
                "type": "JIRA_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            issue_key = metadata.get("issue_key", "")
            issue_title = metadata.get("issue_title", "Untitled Issue")
            status = metadata.get("status", "")
            title = (
                f"Jira: {issue_key} - {issue_title}"
                if issue_key
                else f"Jira: {issue_title}"
            )
            if status:
                title += f" ({status})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            issue_key = metadata.get("issue_key", "")
            base_url = metadata.get("base_url")
            return f"{base_url}/browse/{issue_key}" if issue_key and base_url else ""

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = chunk.get("content", "")
            info_parts = []
            priority = metadata.get("priority", "")
            issue_type = metadata.get("issue_type", "")
            comment_count = metadata.get("comment_count", 0)
            if priority:
                info_parts.append(f"Priority: {priority}")
            if issue_type:
                info_parts.append(f"Type: {issue_type}")
            if comment_count:
                info_parts.append(f"Comments: {comment_count}")
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "issue_key": metadata.get("issue_key", ""),
                "status": metadata.get("status", ""),
                "priority": metadata.get("priority", ""),
                "issue_type": metadata.get("issue_type", ""),
                "comment_count": metadata.get("comment_count", 0),
            }

        sources_list = self._build_chunk_sources_from_documents(
            jira_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 10,  # Assign a unique ID for the Jira connector
            "name": "Jira Issues",
            "type": "JIRA_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, jira_docs

    async def search_google_calendar(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Google Calendar events and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        calendar_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="GOOGLE_CALENDAR_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not calendar_docs:
            return {
                "id": 31,
                "name": "Google Calendar Events",
                "type": "GOOGLE_CALENDAR_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            event_summary = metadata.get("event_summary", "Untitled Event")
            start_time = metadata.get("start_time", "")
            title = f"Calendar: {event_summary}"
            if start_time:
                title += f" ({start_time})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            event_id = metadata.get("event_id", "")
            calendar_id = metadata.get("calendar_id", "")
            return (
                f"https://calendar.google.com/calendar/event?eid={event_id}"
                if event_id and calendar_id
                else ""
            )

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = chunk.get("content", "")
            info_parts = []
            location = metadata.get("location", "")
            calendar_id = metadata.get("calendar_id", "")
            end_time = metadata.get("end_time", "")
            if location:
                info_parts.append(f"Location: {location}")
            if calendar_id and calendar_id != "primary":
                info_parts.append(f"Calendar: {calendar_id}")
            if end_time:
                info_parts.append(f"End: {end_time}")
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "event_id": metadata.get("event_id", ""),
                "event_summary": metadata.get("event_summary", "Untitled Event"),
                "calendar_id": metadata.get("calendar_id", ""),
                "start_time": metadata.get("start_time", ""),
                "end_time": metadata.get("end_time", ""),
                "location": metadata.get("location", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            calendar_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 31,  # Assign a unique ID for the Google Calendar connector
            "name": "Google Calendar Events",
            "type": "GOOGLE_CALENDAR_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, calendar_docs

    async def search_airtable(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Airtable records and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        airtable_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="AIRTABLE_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not airtable_docs:
            return {
                "id": 32,
                "name": "Airtable Records",
                "type": "AIRTABLE_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            record_id = metadata.get("record_id", "")
            return f"Airtable Record: {record_id}" if record_id else "Airtable Record"

        def _description_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            created_time = metadata.get("created_time", "")
            return f"Created: {created_time}" if created_time else ""

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "record_id": metadata.get("record_id", ""),
                "created_time": metadata.get("created_time", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            airtable_docs,
            title_fn=_title_fn,
            url_fn=lambda _doc_info, _metadata: "",
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        result_object = {
            "id": 32,
            "name": "Airtable Records",
            "type": "AIRTABLE_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, airtable_docs

    async def search_google_gmail(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Gmail messages and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        gmail_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="GOOGLE_GMAIL_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not gmail_docs:
            return {
                "id": 32,
                "name": "Gmail Messages",
                "type": "GOOGLE_GMAIL_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            subject = metadata.get("subject", "No Subject")
            sender = metadata.get("sender", "Unknown Sender")
            return (
                f"Email: {subject} (from {sender})" if sender else f"Email: {subject}"
            )

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            message_id = metadata.get("message_id", "")
            return (
                f"https://mail.google.com/mail/u/0/#inbox/{message_id}"
                if message_id
                else ""
            )

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = chunk.get("content", "")
            info_parts = []
            date_str = metadata.get("date", "")
            thread_id = metadata.get("thread_id", "")
            if date_str:
                info_parts.append(f"Date: {date_str}")
            if thread_id:
                info_parts.append(f"Thread: {thread_id}")
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "message_id": metadata.get("message_id", ""),
                "subject": metadata.get("subject", "No Subject"),
                "sender": metadata.get("sender", "Unknown Sender"),
                "date": metadata.get("date", ""),
                "thread_id": metadata.get("thread_id", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            gmail_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 32,  # Assign a unique ID for the Gmail connector
            "name": "Gmail Messages",
            "type": "GOOGLE_GMAIL_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, gmail_docs

    async def search_google_drive(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Google Drive files and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        drive_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="GOOGLE_DRIVE_FILE",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not drive_docs:
            return {
                "id": 33,
                "name": "Google Drive Files",
                "type": "GOOGLE_DRIVE_FILE",
                "sources": [],
            }, []

        def _title_fn(doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return (
                doc_info.get("title")
                or metadata.get("google_drive_file_name")
                or metadata.get("FILE_NAME")
                or "Untitled File"
            )

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            file_id = metadata.get("google_drive_file_id", "")
            return f"https://drive.google.com/file/d/{file_id}/view" if file_id else ""

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = self._chunk_preview(chunk.get("content", ""))
            info_parts = []
            mime_type = metadata.get("google_drive_mime_type", "")
            modified_time = metadata.get("modified_time", "")
            if mime_type:
                # Simplify mime type for display
                if "google-apps" in mime_type:
                    file_type = mime_type.split(".")[-1].title()
                else:
                    file_type = mime_type.split("/")[-1].upper()
                info_parts.append(f"Type: {file_type}")
            if modified_time:
                info_parts.append(f"Modified: {modified_time}")
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "google_drive_file_id": metadata.get("google_drive_file_id", ""),
                "google_drive_mime_type": metadata.get("google_drive_mime_type", ""),
                "modified_time": metadata.get("modified_time", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            drive_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 33,  # Assign a unique ID for the Google Drive connector
            "name": "Google Drive Files",
            "type": "GOOGLE_DRIVE_FILE",
            "sources": sources_list,
        }

        return result_object, drive_docs

    async def search_confluence(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Confluence pages and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        confluence_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="CONFLUENCE_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not confluence_docs:
            return {
                "id": 40,
                "name": "Confluence",
                "type": "CONFLUENCE_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            page_title = metadata.get("page_title", "Untitled Page")
            space_key = metadata.get("space_key", "")
            title = f"Confluence: {page_title}"
            if space_key:
                title += f" ({space_key})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            page_id = metadata.get("page_id", "")
            base_url = metadata.get("base_url", "")
            return f"{base_url}/pages/{page_id}" if base_url and page_id else ""

        sources_list = self._build_chunk_sources_from_documents(
            confluence_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=lambda chunk, _doc_info, _metadata: chunk.get("content", ""),
        )

        # Create result object
        result_object = {
            "id": 40,
            "name": "Confluence",
            "type": "CONFLUENCE_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, confluence_docs

    async def search_clickup(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for ClickUp tasks and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        clickup_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="CLICKUP_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not clickup_docs:
            return {
                "id": 31,
                "name": "ClickUp Tasks",
                "type": "CLICKUP_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return metadata.get("task_name", "ClickUp Task")

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return metadata.get("task_url", "") or ""

        def _description_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            parts = []
            if metadata.get("task_status"):
                parts.append(f"Status: {metadata.get('task_status')}")
            if metadata.get("task_priority"):
                parts.append(f"Priority: {metadata.get('task_priority')}")
            if metadata.get("task_due_date"):
                parts.append(f"Due: {metadata.get('task_due_date')}")
            if metadata.get("task_list_name"):
                parts.append(f"List: {metadata.get('task_list_name')}")
            if metadata.get("task_space_name"):
                parts.append(f"Space: {metadata.get('task_space_name')}")
            return " | ".join(parts) if parts else "ClickUp Task"

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "task_id": metadata.get("task_id", ""),
                "status": metadata.get("task_status", ""),
                "priority": metadata.get("task_priority", ""),
                "assignees": metadata.get("task_assignees", []),
                "due_date": metadata.get("task_due_date", ""),
                "list_name": metadata.get("task_list_name", ""),
                "space_name": metadata.get("task_space_name", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            clickup_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 31,  # Assign a unique ID for the ClickUp connector
            "name": "ClickUp Tasks",
            "type": "CLICKUP_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, clickup_docs

    async def search_linkup(
        self,
        user_query: str,
        search_space_id: int,
        mode: str = "standard",
    ) -> tuple:
        """
        Search using Linkup API and return both the source information and documents

        Args:
            user_query: The user's query
            search_space_id: The search space ID
            mode: Search depth mode, can be "standard" or "deep"

        Returns:
            tuple: (sources_info, documents)
        """
        # Get Linkup connector configuration
        linkup_connector = await self.get_connector_by_type(
            SearchSourceConnectorType.LINKUP_API, search_space_id
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
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Discord messages and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        discord_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="DISCORD_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not discord_docs:
            return {
                "id": 11,
                "name": "Discord",
                "type": "DISCORD_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            channel_name = metadata.get("channel_name", "Unknown Channel")
            message_date = metadata.get("start_date", "")
            title = f"Discord: {channel_name}"
            if message_date:
                title += f" ({message_date})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            channel_id = metadata.get("channel_id", "")
            guild_id = metadata.get("guild_id", "")
            if guild_id and channel_id:
                return f"https://discord.com/channels/{guild_id}/{channel_id}"
            if channel_id:
                return f"https://discord.com/channels/@me/{channel_id}"
            return ""

        sources_list = self._build_chunk_sources_from_documents(
            discord_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=lambda chunk, _doc_info, _metadata: chunk.get("content", ""),
        )

        # Create result object
        result_object = {
            "id": 11,
            "name": "Discord",
            "type": "DISCORD_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, discord_docs

    async def search_teams(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Microsoft Teams messages and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        teams_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="TEAMS_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not teams_docs:
            return {
                "id": 53,
                "name": "Microsoft Teams",
                "type": "TEAMS_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            team_name = metadata.get("team_name", "Unknown Team")
            channel_name = metadata.get("channel_name", "Unknown Channel")
            message_date = metadata.get("start_date", "")
            title = f"Teams: {team_name} - {channel_name}"
            if message_date:
                title += f" ({message_date})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            team_id = metadata.get("team_id", "")
            channel_id = metadata.get("channel_id", "")
            if team_id and channel_id:
                return f"https://teams.microsoft.com/l/channel/{channel_id}/General?groupId={team_id}"
            return ""

        sources_list = self._build_chunk_sources_from_documents(
            teams_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=lambda chunk, _doc_info, _metadata: chunk.get("content", ""),
        )

        # Create result object
        result_object = {
            "id": 53,
            "name": "Microsoft Teams",
            "type": "TEAMS_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, teams_docs

    async def search_luma(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Luma events and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        luma_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="LUMA_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not luma_docs:
            return {
                "id": 33,
                "name": "Luma Events",
                "type": "LUMA_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            event_name = metadata.get("event_name", "Untitled Event")
            start_time = metadata.get("start_time", "")
            return (
                f"Luma: {event_name} ({start_time})"
                if start_time
                else f"Luma: {event_name}"
            )

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return metadata.get("event_url", "") or ""

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = chunk.get("content", "")
            info_parts = []
            if metadata.get("location_name"):
                info_parts.append(f"Venue: {metadata.get('location_name')}")
            elif metadata.get("location_address"):
                info_parts.append(f"Location: {metadata.get('location_address')}")
            if metadata.get("meeting_url"):
                info_parts.append("Online Event")
            if metadata.get("end_time"):
                info_parts.append(f"Ends: {metadata.get('end_time')}")
            if metadata.get("timezone"):
                info_parts.append(f"TZ: {metadata.get('timezone')}")
            if metadata.get("visibility"):
                info_parts.append(
                    f"Visibility: {str(metadata.get('visibility')).title()}"
                )
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "event_id": metadata.get("event_id", ""),
                "event_name": metadata.get("event_name", "Untitled Event"),
                "start_time": metadata.get("start_time", ""),
                "end_time": metadata.get("end_time", ""),
                "location_name": metadata.get("location_name", ""),
                "location_address": metadata.get("location_address", ""),
                "meeting_url": metadata.get("meeting_url", ""),
                "timezone": metadata.get("timezone", ""),
                "visibility": metadata.get("visibility", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            luma_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 33,  # Assign a unique ID for the Luma connector
            "name": "Luma Events",
            "type": "LUMA_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, luma_docs

    async def search_elasticsearch(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Elasticsearch documents and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        elasticsearch_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="ELASTICSEARCH_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not elasticsearch_docs:
            return {
                "id": 34,
                "name": "Elasticsearch",
                "type": "ELASTICSEARCH_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            title = doc_info.get("title", "Elasticsearch Document")
            es_index = metadata.get("elasticsearch_index", "")
            return f"{title} (Index: {es_index})" if es_index else title

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = self._chunk_preview(chunk.get("content", ""), limit=150)
            info_parts = []
            if metadata.get("elasticsearch_id"):
                info_parts.append(f"ID: {metadata.get('elasticsearch_id')}")
            if metadata.get("elasticsearch_score"):
                info_parts.append(f"Score: {metadata.get('elasticsearch_score')}")
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "elasticsearch_id": metadata.get("elasticsearch_id", ""),
                "elasticsearch_index": metadata.get("elasticsearch_index", ""),
                "elasticsearch_score": metadata.get("elasticsearch_score", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            elasticsearch_docs,
            title_fn=_title_fn,
            url_fn=lambda _doc_info, _metadata: "",
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 34,  # Assign a unique ID for the Elasticsearch connector
            "name": "Elasticsearch",
            "type": "ELASTICSEARCH_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, elasticsearch_docs

    async def search_notes(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Notes and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        notes_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="NOTE",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not notes_docs:
            return {
                "id": 51,
                "name": "Notes",
                "type": "NOTE",
                "sources": [],
            }, []

        def _title_fn(doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return doc_info.get("title", "Untitled Note")

        def _url_fn(_doc_info: dict[str, Any], _metadata: dict[str, Any]) -> str:
            return ""  # Notes don't have URLs

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], _metadata: dict[str, Any]
        ) -> str:
            return self._chunk_preview(chunk.get("content", ""), limit=200)

        sources_list = self._build_chunk_sources_from_documents(
            notes_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
        )

        # Create result object
        result_object = {
            "id": 51,
            "name": "Notes",
            "type": "NOTE",
            "sources": sources_list,
        }

        return result_object, notes_docs

    async def search_bookstack(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for BookStack pages and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            user_id: The user's ID
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        bookstack_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="BOOKSTACK_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not bookstack_docs:
            return {
                "id": 50,
                "name": "BookStack",
                "type": "BOOKSTACK_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            page_name = metadata.get("page_name", "Untitled Page")
            return f"BookStack: {page_name}"

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            page_slug = metadata.get("page_slug", "")
            book_slug = metadata.get("book_slug", "")
            base_url = metadata.get("base_url", "")
            page_url = metadata.get("page_url", "")
            if page_url:
                return page_url
            if base_url and book_slug and page_slug:
                return f"{base_url}/books/{book_slug}/page/{page_slug}"
            return ""

        sources_list = self._build_chunk_sources_from_documents(
            bookstack_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=lambda chunk, _doc_info, _metadata: chunk.get("content", ""),
        )

        # Create result object
        result_object = {
            "id": 50,  # Assign a unique ID for the BookStack connector
            "name": "BookStack",
            "type": "BOOKSTACK_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, bookstack_docs

    async def search_circleback(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Circleback meeting notes and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        circleback_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="CIRCLEBACK",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not circleback_docs:
            return {
                "id": 52,
                "name": "Circleback Meetings",
                "type": "CIRCLEBACK",
                "sources": [],
            }, []

        def _title_fn(doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            meeting_name = metadata.get("meeting_name", "")
            meeting_date = metadata.get("meeting_date", "")
            title = doc_info.get("title") or meeting_name or "Circleback Meeting"
            if meeting_date:
                title += f" ({meeting_date})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            meeting_id = metadata.get("circleback_meeting_id", "")
            return (
                f"https://app.circleback.ai/meetings/{meeting_id}" if meeting_id else ""
            )

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = self._chunk_preview(chunk.get("content", ""), limit=200)
            info_parts = []
            duration = metadata.get("duration_seconds")
            attendee_count = metadata.get("attendee_count")
            if duration:
                minutes = int(duration) // 60
                info_parts.append(f"Duration: {minutes} min")
            if attendee_count:
                info_parts.append(f"Attendees: {attendee_count}")
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "circleback_meeting_id": metadata.get("circleback_meeting_id", ""),
                "meeting_name": metadata.get("meeting_name", ""),
                "meeting_date": metadata.get("meeting_date", ""),
                "duration_seconds": metadata.get("duration_seconds", 0),
                "attendee_count": metadata.get("attendee_count", 0),
            }

        sources_list = self._build_chunk_sources_from_documents(
            circleback_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 52,
            "name": "Circleback Meetings",
            "type": "CIRCLEBACK",
            "sources": sources_list,
        }

        return result_object, circleback_docs

    async def search_obsidian(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Obsidian vault notes and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        obsidian_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="OBSIDIAN_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not obsidian_docs:
            return {
                "id": 53,
                "name": "Obsidian Vault",
                "type": "OBSIDIAN_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return doc_info.get("title", "Untitled Note")

        def _url_fn(doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            # Obsidian URL format: obsidian://vault_name/path
            return doc_info.get("url", "")

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = self._chunk_preview(chunk.get("content", ""), limit=200)
            info_parts = []
            vault_name = metadata.get("vault_name")
            tags = metadata.get("tags", [])
            if vault_name:
                info_parts.append(f"Vault: {vault_name}")
            if tags and isinstance(tags, list) and len(tags) > 0:
                info_parts.append(f"Tags: {', '.join(tags[:3])}")
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "vault_name": metadata.get("vault_name", ""),
                "file_path": metadata.get("file_path", ""),
                "tags": metadata.get("tags", []),
                "outgoing_links": metadata.get("outgoing_links", []),
            }

        sources_list = self._build_chunk_sources_from_documents(
            obsidian_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 53,
            "name": "Obsidian Vault",
            "type": "OBSIDIAN_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, obsidian_docs

    # =========================================================================
    # Composio Connector Search Methods
    # =========================================================================

    async def search_composio_google_drive(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Composio Google Drive files and return both the source information
        and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        composio_drive_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="COMPOSIO_GOOGLE_DRIVE_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not composio_drive_docs:
            return {
                "id": 54,
                "name": "Google Drive (Composio)",
                "type": "COMPOSIO_GOOGLE_DRIVE_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return (
                doc_info.get("title")
                or metadata.get("title")
                or metadata.get("file_name")
                or "Untitled Document"
            )

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return metadata.get("url") or metadata.get("web_view_link") or ""

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = self._chunk_preview(chunk.get("content", ""), limit=200)
            info_parts = []
            mime_type = metadata.get("mime_type")
            modified_time = metadata.get("modified_time")
            if mime_type:
                info_parts.append(f"Type: {mime_type}")
            if modified_time:
                info_parts.append(f"Modified: {modified_time}")
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "mime_type": metadata.get("mime_type", ""),
                "file_id": metadata.get("file_id", ""),
                "modified_time": metadata.get("modified_time", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            composio_drive_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 54,
            "name": "Google Drive (Composio)",
            "type": "COMPOSIO_GOOGLE_DRIVE_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, composio_drive_docs

    async def search_composio_gmail(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Composio Gmail messages and return both the source information
        and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        composio_gmail_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="COMPOSIO_GMAIL_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not composio_gmail_docs:
            return {
                "id": 55,
                "name": "Gmail (Composio)",
                "type": "COMPOSIO_GMAIL_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return (
                doc_info.get("title")
                or metadata.get("subject")
                or metadata.get("title")
                or "Untitled Email"
            )

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return metadata.get("url") or ""

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = self._chunk_preview(chunk.get("content", ""), limit=200)
            info_parts = []
            sender = metadata.get("from") or metadata.get("sender")
            date = metadata.get("date") or metadata.get("received_at")
            if sender:
                info_parts.append(f"From: {sender}")
            if date:
                info_parts.append(f"Date: {date}")
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "message_id": metadata.get("message_id", ""),
                "thread_id": metadata.get("thread_id", ""),
                "from": metadata.get("from", ""),
                "to": metadata.get("to", ""),
                "date": metadata.get("date", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            composio_gmail_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 55,
            "name": "Gmail (Composio)",
            "type": "COMPOSIO_GMAIL_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, composio_gmail_docs

    async def search_composio_google_calendar(
        self,
        user_query: str,
        search_space_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Composio Google Calendar events and return both the source information
        and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            search_space_id: The search space ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        composio_calendar_docs = await self._combined_rrf_search(
            query_text=user_query,
            search_space_id=search_space_id,
            document_type="COMPOSIO_GOOGLE_CALENDAR_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not composio_calendar_docs:
            return {
                "id": 56,
                "name": "Google Calendar (Composio)",
                "type": "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return (
                doc_info.get("title")
                or metadata.get("summary")
                or metadata.get("title")
                or "Untitled Event"
            )

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return metadata.get("url") or metadata.get("html_link") or ""

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = self._chunk_preview(chunk.get("content", ""), limit=200)
            info_parts = []
            start_time = metadata.get("start_time") or metadata.get("start")
            end_time = metadata.get("end_time") or metadata.get("end")
            if start_time:
                info_parts.append(f"Start: {start_time}")
            if end_time:
                info_parts.append(f"End: {end_time}")
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "event_id": metadata.get("event_id", ""),
                "calendar_id": metadata.get("calendar_id", ""),
                "start_time": metadata.get("start_time", ""),
                "end_time": metadata.get("end_time", ""),
                "location": metadata.get("location", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            composio_calendar_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 56,
            "name": "Google Calendar (Composio)",
            "type": "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, composio_calendar_docs

    # =========================================================================
    # Utility Methods for Connector Discovery
    # =========================================================================

    async def get_available_connectors(
        self,
        search_space_id: int,
    ) -> list[SearchSourceConnectorType]:
        """
        Get all available (enabled) connector types for a search space.

        Args:
            search_space_id: The search space ID

        Returns:
            List of SearchSourceConnectorType enums for enabled connectors
        """
        query = (
            select(SearchSourceConnector.connector_type)
            .filter(
                SearchSourceConnector.search_space_id == search_space_id,
            )
            .distinct()
        )

        result = await self.session.execute(query)
        connector_types = result.scalars().all()
        return list(connector_types)

    async def get_available_document_types(
        self,
        search_space_id: int,
    ) -> list[str]:
        """
        Get all document types that have at least one document in the search space.

        Args:
            search_space_id: The search space ID

        Returns:
            List of document type strings that have documents indexed
        """
        from sqlalchemy import distinct

        from app.db import Document

        query = select(distinct(Document.document_type)).filter(
            Document.search_space_id == search_space_id,
        )

        result = await self.session.execute(query)
        doc_types = result.scalars().all()
        return [str(dt) for dt in doc_types]
