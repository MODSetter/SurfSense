import contextlib
import time
from datetime import datetime

from app.utils.perf import get_perf_logger

_MAX_FETCH_CHUNKS_PER_DOC = 20


class DocumentHybridSearchRetriever:
    def __init__(self, db_session):
        """
        Initialize the hybrid search retriever with a database session.

        Args:
            db_session: SQLAlchemy AsyncSession from FastAPI dependency injection
        """
        self.db_session = db_session

    async def vector_search(
        self,
        query_text: str,
        top_k: int,
        search_space_id: int,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list:
        """
        Perform vector similarity search on documents.

        Args:
            query_text: The search query text
            top_k: Number of results to return
            search_space_id: The search space ID to search within
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            List of documents sorted by vector similarity
        """
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        from app.config import config
        from app.db import Document

        perf = get_perf_logger()
        t0 = time.perf_counter()

        # Get embedding for the query
        embedding_model = config.embedding_model_instance
        query_embedding = embedding_model.embed(query_text)

        # Build the query filtered by search space
        query = (
            select(Document)
            .options(joinedload(Document.search_space))
            .where(Document.search_space_id == search_space_id)
        )

        # Add time-based filtering if provided
        if start_date is not None:
            query = query.where(Document.updated_at >= start_date)
        if end_date is not None:
            query = query.where(Document.updated_at <= end_date)

        # Add vector similarity ordering
        query = query.order_by(Document.embedding.op("<=>")(query_embedding)).limit(
            top_k
        )

        # Execute the query
        result = await self.db_session.execute(query)
        documents = result.scalars().all()
        perf.info(
            "[doc_search] vector_search in %.3fs results=%d space=%d",
            time.perf_counter() - t0,
            len(documents),
            search_space_id,
        )

        return documents

    async def full_text_search(
        self,
        query_text: str,
        top_k: int,
        search_space_id: int,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list:
        """
        Perform full-text keyword search on documents.

        Args:
            query_text: The search query text
            top_k: Number of results to return
            search_space_id: The search space ID to search within
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            List of documents sorted by text relevance
        """
        from sqlalchemy import func, select
        from sqlalchemy.orm import joinedload

        from app.db import Document

        perf = get_perf_logger()
        t0 = time.perf_counter()

        # Create tsvector and tsquery for PostgreSQL full-text search
        tsvector = func.to_tsvector("english", Document.content)
        tsquery = func.plainto_tsquery("english", query_text)

        # Build the query filtered by search space
        query = (
            select(Document)
            .options(joinedload(Document.search_space))
            .where(Document.search_space_id == search_space_id)
            .where(
                tsvector.op("@@")(tsquery)
            )  # Only include results that match the query
        )

        # Add time-based filtering if provided
        if start_date is not None:
            query = query.where(Document.updated_at >= start_date)
        if end_date is not None:
            query = query.where(Document.updated_at <= end_date)

        # Add text search ranking
        query = query.order_by(func.ts_rank_cd(tsvector, tsquery).desc()).limit(top_k)

        # Execute the query
        result = await self.db_session.execute(query)
        documents = result.scalars().all()
        perf.info(
            "[doc_search] full_text_search in %.3fs results=%d space=%d",
            time.perf_counter() - t0,
            len(documents),
            search_space_id,
        )

        return documents

    async def hybrid_search(
        self,
        query_text: str,
        top_k: int,
        search_space_id: int,
        document_type: str | list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        query_embedding: list | None = None,
    ) -> list:
        """
        Hybrid search that returns **documents** (not individual chunks).

        Each returned item is a document-grouped dict that preserves real DB chunk IDs so
        downstream agents can cite with `[citation:<chunk_id>]`.

        Args:
            query_text: The search query text
            top_k: Number of documents to return
            search_space_id: The search space ID to search within
            document_type: Optional document type to filter results (e.g., "FILE", "CRAWLED_URL")
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at
            query_embedding: Pre-computed embedding vector. If None, will be computed here.
        """
        from sqlalchemy import func, select, text
        from sqlalchemy.orm import joinedload

        from app.config import config
        from app.db import Chunk, Document, DocumentType

        perf = get_perf_logger()
        t0 = time.perf_counter()

        if query_embedding is None:
            embedding_model = config.embedding_model_instance
            query_embedding = embedding_model.embed(query_text)

        # RRF constants
        k = 60
        n_results = top_k * 2  # Fetch extra documents for better fusion

        # Create tsvector and tsquery for PostgreSQL full-text search
        tsvector = func.to_tsvector("english", Document.content)
        tsquery = func.plainto_tsquery("english", query_text)

        # Base conditions for document filtering - search space is required.
        # Exclude documents in "deleting" state (background deletion in progress).
        base_conditions = [
            Document.search_space_id == search_space_id,
            func.coalesce(Document.status["state"].astext, "ready") != "deleting",
        ]

        # Add document type filter if provided (single string or list of strings)
        if document_type is not None:
            type_list = (
                document_type if isinstance(document_type, list) else [document_type]
            )
            doc_type_enums = []
            for dt in type_list:
                if isinstance(dt, str):
                    with contextlib.suppress(KeyError):
                        doc_type_enums.append(DocumentType[dt])
                else:
                    doc_type_enums.append(dt)
            if not doc_type_enums:
                return []
            if len(doc_type_enums) == 1:
                base_conditions.append(Document.document_type == doc_type_enums[0])
            else:
                base_conditions.append(Document.document_type.in_(doc_type_enums))

        # Add time-based filtering if provided
        if start_date is not None:
            base_conditions.append(Document.updated_at >= start_date)
        if end_date is not None:
            base_conditions.append(Document.updated_at <= end_date)

        # CTE for semantic search filtered by search space
        semantic_search_cte = select(
            Document.id,
            func.rank()
            .over(order_by=Document.embedding.op("<=>")(query_embedding))
            .label("rank"),
        ).where(*base_conditions)

        semantic_search_cte = (
            semantic_search_cte.order_by(Document.embedding.op("<=>")(query_embedding))
            .limit(n_results)
            .cte("semantic_search")
        )

        # CTE for keyword search filtered by search space
        keyword_search_cte = (
            select(
                Document.id,
                func.rank()
                .over(order_by=func.ts_rank_cd(tsvector, tsquery).desc())
                .label("rank"),
            )
            .where(*base_conditions)
            .where(tsvector.op("@@")(tsquery))
        )

        keyword_search_cte = (
            keyword_search_cte.order_by(func.ts_rank_cd(tsvector, tsquery).desc())
            .limit(n_results)
            .cte("keyword_search")
        )

        # Final combined query using a FULL OUTER JOIN with RRF scoring
        final_query = (
            select(
                Document,
                (
                    func.coalesce(1.0 / (k + semantic_search_cte.c.rank), 0.0)
                    + func.coalesce(1.0 / (k + keyword_search_cte.c.rank), 0.0)
                ).label("score"),
            )
            .select_from(
                semantic_search_cte.outerjoin(
                    keyword_search_cte,
                    semantic_search_cte.c.id == keyword_search_cte.c.id,
                    full=True,
                )
            )
            .join(
                Document,
                Document.id
                == func.coalesce(semantic_search_cte.c.id, keyword_search_cte.c.id),
            )
            .options(joinedload(Document.search_space))
            .order_by(text("score DESC"))
            .limit(top_k)
        )

        # Execute the query
        result = await self.db_session.execute(final_query)
        documents_with_scores = result.all()

        # If no results were found, return an empty list
        if not documents_with_scores:
            return []

        # Collect document IDs and pre-cache metadata from the small RRF
        # result set so the bulk chunk fetch can skip joinedload entirely.
        doc_ids: list[int] = [doc.id for doc, _score in documents_with_scores]
        doc_meta_cache: dict[int, dict] = {}
        doc_score_cache: dict[int, float] = {}
        doc_source_cache: dict[int, str | None] = {}
        for doc, score in documents_with_scores:
            doc_meta_cache[doc.id] = {
                "id": doc.id,
                "title": doc.title,
                "document_type": doc.document_type.value
                if getattr(doc, "document_type", None)
                else None,
                "metadata": doc.document_metadata or {},
            }
            doc_score_cache[doc.id] = float(score)
            doc_source_cache[doc.id] = (
                doc.document_type.value if getattr(doc, "document_type", None) else None
            )

        # SQL-level per-document chunk limit using ROW_NUMBER().
        # Avoids loading hundreds of chunks per large document only to
        # discard them in Python.
        numbered = (
            select(
                Chunk.id.label("chunk_id"),
                func.row_number()
                .over(partition_by=Chunk.document_id, order_by=Chunk.id)
                .label("rn"),
            )
            .where(Chunk.document_id.in_(doc_ids))
            .subquery("numbered")
        )

        # Select only the columns we need (skip Chunk.embedding ~12KB/row).
        chunks_query = (
            select(Chunk.id, Chunk.content, Chunk.document_id)
            .join(numbered, Chunk.id == numbered.c.chunk_id)
            .where(numbered.c.rn <= _MAX_FETCH_CHUNKS_PER_DOC)
            .order_by(Chunk.document_id, Chunk.id)
        )

        t_fetch = time.perf_counter()
        chunks_result = await self.db_session.execute(chunks_query)
        fetched_chunks = chunks_result.all()
        perf.debug(
            "[doc_search] chunk fetch in %.3fs rows=%d",
            time.perf_counter() - t_fetch,
            len(fetched_chunks),
        )

        # Assemble doc-grouped results using pre-cached metadata.
        doc_map: dict[int, dict] = {
            doc_id: {
                "document_id": doc_id,
                "content": "",
                "score": doc_score_cache.get(doc_id, 0.0),
                "chunks": [],
                "matched_chunk_ids": [],
                "document": doc_meta_cache.get(doc_id, {}),
                "source": doc_source_cache.get(doc_id),
            }
            for doc_id in doc_ids
        }

        for row in fetched_chunks:
            doc_id = row.document_id
            if doc_id not in doc_map:
                continue
            doc_map[doc_id]["chunks"].append(
                {"chunk_id": row.id, "content": row.content}
            )

        # Fill concatenated content (useful for reranking)
        final_docs: list[dict] = []
        for doc_id in doc_ids:
            entry = doc_map[doc_id]
            entry["content"] = "\n\n".join(
                c["content"] for c in entry.get("chunks", []) if c.get("content")
            )
            final_docs.append(entry)

        perf.info(
            "[doc_search] hybrid_search TOTAL in %.3fs docs=%d space=%d type=%s",
            time.perf_counter() - t0,
            len(final_docs),
            search_space_id,
            document_type,
        )
        return final_docs
