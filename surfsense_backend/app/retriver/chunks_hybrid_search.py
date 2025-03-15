class ChucksHybridSearchRetriever:
    def __init__(self, db_session):
        """
        Initialize the hybrid search retriever with a database session.
        
        Args:
            db_session: SQLAlchemy AsyncSession from FastAPI dependency injection
        """
        self.db_session = db_session

    async def vector_search(self, query_text: str, top_k: int, user_id: str, search_space_id: int = None) -> list:
        """
        Perform vector similarity search on chunks.
        
        Args:
            query_text: The search query text
            top_k: Number of results to return
            user_id: The ID of the user performing the search
            search_space_id: Optional search space ID to filter results
            
        Returns:
            List of chunks sorted by vector similarity
        """
        from sqlalchemy import select, func
        from sqlalchemy.orm import joinedload
        from app.db import Chunk, Document, SearchSpace
        from app.config import config
        
        # Get embedding for the query
        embedding_model = config.embedding_model_instance
        query_embedding = embedding_model.embed(query_text)
        
        # Build the base query with user ownership check
        query = (
            select(Chunk)
            .options(joinedload(Chunk.document).joinedload(Document.search_space))
            .join(Document, Chunk.document_id == Document.id)
            .join(SearchSpace, Document.search_space_id == SearchSpace.id)
            .where(SearchSpace.user_id == user_id)
        )
        
        # Add search space filter if provided
        if search_space_id is not None:
            query = query.where(Document.search_space_id == search_space_id)
        
        # Add vector similarity ordering
        query = (
            query
            .order_by(Chunk.embedding.op("<=>")(query_embedding))
            .limit(top_k)
        )
        
        # Execute the query
        result = await self.db_session.execute(query)
        chunks = result.scalars().all()
        
        return chunks

    async def full_text_search(self, query_text: str, top_k: int, user_id: str, search_space_id: int = None) -> list:
        """
        Perform full-text keyword search on chunks.
        
        Args:
            query_text: The search query text
            top_k: Number of results to return
            user_id: The ID of the user performing the search
            search_space_id: Optional search space ID to filter results
            
        Returns:
            List of chunks sorted by text relevance
        """
        from sqlalchemy import select, func, text
        from sqlalchemy.orm import joinedload
        from app.db import Chunk, Document, SearchSpace
        
        # Create tsvector and tsquery for PostgreSQL full-text search
        tsvector = func.to_tsvector('english', Chunk.content)
        tsquery = func.plainto_tsquery('english', query_text)
        
        # Build the base query with user ownership check
        query = (
            select(Chunk)
            .options(joinedload(Chunk.document).joinedload(Document.search_space))
            .join(Document, Chunk.document_id == Document.id)
            .join(SearchSpace, Document.search_space_id == SearchSpace.id)
            .where(SearchSpace.user_id == user_id)
            .where(tsvector.op("@@")(tsquery))  # Only include results that match the query
        )
        
        # Add search space filter if provided
        if search_space_id is not None:
            query = query.where(Document.search_space_id == search_space_id)
        
        # Add text search ranking
        query = (
            query
            .order_by(func.ts_rank_cd(tsvector, tsquery).desc())
            .limit(top_k)
        )
        
        # Execute the query
        result = await self.db_session.execute(query)
        chunks = result.scalars().all()
        
        return chunks

    async def hybrid_search(self, query_text: str, top_k: int, user_id: str, search_space_id: int = None, document_type: str = None) -> list:
        """
        Combine vector similarity and full-text search results using Reciprocal Rank Fusion.
        
        Args:
            query_text: The search query text
            top_k: Number of results to return
            user_id: The ID of the user performing the search
            search_space_id: Optional search space ID to filter results
            document_type: Optional document type to filter results (e.g., "FILE", "CRAWLED_URL")
            
        Returns:
            List of dictionaries containing chunk data and relevance scores
        """
        from sqlalchemy import select, func, text
        from sqlalchemy.orm import joinedload
        from app.db import Chunk, Document, SearchSpace, DocumentType
        from app.config import config
        
        # Get embedding for the query
        embedding_model = config.embedding_model_instance
        query_embedding = embedding_model.embed(query_text)
        
        # Constants for RRF calculation
        k = 60  # Constant for RRF calculation
        n_results = top_k * 2  # Get more results for better fusion
        
        # Create tsvector and tsquery for PostgreSQL full-text search
        tsvector = func.to_tsvector('english', Chunk.content)
        tsquery = func.plainto_tsquery('english', query_text)
        
        # Base conditions for document filtering
        base_conditions = [SearchSpace.user_id == user_id]
        
        # Add search space filter if provided
        if search_space_id is not None:
            base_conditions.append(Document.search_space_id == search_space_id)
            
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
        
        # CTE for semantic search with user ownership check
        semantic_search_cte = (
            select(
                Chunk.id,
                func.rank().over(order_by=Chunk.embedding.op("<=>")(query_embedding)).label("rank")
            )
            .join(Document, Chunk.document_id == Document.id)
            .join(SearchSpace, Document.search_space_id == SearchSpace.id)
            .where(*base_conditions)
        )
        
        semantic_search_cte = (
            semantic_search_cte
            .order_by(Chunk.embedding.op("<=>")(query_embedding))
            .limit(n_results)
            .cte("semantic_search")
        )
        
        # CTE for keyword search with user ownership check
        keyword_search_cte = (
            select(
                Chunk.id,
                func.rank().over(order_by=func.ts_rank_cd(tsvector, tsquery).desc()).label("rank")
            )
            .join(Document, Chunk.document_id == Document.id)
            .join(SearchSpace, Document.search_space_id == SearchSpace.id)
            .where(*base_conditions)
            .where(tsvector.op("@@")(tsquery))
        )
        
        keyword_search_cte = (
            keyword_search_cte
            .order_by(func.ts_rank_cd(tsvector, tsquery).desc())
            .limit(n_results)
            .cte("keyword_search")
        )
        
        # Final combined query using a FULL OUTER JOIN with RRF scoring
        final_query = (
            select(
                Chunk,
                (
                    func.coalesce(1.0 / (k + semantic_search_cte.c.rank), 0.0) +
                    func.coalesce(1.0 / (k + keyword_search_cte.c.rank), 0.0)
                ).label("score")
            )
            .select_from(
                semantic_search_cte.outerjoin(
                    keyword_search_cte, 
                    semantic_search_cte.c.id == keyword_search_cte.c.id,
                    full=True
                )
            )
            .join(
                Chunk,
                Chunk.id == func.coalesce(semantic_search_cte.c.id, keyword_search_cte.c.id)
            )
            .options(joinedload(Chunk.document))
            .order_by(text("score DESC"))
            .limit(top_k)
        )
        
        # Execute the query
        result = await self.db_session.execute(final_query)
        chunks_with_scores = result.all()
        
        # If no results were found, return an empty list
        if not chunks_with_scores:
            return []
        
        # Convert to serializable dictionaries if no reranker is available or if reranking failed
        serialized_results = []
        for chunk, score in chunks_with_scores:
            serialized_results.append({
                "chunk_id": chunk.id,
                "content": chunk.content,
                "score": float(score),  # Ensure score is a Python float
                "document": {
                    "id": chunk.document.id,
                    "title": chunk.document.title,
                    "document_type": chunk.document.document_type.value if hasattr(chunk.document, 'document_type') else None,
                    "metadata": chunk.document.document_metadata
                }
            })
        
        return serialized_results
