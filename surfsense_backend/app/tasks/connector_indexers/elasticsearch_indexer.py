import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

from app.connectors.elasticsearch_connector import ElasticsearchConnector
from app.schemas.documents import DocumentCreate
from app.tasks.connector_indexers.base import BaseConnectorIndexer

logger = logging.getLogger(__name__)


class ElasticsearchIndexer(BaseConnectorIndexer):
    """Indexer for Elasticsearch data sources"""

    def __init__(self, connector_config: dict[str, Any]):
        super().__init__(connector_config)
        self.connector = ElasticsearchConnector(self.config)

    async def get_documents(self) -> AsyncGenerator[DocumentCreate, None]:
        """Fetch documents from Elasticsearch based on configuration"""
        try:
            # Connect to Elasticsearch
            if not await self.connector.connect():
                logger.error("Failed to connect to Elasticsearch")
                return

            # Get configuration parameters
            query = self.connector_config.get("query", "*")
            indices = self.connector_config.get("indices", None)
            max_docs = self.connector_config.get("max_documents", 1000)
            fields = self.connector_config.get("search_fields", None)

            logger.info(f"Searching Elasticsearch with query: {query}")

            # Search documents
            doc_count = 0
            async for document in self.connector.search_documents(
                query=query, indices=indices, size=max_docs, fields=fields
            ):
                if doc_count >= max_docs:
                    break

                yield document
                doc_count += 1

                # Add small delay to prevent overwhelming Elasticsearch
                if doc_count % 10 == 0:
                    await asyncio.sleep(0.1)

            logger.info(f"Fetched {doc_count} documents from Elasticsearch")

        except Exception as e:
            logger.error(f"Error fetching documents from Elasticsearch: {e}")
        finally:
            await self.connector.disconnect()

    async def test_connection(self) -> dict[str, Any]:
        """Test the Elasticsearch connection"""
        return await self.connector.test_connection()
