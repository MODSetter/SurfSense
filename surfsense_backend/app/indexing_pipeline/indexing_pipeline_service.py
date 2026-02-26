import contextlib
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Chunk, Document, DocumentStatus
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.document_chunker import chunk_text
from app.indexing_pipeline.document_embedder import embed_text
from app.indexing_pipeline.document_hashing import (
    compute_content_hash,
    compute_unique_identifier_hash,
)
from app.indexing_pipeline.document_persistence import (
    attach_chunks_to_document,
    rollback_and_persist_failure,
)
from app.indexing_pipeline.document_summarizer import summarize_document
from app.indexing_pipeline.exceptions import (
    EMBEDDING_ERRORS,
    PERMANENT_LLM_ERRORS,
    RETRYABLE_LLM_ERRORS,
    PipelineMessages,
    embedding_message,
    llm_permanent_message,
    llm_retryable_message,
    safe_exception_message,
)
from app.indexing_pipeline.pipeline_logger import (
    PipelineLogContext,
    log_batch_aborted,
    log_chunking_overflow,
    log_doc_skipped_unknown,
    log_document_queued,
    log_document_requeued,
    log_document_updated,
    log_embedding_error,
    log_index_started,
    log_index_success,
    log_permanent_llm_error,
    log_race_condition,
    log_retryable_llm_error,
    log_unexpected_error,
)


class IndexingPipelineService:
    """Single pipeline for indexing connector documents. All connectors use this service."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def prepare_for_indexing(
        self, connector_docs: list[ConnectorDocument]
    ) -> list[Document]:
        """
        Persist new documents and detect changes, returning only those that need indexing.
        """
        documents = []
        seen_hashes: set[str] = set()
        batch_ctx = PipelineLogContext(
            connector_id=connector_docs[0].connector_id if connector_docs else 0,
            search_space_id=connector_docs[0].search_space_id if connector_docs else 0,
            unique_id="batch",
        )

        for connector_doc in connector_docs:
            ctx = PipelineLogContext(
                connector_id=connector_doc.connector_id,
                search_space_id=connector_doc.search_space_id,
                unique_id=connector_doc.unique_id,
            )
            try:
                unique_identifier_hash = compute_unique_identifier_hash(connector_doc)
                content_hash = compute_content_hash(connector_doc)

                if unique_identifier_hash in seen_hashes:
                    continue
                seen_hashes.add(unique_identifier_hash)

                result = await self.session.execute(
                    select(Document).filter(
                        Document.unique_identifier_hash == unique_identifier_hash
                    )
                )
                existing = result.scalars().first()

                if existing is not None:
                    if existing.content_hash == content_hash:
                        if existing.title != connector_doc.title:
                            existing.title = connector_doc.title
                            existing.updated_at = datetime.now(UTC)
                        if not DocumentStatus.is_state(
                            existing.status, DocumentStatus.READY
                        ):
                            existing.status = DocumentStatus.pending()
                            existing.updated_at = datetime.now(UTC)
                            documents.append(existing)
                            log_document_requeued(ctx)
                        continue

                    existing.title = connector_doc.title
                    existing.content_hash = content_hash
                    existing.source_markdown = connector_doc.source_markdown
                    existing.document_metadata = connector_doc.metadata
                    existing.updated_at = datetime.now(UTC)
                    existing.status = DocumentStatus.pending()
                    documents.append(existing)
                    log_document_updated(ctx)
                    continue

                duplicate = await self.session.execute(
                    select(Document).filter(Document.content_hash == content_hash)
                )
                if duplicate.scalars().first() is not None:
                    continue

                document = Document(
                    title=connector_doc.title,
                    document_type=connector_doc.document_type,
                    content="Pending...",
                    content_hash=content_hash,
                    unique_identifier_hash=unique_identifier_hash,
                    source_markdown=connector_doc.source_markdown,
                    document_metadata=connector_doc.metadata,
                    search_space_id=connector_doc.search_space_id,
                    connector_id=connector_doc.connector_id,
                    created_by_id=connector_doc.created_by_id,
                    updated_at=datetime.now(UTC),
                    status=DocumentStatus.pending(),
                )
                self.session.add(document)
                documents.append(document)
                log_document_queued(ctx)

            except Exception as e:
                log_doc_skipped_unknown(ctx, e)

        try:
            await self.session.commit()
            return documents
        except IntegrityError:
            # A concurrent worker committed a document with the same content_hash
            # or unique_identifier_hash between our check and our INSERT.
            # The document already exists — roll back and let the next sync run handle it.
            log_race_condition(batch_ctx)
            await self.session.rollback()
            return []
        except Exception as e:
            log_batch_aborted(batch_ctx, e)
            await self.session.rollback()
            return []

    async def index(
        self, document: Document, connector_doc: ConnectorDocument, llm
    ) -> Document:
        """
        Run summarization, embedding, and chunking for a document and persist the results.
        """
        ctx = PipelineLogContext(
            connector_id=connector_doc.connector_id,
            search_space_id=connector_doc.search_space_id,
            unique_id=connector_doc.unique_id,
            doc_id=document.id,
        )
        try:
            log_index_started(ctx)
            document.status = DocumentStatus.processing()
            await self.session.commit()

            if connector_doc.should_summarize and llm is not None:
                content = await summarize_document(
                    connector_doc.source_markdown, llm, connector_doc.metadata
                )
            elif connector_doc.should_summarize and connector_doc.fallback_summary:
                content = connector_doc.fallback_summary
            else:
                content = connector_doc.source_markdown

            embedding = embed_text(content)

            await self.session.execute(
                delete(Chunk).where(Chunk.document_id == document.id)
            )

            chunks = [
                Chunk(content=text, embedding=embed_text(text))
                for text in chunk_text(
                    connector_doc.source_markdown,
                    use_code_chunker=connector_doc.should_use_code_chunker,
                )
            ]

            document.content = content
            document.embedding = embedding
            attach_chunks_to_document(document, chunks)
            document.updated_at = datetime.now(UTC)
            document.status = DocumentStatus.ready()
            await self.session.commit()
            log_index_success(ctx, chunk_count=len(chunks))

        except RETRYABLE_LLM_ERRORS as e:
            log_retryable_llm_error(ctx, e)
            await rollback_and_persist_failure(
                self.session, document, llm_retryable_message(e)
            )

        except PERMANENT_LLM_ERRORS as e:
            log_permanent_llm_error(ctx, e)
            await rollback_and_persist_failure(
                self.session, document, llm_permanent_message(e)
            )

        except RecursionError as e:
            log_chunking_overflow(ctx, e)
            await rollback_and_persist_failure(
                self.session, document, PipelineMessages.CHUNKING_OVERFLOW
            )

        except EMBEDDING_ERRORS as e:
            log_embedding_error(ctx, e)
            await rollback_and_persist_failure(
                self.session, document, embedding_message(e)
            )

        except Exception as e:
            log_unexpected_error(ctx, e)
            await rollback_and_persist_failure(
                self.session, document, safe_exception_message(e)
            )

        with contextlib.suppress(Exception):
            await self.session.refresh(document)

        return document
