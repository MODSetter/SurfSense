from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentStatus, DocumentType
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.document_hashing import compute_content_hash
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService


class UploadDocumentAdapter:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._service = IndexingPipelineService(session)

    async def index(
        self,
        markdown_content: str,
        filename: str,
        etl_service: str,
        workspace_id: int,
        user_id: str,
    ) -> None:
        connector_doc = ConnectorDocument(
            title=filename,
            source_markdown=markdown_content,
            unique_id=filename,
            document_type=DocumentType.FILE,
            workspace_id=workspace_id,
            created_by_id=user_id,
            connector_id=None,
            should_use_code_chunker=False,
            metadata={
                "FILE_NAME": filename,
                "ETL_SERVICE": etl_service,
            },
        )

        documents = await self._service.prepare_for_indexing([connector_doc])

        if not documents:
            raise RuntimeError("prepare_for_indexing returned no documents")

        indexed = await self._service.index(documents[0], connector_doc)

        if not DocumentStatus.is_state(indexed.status, DocumentStatus.READY):
            raise RuntimeError(indexed.status.get("reason", "Indexing failed"))

        indexed.content_needs_reindexing = False
        await self._session.commit()

    async def reindex(self, document: Document) -> None:
        """Re-index an existing document after its source_markdown has been updated."""
        if not document.source_markdown:
            raise RuntimeError("Document has no source_markdown to reindex")

        metadata = document.document_metadata or {}

        connector_doc = ConnectorDocument(
            title=document.title,
            source_markdown=document.source_markdown,
            unique_id=document.title,
            document_type=document.document_type,
            workspace_id=document.workspace_id,
            created_by_id=str(document.created_by_id),
            connector_id=document.connector_id,
            should_use_code_chunker=False,
            metadata=metadata,
        )

        document.content_hash = compute_content_hash(connector_doc)

        indexed = await self._service.index(document, connector_doc)

        if not DocumentStatus.is_state(indexed.status, DocumentStatus.READY):
            raise RuntimeError(indexed.status.get("reason", "Reindexing failed"))

        indexed.content_needs_reindexing = False
        await self._session.commit()
