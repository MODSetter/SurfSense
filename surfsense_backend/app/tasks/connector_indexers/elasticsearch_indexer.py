"""
Elasticsearch connector indexer.
"""

import asyncio
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.elasticsearch_connector import ElasticsearchConnector
from app.db import Document, DocumentType, SearchSourceConnectorType
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_document_summary,
)

from .base import (
    check_duplicate_document_by_hash,
    get_connector_by_id,
    logger,
    update_connector_last_indexed,
)


class ElasticsearchIndexer:
    """Indexer class for Elasticsearch data sources (kept for backward compatibility)"""

    def __init__(self, connector_config: dict):
        self.connector_config = connector_config
        self.connector = ElasticsearchConnector(self.config)

    async def get_documents(self):
        """Get documents from Elasticsearch (kept for backward compatibility)"""
        try:
            if not await self.connector.connect():
                logger.error("Failed to connect to Elasticsearch")
                return

            query = self.connector_config.get("query", "*")
            indices = self.connector_config.get("indices", None)
            max_docs = self.connector_config.get("max_documents", 1000)
            fields = self.connector_config.get("search_fields", None)

            logger.info(f"Searching Elasticsearch with query: {query}")

            doc_count = 0
            async for document in self.connector.search_documents(
                query=query, indices=indices, size=max_docs, fields=fields
            ):
                if doc_count >= max_docs:
                    break

                yield document
                doc_count += 1

                if doc_count % 10 == 0:
                    await asyncio.sleep(0.1)

            logger.info(f"Fetched {doc_count} documents from Elasticsearch")

        except Exception as e:
            logger.error(f"Error fetching documents from Elasticsearch: {e}")
        finally:
            await self.connector.disconnect()

    async def test_connection(self):
        """Test the Elasticsearch connection (kept for backward compatibility)"""
        return await self.connector.test_connection()


async def index_elasticsearch_documents(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str
    | None = None,  # Not used for Elasticsearch but kept for consistency
    end_date: str | None = None,  # Not used for Elasticsearch but kept for consistency
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index Elasticsearch documents.

    Args:
        session: Database session
        connector_id: ID of the Elasticsearch connector
        search_space_id: ID of the search space to store documents in
        user_id: User ID
        start_date: Start date for indexing (not used for Elasticsearch but kept for consistency)
        end_date: End date for indexing (not used for Elasticsearch but kept for consistency)
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="elasticsearch_documents_indexing",
        source="connector_indexing_task",
        message=f"Starting Elasticsearch documents indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    try:
        # Get the connector
        await task_logger.log_task_progress(
            log_entry,
            f"Retrieving Elasticsearch connector {connector_id} from database",
            {"stage": "connector_retrieval"},
        )

        # Get the connector from the database
        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.ELASTICSEARCH_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not an Elasticsearch connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return (
                0,
                f"Connector with ID {connector_id} not found or is not an Elasticsearch connector",
            )

        logger.info(f"Starting Elasticsearch indexing for connector {connector_id}")

        # Initialize Elasticsearch connector
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Elasticsearch connector for connector {connector_id}",
            {"stage": "connector_initialization"},
        )

        try:
            elasticsearch_connector = ElasticsearchConnector(connector.config)
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Invalid Elasticsearch configuration for connector {connector_id}: {e}",
                "Invalid configuration",
                {"error_type": "InvalidConfiguration"},
            )
            return 0, f"Invalid Elasticsearch configuration: {e}"

        # Test connection first
        await task_logger.log_task_progress(
            log_entry,
            f"Testing Elasticsearch connection for connector {connector_id}",
            {"stage": "connection_test"},
        )

        connection_test = await elasticsearch_connector.test_connection()
        if not connection_test.get("success"):
            await task_logger.log_task_failure(
                log_entry,
                f"Connection test failed: {connection_test.get('error')}",
                "Connection failed",
                {"error_type": "ConnectionError"},
            )
            return 0, f"Connection test failed: {connection_test.get('error')}"

        # Get configuration parameters
        query = connector.config.get("query", "*")
        indices = connector.config.get("indices", None)
        max_docs = connector.config.get("max_documents", 1000)
        fields = connector.config.get("search_fields", None)

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Elasticsearch documents with query: {query}",
            {
                "stage": "fetching_documents",
                "query": query,
                "indices": indices,
                "max_documents": max_docs,
            },
        )

        # Index documents
        documents_indexed = 0
        documents_skipped = 0
        skipped_documents = []

        try:
            # Connect to Elasticsearch
            if not await elasticsearch_connector.connect():
                await task_logger.log_task_failure(
                    log_entry,
                    "Failed to connect to Elasticsearch",
                    "Connection failed",
                    {"error_type": "ConnectionError"},
                )
                return 0, "Failed to connect to Elasticsearch"

            # Search documents
            doc_count = 0
            async for elasticsearch_doc in elasticsearch_connector.search_documents(
                query=query, indices=indices, size=max_docs, fields=fields
            ):
                try:
                    if doc_count >= max_docs:
                        break

                    # Convert ElasticsearchDocument to markdown content
                    document_content = elasticsearch_doc.content
                    document_title = elasticsearch_doc.title

                    if not document_content.strip():
                        logger.warning(
                            f"Skipping document with no content: {document_title}"
                        )
                        skipped_documents.append(f"{document_title} (no content)")
                        documents_skipped += 1
                        continue

                    # Generate content hash
                    content_hash = generate_content_hash(
                        document_content, search_space_id
                    )

                    # Check if document already exists
                    existing_document_by_hash = await check_duplicate_document_by_hash(
                        session, content_hash
                    )
                    if existing_document_by_hash:
                        logger.info(
                            f"Document with content hash {content_hash} already exists for document {document_title}. Skipping processing."
                        )
                        documents_skipped += 1
                        continue

                    # Generate summary with metadata
                    user_llm = await get_user_long_context_llm(session, user_id)

                    if user_llm:
                        # Create metadata for summary generation
                        document_metadata = {
                            "document_title": document_title,
                            "document_type": "Elasticsearch Document",
                            "connector_type": "Elasticsearch",
                            "source_index": elasticsearch_doc.metadata.get(
                                "elasticsearch_index", "unknown"
                            ),
                        }
                        document_metadata.update(elasticsearch_doc.metadata)

                        (
                            summary_content,
                            summary_embedding,
                        ) = await generate_document_summary(
                            document_content, user_llm, document_metadata
                        )
                    else:
                        # Fallback to simple summary if no LLM configured
                        summary_content = (
                            f"Elasticsearch Document: {document_title}\n\n"
                        )
                        if elasticsearch_doc.metadata.get("elasticsearch_index"):
                            summary_content += f"Index: {elasticsearch_doc.metadata['elasticsearch_index']}\n"

                        # Add content preview
                        content_preview = document_content[:300]
                        if len(document_content) > 300:
                            content_preview += "..."
                        summary_content += f"Content: {content_preview}\n"

                        summary_embedding = config.embedding_model_instance.embed(
                            summary_content
                        )

                    # Create document chunks
                    chunks = await create_document_chunks(document_content)

                    # Create document
                    document = Document(
                        search_space_id=search_space_id,
                        title=f"Elasticsearch Document - {document_title}",
                        document_type=DocumentType.ELASTICSEARCH_CONNECTOR,
                        document_metadata={
                            "document_title": document_title,
                            "source_index": elasticsearch_doc.metadata.get(
                                "elasticsearch_index", "unknown"
                            ),
                            "document_id": elasticsearch_doc.metadata.get(
                                "elasticsearch_id", "unknown"
                            ),
                            "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            **elasticsearch_doc.metadata,
                        },
                        content=summary_content,
                        content_hash=content_hash,
                        embedding=summary_embedding,
                        chunks=chunks,
                    )

                    session.add(document)
                    documents_indexed += 1
                    doc_count += 1
                    logger.info(f"Successfully indexed new document {document_title}")

                    # Add small delay to prevent overwhelming Elasticsearch
                    if doc_count % 10 == 0:
                        await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(
                        f"Error processing document {elasticsearch_doc.title if 'elasticsearch_doc' in locals() else 'Unknown'}: {e!s}",
                        exc_info=True,
                    )
                    skipped_documents.append(
                        f"{elasticsearch_doc.title if 'elasticsearch_doc' in locals() else 'Unknown'} (processing error)"
                    )
                    documents_skipped += 1
                    continue

            logger.info(f"Fetched {doc_count} documents from Elasticsearch")

        except Exception as e:
            logger.error(f"Error fetching documents from Elasticsearch: {e}")
            await task_logger.log_task_failure(
                log_entry,
                f"Error fetching documents from Elasticsearch: {e}",
                "Fetch error",
                {"error_type": "FetchError"},
            )
            return 0, f"Error fetching documents from Elasticsearch: {e}"
        finally:
            await elasticsearch_connector.disconnect()

        total_processed = documents_indexed
        if total_processed > 0:
            await update_connector_last_indexed(session, connector, update_last_indexed)

        await session.commit()

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Elasticsearch indexing for connector {connector_id}",
            {
                "documents_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "skipped_documents_count": len(skipped_documents),
            },
        )

        logger.info(
            f"Elasticsearch indexing completed: {documents_indexed} new documents, {documents_skipped} skipped"
        )
        return total_processed, None

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Elasticsearch indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Elasticsearch documents for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Elasticsearch documents: {e!s}", exc_info=True)
        return 0, f"Failed to index Elasticsearch documents: {e!s}"
