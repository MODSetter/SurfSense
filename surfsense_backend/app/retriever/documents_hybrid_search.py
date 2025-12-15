from datetime import datetime


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

        return documents

    async def hybrid_search(
        self,
        query_text: str,
        top_k: int,
        search_space_id: int,
        document_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
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

        """
        from sqlalchemy import func, select, text
        from sqlalchemy.orm import joinedload

        from app.config import config
        from app.db import Chunk, Document, DocumentType

        # Get embedding for the query
        embedding_model = config.embedding_model_instance
        query_embedding = embedding_model.embed(query_text)

        # RRF constants
        k = 60
        n_results = top_k * 2  # Fetch extra documents for better fusion

        # Create tsvector and tsquery for PostgreSQL full-text search
        tsvector = func.to_tsvector("english", Document.content)
        tsquery = func.plainto_tsquery("english", query_text)

        # Base conditions for document filtering - search space is required
        base_conditions = [Document.search_space_id == search_space_id]

        # Add document type filter if provided
        if document_type is not None:
            # Convert string to enum value if needed
            if isinstance(document_type, str):
                try:
                    doc_type_enum = DocumentType[document_type]
                    base_conditions.append(Document.document_type == doc_type_enum)
                except KeyError:
                    # If the document type doesn't exist in the enum, return empty results
                    return []
            else:
                base_conditions.append(Document.document_type == document_type)

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

        # Collect document IDs for chunk fetching
        doc_ids: list[int] = [doc.id for doc, _score in documents_with_scores]

        # Fetch ALL chunks for these documents in a single query
        chunks_query = (
            select(Chunk)
            .options(joinedload(Chunk.document))
            .where(Chunk.document_id.in_(doc_ids))
            .order_by(Chunk.document_id, Chunk.id)
        )
        chunks_result = await self.db_session.execute(chunks_query)
        chunks = chunks_result.scalars().all()

        # Assemble doc-grouped results
        doc_map: dict[int, dict] = {
            doc.id: {
                "document_id": doc.id,
                "content": "",
                "score": float(score),
                "chunks": [],
                "document": {
                    "id": doc.id,
                    "title": doc.title,
                    "document_type": doc.document_type.value
                    if getattr(doc, "document_type", None)
                    else None,
                    "metadata": doc.document_metadata or {},
                },
                "source": doc.document_type.value
                if getattr(doc, "document_type", None)
                else None,
            }
            for doc, score in documents_with_scores
        }

        for chunk in chunks:
            doc_id = chunk.document_id
            if doc_id not in doc_map:
                continue
            doc_map[doc_id]["chunks"].append(
                {"chunk_id": chunk.id, "content": chunk.content}
            )

        # Fill concatenated content (useful for reranking)
        final_docs: list[dict] = []
        for doc_id in doc_ids:
            entry = doc_map[doc_id]
            entry["content"] = "\n\n".join(
                c["content"] for c in entry.get("chunks", []) if c.get("content")
            )
            final_docs.append(entry)

        return final_docs
