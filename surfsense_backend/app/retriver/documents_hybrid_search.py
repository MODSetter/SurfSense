class DocumentHybridSearchRetriever:
    def __init__(self, db_session):
        """
        Initialize the hybrid search retriever with a database session.
        
        Args:
            db_session: SQLAlchemy AsyncSession from FastAPI dependency injection
        """
        self.db_session = db_session

    async def vector_search(self, query_text: str, top_k: int, user_id: str, search_space_id: int = None) -> list:
        """
        Perform vector similarity search on documents.
        
        Args:
            query_text: The search query text
            top_k: Number of results to return
            user_id: The ID of the user performing the search
            search_space_id: Optional search space ID to filter results
            
        Returns:
            List of documents sorted by vector similarity
        """
        from sqlalchemy import select, func
        from sqlalchemy.orm import joinedload
        from app.db import Document, SearchSpace
        from app.config import config
        
        # Get embedding for the query
        embedding_model = config.embedding_model_instance
        query_embedding = embedding_model.embed(query_text)
        
        # Build the base query with user ownership check
        query = (
            select(Document)
            .options(joinedload(Document.search_space))
            .join(SearchSpace, Document.search_space_id == SearchSpace.id)
            .where(SearchSpace.user_id == user_id)
        )
        
        # Add search space filter if provided
        if search_space_id is not None:
            query = query.where(Document.search_space_id == search_space_id)
        
        # Add vector similarity ordering
        query = (
            query
            .order_by(Document.embedding.op("<=>")(query_embedding))
            .limit(top_k)
        )
        
        # Execute the query
        result = await self.db_session.execute(query)
        documents = result.scalars().all()
        
        return documents

    async def full_text_search(self, query_text: str, top_k: int, user_id: str, search_space_id: int = None) -> list:
        """
        Perform full-text keyword search on documents.
        
        Args:
            query_text: The search query text
            top_k: Number of results to return
            user_id: The ID of the user performing the search
            search_space_id: Optional search space ID to filter results
            
        Returns:
            List of documents sorted by text relevance
        """
        from sqlalchemy import select, func, text
        from sqlalchemy.orm import joinedload
        from app.db import Document, SearchSpace
        
        # Create tsvector and tsquery for PostgreSQL full-text search
        tsvector = func.to_tsvector('english', Document.content)
        tsquery = func.plainto_tsquery('english', query_text)
        
        # Build the base query with user ownership check
        query = (
            select(Document)
            .options(joinedload(Document.search_space))
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
        documents = result.scalars().all()
        
        return documents

    async def hybrid_search(self, query_text: str, top_k: int, user_id: str, search_space_id: int = None, document_type: str = None) -> list:
        """
        Combine vector similarity and full-text search results using Reciprocal Rank Fusion.
        
        Args:
            query_text: The search query text
            top_k: Number of results to return
            user_id: The ID of the user performing the search
            search_space_id: Optional search space ID to filter results
            document_type: Optional document type to filter results (e.g., "FILE", "CRAWLED_URL")
            
        """
        from sqlalchemy import select, func, text
        from sqlalchemy.orm import joinedload
        from app.db import Document, SearchSpace, DocumentType
        from app.config import config
        
        # Get embedding for the query
        embedding_model = config.embedding_model_instance
        query_embedding = embedding_model.embed(query_text)
        
        # Constants for RRF calculation
        k = 60  # Constant for RRF calculation
        n_results = top_k * 2  # Get more results for better fusion
        
        # Create tsvector and tsquery for PostgreSQL full-text search
        tsvector = func.to_tsvector('english', Document.content)
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
                Document.id,
                func.rank().over(order_by=Document.embedding.op("<=>")(query_embedding)).label("rank")
            )
            .join(SearchSpace, Document.search_space_id == SearchSpace.id)
            .where(*base_conditions)
        )
        
        semantic_search_cte = (
            semantic_search_cte
            .order_by(Document.embedding.op("<=>")(query_embedding))
            .limit(n_results)
            .cte("semantic_search")
        )
        
        # CTE for keyword search with user ownership check
        keyword_search_cte = (
            select(
                Document.id,
                func.rank().over(order_by=func.ts_rank_cd(tsvector, tsquery).desc()).label("rank")
            )
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
                Document,
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
                Document,
                Document.id == func.coalesce(semantic_search_cte.c.id, keyword_search_cte.c.id)
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
        
        # Convert to serializable dictionaries
        serialized_results = []
        for document, score in documents_with_scores:
            # Fetch associated chunks for this document
            from sqlalchemy import select
            from app.db import Chunk
            
            chunks_query = select(Chunk).where(Chunk.document_id == document.id).order_by(Chunk.id)
            chunks_result = await self.db_session.execute(chunks_query)
            chunks = chunks_result.scalars().all()
            
            # Concatenate chunks content
            concatenated_chunks_content = " ".join([chunk.content for chunk in chunks]) if chunks else document.content
            
            serialized_results.append({
                "document_id": document.id,
                "title": document.title,
                "content": document.content,
                "chunks_content": concatenated_chunks_content,
                "document_type": document.document_type.value if hasattr(document, 'document_type') else None,
                "metadata": document.document_metadata,
                "score": float(score),  # Ensure score is a Python float
                "search_space_id": document.search_space_id
            })
        
        return serialized_results 