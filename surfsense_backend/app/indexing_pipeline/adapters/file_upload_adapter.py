from sqlalchemy.ext.asyncio import AsyncSession

from app.db import DocumentStatus, DocumentType
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService


async def index_uploaded_file(
    markdown_content: str,
    filename: str,
    etl_service: str,
    search_space_id: int,
    user_id: str,
    session: AsyncSession,
    llm,
) -> None:
    connector_doc = ConnectorDocument(
        title=filename,
        source_markdown=markdown_content,
        unique_id=filename,
        document_type=DocumentType.FILE,
        search_space_id=search_space_id,
        created_by_id=user_id,
        connector_id=None,
        should_summarize=True,
        should_use_code_chunker=False,
        fallback_summary=markdown_content[:4000],
        metadata={
            "FILE_NAME": filename,
            "ETL_SERVICE": etl_service,
        },
    )

    service = IndexingPipelineService(session)
    documents = await service.prepare_for_indexing([connector_doc])

    if not documents:
        raise RuntimeError("prepare_for_indexing returned no documents")

    indexed = await service.index(documents[0], connector_doc, llm)

    if not DocumentStatus.is_state(indexed.status, DocumentStatus.READY):
        raise RuntimeError(indexed.status.get("reason", "Indexing failed"))

    indexed.content_needs_reindexing = False
    await session.commit()
