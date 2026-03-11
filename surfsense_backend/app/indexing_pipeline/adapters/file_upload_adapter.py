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
        search_space_id: int,
        user_id: str,
        llm,
        should_summarize: bool = False,
    ) -> None:
        connector_doc = ConnectorDocument(
            title=filename,
            source_markdown=markdown_content,
            unique_id=filename,
            document_type=DocumentType.FILE,
            search_space_id=search_space_id,
            created_by_id=user_id,
            connector_id=None,
            should_summarize=should_summarize,
            should_use_code_chunker=False,
            fallback_summary=markdown_content[:4000],
            metadata={
                "FILE_NAME": filename,
                "ETL_SERVICE": etl_service,
            },
        )

        documents = await self._service.prepare_for_indexing([connector_doc])

        if not documents:
            raise RuntimeError("prepare_for_indexing returned no documents")

        indexed = await self._service.index(documents[0], connector_doc, llm)

        if not DocumentStatus.is_state(indexed.status, DocumentStatus.READY):
            raise RuntimeError(indexed.status.get("reason", "Indexing failed"))

        indexed.content_needs_reindexing = False
        await self._session.commit()

    async def reindex(self, document: Document, llm) -> None:
        """Re-index an existing document after its source_markdown has been updated."""
        if not document.source_markdown:
            raise RuntimeError("Document has no source_markdown to reindex")

        metadata = document.document_metadata or {}

        connector_doc = ConnectorDocument(
            title=document.title,
            source_markdown=document.source_markdown,
            unique_id=document.title,
            document_type=document.document_type,
            search_space_id=document.search_space_id,
            created_by_id=str(document.created_by_id),
            connector_id=document.connector_id,
            should_summarize=True,
            should_use_code_chunker=False,
            fallback_summary=document.source_markdown[:4000],
            metadata=metadata,
        )

        document.content_hash = compute_content_hash(connector_doc)

        indexed = await self._service.index(document, connector_doc, llm)

        if not DocumentStatus.is_state(indexed.status, DocumentStatus.READY):
            raise RuntimeError(indexed.status.get("reason", "Reindexing failed"))

        indexed.content_needs_reindexing = False
        await self._session.commit()
