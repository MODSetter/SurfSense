import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from elasticsearch import AsyncElasticsearch
from elasticsearch.exceptions import AuthenticationException, ConnectionError

from app.db import DocumentType

logger = logging.getLogger(__name__)


# Create a simple document structure for Elasticsearch results
class ElasticsearchDocument:
    def __init__(
        self, title: str, content: str, url: str, metadata: dict | None = None
    ):
        self.title = title
        self.content = content
        self.url = url
        self.metadata = metadata or {}
        self.document_type = DocumentType.ELASTICSEARCH_CONNECTOR


class ElasticsearchConnector:
    def __init__(self, config: dict):
        self.config = config
        self.client: AsyncElasticsearch | None = None

    async def connect(self) -> bool:
        """Establish connection to Elasticsearch"""
        try:
            # Build the URL with proper scheme
            scheme = "https" if self.config.get("ssl_enabled", True) else "http"
            port = self.config.get("port", 443 if scheme == "https" else 9200)
            hostname = self.config["hostname"]

            # Construct the full URL
            url = f"{scheme}://{hostname}:{port}"

            connection_params = {
                "hosts": [url],
                "verify_certs": self.config.get("ssl_enabled", True),
                "request_timeout": 30,
            }

            # Handle different authentication methods
            auth_method = self.config.get("auth_method", "none")

            if (
                auth_method == "basic"
                and self.config.get("username")
                and self.config.get("password")
            ):
                connection_params["basic_auth"] = (
                    self.config["username"],
                    self.config["password"],
                )
            elif auth_method == "api_key" and self.config.get("api_key"):
                api_key = self.config["api_key"]
                if api_key.startswith("ApiKey "):
                    connection_params["headers"] = {"Authorization": api_key}
                else:
                    connection_params["api_key"] = api_key

            logger.info(f"Connecting to Elasticsearch at {url}")
            self.client = AsyncElasticsearch(**connection_params)

            # Test connection
            info = await self.client.info()
            logger.info(
                f"Successfully connected to Elasticsearch cluster: {info.get('cluster_name', 'Unknown')}"
            )
            return True

        except (ConnectionError, AuthenticationException) as e:
            logger.error(f"Failed to connect to Elasticsearch: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to Elasticsearch: {e}")
            return False

    async def disconnect(self):
        """Close Elasticsearch connection"""
        if self.client:
            await self.client.close()
            self.client = None

    async def test_connection(self) -> dict[str, Any]:
        """Test the Elasticsearch connection and return cluster info"""
        try:
            if not self.client:
                await self.connect()

            if not self.client:
                return {"success": False, "error": "Failed to establish connection"}

            info = await self.client.info()
            indices = await self.client.cat.indices(format="json")

            return {
                "success": True,
                "cluster_name": info.get("cluster_name"),
                "version": info.get("version", {}).get("number"),
                "indices_count": len(indices) if indices else 0,
                "indices": [
                    idx["index"] for idx in indices if not idx["index"].startswith(".")
                ],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_indices(self) -> list[str]:
        """Get list of available indices"""
        try:
            if not self.client:
                await self.connect()

            indices = await self.client.cat.indices(format="json")
            return [idx["index"] for idx in indices if not idx["index"].startswith(".")]
        except Exception as e:
            logger.error(f"Error fetching indices: {e}")
            return []

    async def search_documents(
        self,
        query: str,
        indices: list[str] | None = None,
        size: int = 100,
        fields: list[str] | None = None,
    ) -> AsyncGenerator[ElasticsearchDocument, None]:
        """Search documents in Elasticsearch and yield them as ElasticsearchDocument objects"""
        try:
            if not self.client:
                await self.connect()

            if not self.client:
                logger.error("No Elasticsearch client available")
                return

            # Build search query
            search_body = {
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": fields or ["*"],
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                    }
                },
                "size": size,
                "_source": True,
            }

            # Search across specified indices or all indices
            index_pattern = ",".join(indices) if indices else "*"

            response = await self.client.search(index=index_pattern, body=search_body)

            for hit in response["hits"]["hits"]:
                try:
                    # Convert Elasticsearch document to ElasticsearchDocument
                    document = await self._convert_es_document(hit)
                    if document:
                        yield document
                except Exception as e:
                    logger.warning(f"Failed to convert document {hit.get('_id')}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error searching Elasticsearch: {e}")

    async def get_document_by_id(
        self, index: str, doc_id: str
    ) -> ElasticsearchDocument | None:
        """Get a specific document by ID"""
        try:
            if not self.client:
                await self.connect()

            response = await self.client.get(index=index, id=doc_id)
            return await self._convert_es_document(response)
        except Exception as e:
            logger.error(f"Error fetching document {doc_id} from {index}: {e}")
            return None

    async def _convert_es_document(
        self, es_doc: dict[str, Any]
    ) -> ElasticsearchDocument | None:
        """Convert Elasticsearch document to ElasticsearchDocument"""
        try:
            source = es_doc.get("_source", {})

            # Extract title - try common field names
            title = (
                source.get("title")
                or source.get("name")
                or source.get("subject")
                or source.get("filename")
                or f"Document {es_doc.get('_id', 'Unknown')}"
            )

            # Extract content - try common field names
            content = (
                source.get("content")
                or source.get("text")
                or source.get("body")
                or source.get("message")
                or json.dumps(source)  # Fallback to full source as JSON
            )

            # Generate URL pointing back to Elasticsearch
            url = f"elasticsearch://{es_doc.get('_index')}/{es_doc.get('_id')}"

            # Create metadata
            metadata = {
                "elasticsearch_index": es_doc.get("_index"),
                "elasticsearch_id": es_doc.get("_id"),
                "elasticsearch_score": es_doc.get("_score"),
                "source_fields": list(source.keys()),
                **{
                    k: v
                    for k, v in source.items()
                    if k not in ["content", "text", "body", "message"]
                    and isinstance(v, str | int | float | bool)
                },
            }

            return ElasticsearchDocument(
                title=title[:500],  # Limit title length
                content=content,
                url=url,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Error converting Elasticsearch document: {e}")
            return None
