"""
Elasticsearch connector for SurfSense
"""

import logging
from typing import Any

from elasticsearch import AsyncElasticsearch
from elasticsearch.exceptions import (
    AuthenticationException,
    ConnectionError,
    NotFoundError,
)

logger = logging.getLogger(__name__)


class ElasticsearchConnector:
    """
    Connector for Elasticsearch instances
    """

    def __init__(
        self,
        url: str,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
        verify_certs: bool = True,
        ca_certs: str | None = None,
    ):
        """
        Initialize Elasticsearch connector

        Args:
            url: Full Elasticsearch URL (e.g., https://host:port or cloud endpoint)
            api_key: API key for authentication (preferred method)
            username: Username for basic authentication
            password: Password for basic authentication
            verify_certs: Whether to verify SSL certificates
            ca_certs: Path to CA certificates file
        """
        self.url = url
        self.api_key = api_key
        self.username = username
        self.password = password
        self.verify_certs = verify_certs
        self.ca_certs = ca_certs

        # Build connection configuration
        self.es_config = self._build_config()

        # Initialize Elasticsearch client
        try:
            self.client = AsyncElasticsearch(**self.es_config)
        except Exception as e:
            logger.error(f"Failed to initialize Elasticsearch client: {e}")
            raise

    def _build_config(self) -> dict[str, Any]:
        """Build Elasticsearch client configuration"""
        config = {
            "hosts": [self.url],
            "verify_certs": self.verify_certs,
            "request_timeout": 30,
            "max_retries": 3,
            "retry_on_timeout": True,
        }

        # Authentication - API key takes precedence
        if self.api_key:
            config["api_key"] = self.api_key
        elif self.username and self.password:
            config["basic_auth"] = (self.username, self.password)

        # SSL configuration
        if self.ca_certs:
            config["ca_certs"] = self.ca_certs

        return config

    async def search(
        self,
        index: str | list[str],
        query: dict[str, Any],
        size: int = 100,
        from_: int = 0,
        fields: list[str] | None = None,
        sort: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Search documents in Elasticsearch

        Args:
            index: Elasticsearch index name or list of indices
            query: Elasticsearch query DSL
            size: Number of results to return
            from_: Starting offset for pagination
            fields: List of fields to include in response
            sort: Sort configuration

        Returns:
            Elasticsearch search response
        """
        try:
            search_body: dict[str, Any] = {
                "query": query,
                "size": size,
                "from": from_,
            }

            if fields:
                search_body["_source"] = fields

            if sort:
                search_body["sort"] = sort

            response = await self.client.search(index=index, body=search_body)

            total_hits = response.get("hits", {}).get("total", {})
            # normalize total value (could be dict or int depending on server)
            total_val = (
                total_hits.get("value", total_hits)
                if isinstance(total_hits, dict)
                else total_hits
            )
            logger.info(
                f"Successfully searched index '{index}', found {total_val} results"
            )
            return response

        except NotFoundError:
            logger.error(f"Index '{index}' not found")
            raise
        except AuthenticationException:
            logger.error("Authentication failed")
            raise
        except ConnectionError:
            logger.error("Failed to connect to Elasticsearch")
            raise
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    async def get_indices(self) -> list[str]:
        """
        Get list of available indices

        Returns:
            List of index names
        """
        try:
            indices = await self.client.indices.get_alias(index="*")
            return list(indices.keys())
        except Exception as e:
            logger.error(f"Failed to get indices: {e}")
            raise

    async def get_mapping(self, index: str) -> dict[str, Any]:
        """
        Get mapping for an index

        Args:
            index: Index name

        Returns:
            Index mapping
        """
        try:
            mapping = await self.client.indices.get_mapping(index=index)
            return mapping[index]["mappings"] if index in mapping else {}
        except Exception as e:
            logger.error(f"Failed to get mapping for index '{index}': {e}")
            raise

    async def scroll_search(
        self,
        index: str | list[str],
        query: dict[str, Any],
        size: int = 1000,
        scroll_timeout: str = "5m",
        fields: list[str] | None = None,
    ):
        """
        Perform a scroll search for large result sets

        Args:
            index: Elasticsearch index name or list of indices
            query: Elasticsearch query DSL
            size: Number of results per scroll
            scroll_timeout: Scroll timeout
            fields: List of fields to include in response

        Yields:
            Document hits from Elasticsearch
        """
        try:
            search_body: dict[str, Any] = {
                "query": query,
                "size": size,
            }

            if fields:
                search_body["_source"] = fields

            # Initial search
            response = await self.client.search(
                index=index, body=search_body, scroll=scroll_timeout
            )

            scroll_id = response.get("_scroll_id")
            hits = response.get("hits", {}).get("hits", [])

            while hits:
                for hit in hits:
                    yield hit

                # Continue scrolling
                if scroll_id:
                    response = await self.client.scroll(
                        scroll_id=scroll_id, scroll=scroll_timeout
                    )
                    scroll_id = response.get("_scroll_id")
                    hits = response.get("hits", {}).get("hits", [])

            # Clear scroll
            if scroll_id:
                try:
                    await self.client.clear_scroll(scroll_id=scroll_id)
                except Exception:
                    logger.debug("Failed to clear scroll id (non-fatal)")

        except Exception as e:
            logger.error(f"Scroll search failed: {e}", exc_info=True)
            raise

    async def count_documents(
        self, index: str | list[str], query: dict[str, Any] | None = None
    ) -> int:
        """
        Count documents in an index

        Args:
            index: Index name or list of indices
            query: Optional query to filter documents

        Returns:
            Number of documents
        """
        try:
            if query:
                response = await self.client.count(index=index, body={"query": query})
            else:
                response = await self.client.count(index=index)

            return response["count"]
        except Exception as e:
            logger.error(f"Failed to count documents in index '{index}': {e}")
            raise

    async def close(self):
        """Close the Elasticsearch client connection"""
        if hasattr(self, "client"):
            await self.client.close()
