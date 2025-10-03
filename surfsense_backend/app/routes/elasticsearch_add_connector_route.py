import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.elasticsearch_connector import ElasticsearchConnector
from app.db import (
    Chunk,
    Document,
    SearchSourceConnector,
    SearchSourceConnectorType,
    get_async_session,
)
from app.schemas.users import User
from app.tasks.connector_indexers.elasticsearch_indexer import ElasticsearchIndexer
from app.users import current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/elasticsearch", tags=["elasticsearch"])


class ElasticsearchConnectorConfig(BaseModel):
    hostname: str
    port: int = 9200
    username: str | None = None
    password: str | None = None
    api_key: str | None = None
    ssl_enabled: bool = True
    indices: list[str] | None = None
    query: str = "*"
    search_fields: list[str] | None = None
    max_documents: int = 1000


@router.post("/add-connector")
async def add_elasticsearch_connector(
    connector_data: ElasticsearchConnectorConfig,
    current_user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Add a new Elasticsearch connector for the current user"""

    # Test the connection before saving
    elasticsearch_connector = ElasticsearchConnector(connector_data)

    try:
        connection_test = await elasticsearch_connector.test_connection()
        if not connection_test.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to connect to Elasticsearch: {connection_test.get('error')}",
            )
    except Exception as e:
        logger.error(f"Error testing Elasticsearch connection: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to test Elasticsearch connection: {e!s}",
        ) from e
    finally:
        await elasticsearch_connector.disconnect()

    try:
        # Check if connector already exists for this user
        existing_connector_result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.user_id == current_user.id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.ELASTICSEARCH,
            )
        )
        existing_connector = existing_connector_result.scalars().first()

        if existing_connector:
            # Update existing connector
            existing_connector.config = connector_data.model_dump()
            existing_connector.name = (
                f"Elasticsearch - {connector_data.hostname}:{connector_data.port}"
            )
            existing_connector.is_indexable = True
            logger.info(
                f"Updated existing Elasticsearch connector for user {current_user.id}"
            )
        else:
            # Create new connector
            new_connector = SearchSourceConnector(
                name=f"Elasticsearch - {connector_data.hostname}:{connector_data.port}",
                connector_type=SearchSourceConnectorType.ELASTICSEARCH,
                is_indexable=True,
                config=connector_data.model_dump(),
                user_id=current_user.id,
            )
            session.add(new_connector)
            logger.info(
                f"Created new Elasticsearch connector for user {current_user.id}"
            )

        await session.commit()

        # Get the connector (either existing or new) to return
        if existing_connector:
            connector = existing_connector
        else:
            await session.refresh(new_connector)
            connector = new_connector

        logger.info(
            f"Successfully saved Elasticsearch connector for user {current_user.id}"
        )

        return {
            "success": True,
            "message": "Elasticsearch connector added successfully",
            "connector": {
                "id": connector.id,
                "name": connector.name,
                "connector_type": connector.connector_type.value,
                "is_indexable": connector.is_indexable,
                "created_at": connector.created_at.isoformat()
                if connector.created_at
                else None,
                "last_indexed_at": connector.last_indexed_at.isoformat()
                if connector.last_indexed_at
                else None,
            },
        }

    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Integrity error: A connector with this configuration already exists. {e!s}",
        ) from e
    except Exception as e:
        logger.error(f"Failed to create Elasticsearch connector: {e!s}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create Elasticsearch connector: {e!s}",
        ) from e


@router.get("/connectors")
async def get_elasticsearch_connectors(
    current_user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Get all Elasticsearch connectors for the current user"""

    try:
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.user_id == current_user.id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.ELASTICSEARCH,
            )
        )
        connectors = result.scalars().all()

        connector_list = []
        for connector in connectors:
            connector_list.append(
                {
                    "id": connector.id,
                    "name": connector.name,
                    "connector_type": connector.connector_type.value,
                    "is_indexable": connector.is_indexable,
                    "created_at": connector.created_at.isoformat()
                    if connector.created_at
                    else None,
                    "last_indexed_at": connector.last_indexed_at.isoformat()
                    if connector.last_indexed_at
                    else None,
                    "config": {
                        "hostname": connector.config.get("hostname"),
                        "port": connector.config.get("port"),
                        "indices": connector.config.get("indices"),
                        # Don't expose sensitive credentials
                    },
                }
            )

        return {"success": True, "connectors": connector_list}

    except Exception as e:
        logger.error(f"Error fetching Elasticsearch connectors: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch Elasticsearch connectors",
        ) from e


@router.put("/connectors/{connector_id}")
async def update_elasticsearch_connector(
    connector_id: int,
    connector_data: ElasticsearchConnectorConfig,
    current_user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Update an existing Elasticsearch connector"""

    try:
        # Get the connector
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.user_id == current_user.id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.ELASTICSEARCH,
            )
        )
        connector = result.scalar_one_or_none()

        if not connector:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Elasticsearch connector not found",
            )

        # Test the new connection
        elasticsearch_connector = ElasticsearchConnector(connector_data)

        try:
            connection_test = await elasticsearch_connector.test_connection()
            if not connection_test.get("success"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to connect to Elasticsearch: {connection_test.get('error')}",
                )
        finally:
            await elasticsearch_connector.disconnect()

        # Update the connector
        connector.config = connector_data.model_dump()
        connector.name = (
            f"Elasticsearch - {connector_data.hostname}:{connector_data.port}"
        )

        await session.commit()
        await session.refresh(connector)

        return {
            "success": True,
            "message": "Elasticsearch connector updated successfully",
            "connector": {
                "id": connector.id,
                "name": connector.name,
                "connector_type": connector.connector_type.value,
                "is_indexable": connector.is_indexable,
                "created_at": connector.created_at.isoformat()
                if connector.created_at
                else None,
                "last_indexed_at": connector.last_indexed_at.isoformat()
                if connector.last_indexed_at
                else None,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating Elasticsearch connector: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update Elasticsearch connector",
        ) from e


@router.delete("/connectors/{connector_id}")
async def delete_elasticsearch_connector(
    connector_id: int,
    current_user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Delete an Elasticsearch connector"""

    try:
        # Get the connector
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.user_id == current_user.id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.ELASTICSEARCH,
            )
        )
        connector = result.scalar_one_or_none()

        if not connector:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Elasticsearch connector not found",
            )

        # Delete the connector
        await session.delete(connector)
        await session.commit()

        return {
            "success": True,
            "message": "Elasticsearch connector deleted successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting Elasticsearch connector: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete Elasticsearch connector",
        ) from e


@router.get("/test-connection")
async def test_elasticsearch_connection(
    hostname: str,
    port: int = 9200,
    username: str | None = None,
    password: str | None = None,
    api_key: str | None = None,
    ssl_enabled: bool = True,
    current_user: User = Depends(current_active_user),
) -> dict[str, Any]:
    """Test Elasticsearch connection with provided credentials"""

    config_data = ElasticsearchConnectorConfig(
        hostname=hostname,
        port=port,
        username=username,
        password=password,
        api_key=api_key,
        ssl_enabled=ssl_enabled,
    )

    elasticsearch_connector = ElasticsearchConnector(config_data)

    try:
        result = await elasticsearch_connector.test_connection()
        return result
    except Exception as e:
        logger.error(f"Error testing Elasticsearch connection: {e}")
        return {"success": False, "error": str(e)}
    finally:
        await elasticsearch_connector.disconnect()


@router.get("/indices")
async def get_elasticsearch_indices(
    hostname: str,
    port: int = 9200,
    username: str | None = None,
    password: str | None = None,
    api_key: str | None = None,
    ssl_enabled: bool = True,
    current_user: User = Depends(current_active_user),
) -> dict[str, Any]:
    """Get list of available Elasticsearch indices"""

    config_data = ElasticsearchConnectorConfig(
        hostname=hostname,
        port=port,
        username=username,
        password=password,
        api_key=api_key,
        ssl_enabled=ssl_enabled,
    )

    elasticsearch_connector = ElasticsearchConnector(config_data)

    try:
        if not await elasticsearch_connector.connect():
            return {"success": False, "error": "Failed to connect to Elasticsearch"}

        indices = await elasticsearch_connector.get_indices()
        return {"success": True, "indices": indices}
    except Exception as e:
        logger.error(f"Error fetching Elasticsearch indices: {e}")
        return {"success": False, "error": str(e)}
    finally:
        await elasticsearch_connector.disconnect()


@router.post("/index-connector/{connector_id}")
async def index_elasticsearch_connector(
    connector_id: int,
    search_space_id: int,
    current_user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """
    Index documents from an Elasticsearch connector into a search space
    """
    try:
        # Get the connector directly from database
        stmt = select(SearchSourceConnector).where(
            SearchSourceConnector.id == connector_id,
            SearchSourceConnector.user_id == current_user.id,
        )
        result = await session.execute(stmt)
        connector = result.scalar_one_or_none()

        if not connector:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connector {connector_id} not found",
            )

        if connector.connector_type != SearchSourceConnectorType.ELASTICSEARCH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Connector is not an Elasticsearch connector",
            )

        # Initialize the indexer
        indexer = ElasticsearchIndexer(connector.config)

        # Test connection first
        logger.info(f"Testing Elasticsearch connection for connector {connector_id}")
        connection_test = await indexer.test_connection()
        if not connection_test.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connection test failed: {connection_test.get('error')}",
            )

        # Index documents
        logger.info(f"Starting indexing for Elasticsearch connector {connector_id}")
        indexed_count = 0
        error_count = 0

        async for document in indexer.get_documents():
            try:
                # Create content hash
                content_hash = hashlib.sha256(document.content.encode()).hexdigest()

                # Check if document already exists
                existing_doc_stmt = select(Document).where(
                    Document.content_hash == content_hash,
                    Document.search_space_id == search_space_id,
                )
                existing_doc_result = await session.execute(existing_doc_stmt)
                if existing_doc_result.scalar_one_or_none():
                    logger.info(f"Document already exists, skipping: {document.title}")
                    continue

                # Generate embedding for document
                embedding = await config.embedding_model_instance.encode(
                    document.content
                )

                # Create document
                db_document = Document(
                    title=document.title,
                    content=document.content,
                    content_hash=content_hash,
                    document_type=document.document_type,
                    document_metadata=document.metadata,
                    search_space_id=search_space_id,
                    embedding=embedding,
                )
                session.add(db_document)
                await session.flush()  # Get the document ID

                # Create a single chunk with the entire document content
                chunk_embedding = await config.embedding_model_instance.encode(
                    document.content
                )
                db_chunk = Chunk(
                    content=document.content,
                    embedding=chunk_embedding,
                    document_id=db_document.id,
                )
                session.add(db_chunk)

                indexed_count += 1

                if indexed_count % 10 == 0:
                    logger.info(f"Indexed {indexed_count} Elasticsearch documents")
                    await session.commit()  # Periodic commit

            except Exception as e:
                logger.error(f"Error indexing document: {e}")
                error_count += 1

        await session.commit()

        # Update last_indexed_at timestamp
        update_stmt = (
            update(SearchSourceConnector)
            .where(SearchSourceConnector.id == connector_id)
            .values(last_indexed_at=datetime.now(UTC))
        )
        await session.execute(update_stmt)
        await session.commit()

        logger.info(
            f"Elasticsearch indexing completed: {indexed_count} documents indexed, {error_count} errors"
        )

        return {
            "success": True,
            "indexed_documents": indexed_count,
            "errors": error_count,
            "connector_id": connector_id,
            "search_space_id": search_space_id,
            "message": f"Successfully indexed {indexed_count} documents from Elasticsearch",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during Elasticsearch indexing: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during indexing: {e!s}",
        ) from e
