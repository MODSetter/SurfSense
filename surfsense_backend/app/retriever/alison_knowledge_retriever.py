from sqlalchemy import func, select, text
from sqlalchemy.orm import joinedload

from app.config import config
from app.db import Chunk, Document, DocumentType, SearchSpace, User

class AlisonKnowledgeRetriever:
    def __init__(self, db_session):
        self.db_session = db_session

    async def hybrid_search(self, query_text: str, top_k: int) -> list:
        # Get the "alison" user and "Alison's Knowledge Base" search space
        result = await self.db_session.execute(select(User).where(User.email == "alison@surfsense.ai"))
        alison_user = await (await result.scalars()).first()
        if not alison_user:
            return []

        result = await self.db_session.execute(select(SearchSpace).where(SearchSpace.name == "Alison's Knowledge Base"))
        alison_search_space = await (await result.scalars()).first()
        if not alison_search_space:
            return []

        embedding_model = config.embedding_model_instance
        query_embedding = embedding_model.embed(query_text)

        k = 60
        n_results = top_k * 2

        tsvector = func.to_tsvector("english", Chunk.content)
        tsquery = func.plainto_tsquery("english", query_text)

        base_conditions = [
            SearchSpace.user_id == alison_user.id,
            Document.search_space_id == alison_search_space.id,
        ]

        semantic_search_cte = (
            select(
                Chunk.id,
                func.rank()
                .over(order_by=Chunk.embedding.op("<=>")(query_embedding))
                .label("rank"),
            )
            .join(Document, Chunk.document_id == Document.id)
            .join(SearchSpace, Document.search_space_id == SearchSpace.id)
            .where(*base_conditions)
        )

        semantic_search_cte = (
            semantic_search_cte.order_by(Chunk.embedding.op("<=>")(query_embedding))
            .limit(n_results)
            .cte("semantic_search")
        )

        keyword_search_cte = (
            select(
                Chunk.id,
                func.rank()
                .over(order_by=func.ts_rank_cd(tsvector, tsquery).desc())
                .label("rank"),
            )
            .join(Document, Chunk.document_id == Document.id)
            .join(SearchSpace, Document.search_space_id == SearchSpace.id)
            .where(*base_conditions)
            .where(tsvector.op("@@")(tsquery))
        )

        keyword_search_cte = (
            keyword_search_cte.order_by(func.ts_rank_cd(tsvector, tsquery).desc())
            .limit(n_results)
            .cte("keyword_search")
        )

        final_query = (
            select(
                Chunk,
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
                Chunk,
                Chunk.id
                == func.coalesce(semantic_search_cte.c.id, keyword_search_cte.c.id),
            )
            .options(joinedload(Chunk.document))
            .order_by(text("score DESC"))
            .limit(top_k)
        )

        result = await self.db_session.execute(final_query)
        chunks_with_scores = (await result.all())

        if not chunks_with_scores:
            return []

        serialized_results = []
        for chunk, score in chunks_with_scores:
            serialized_results.append(
                {
                    "chunk_id": chunk.id,
                    "content": chunk.content,
                    "score": float(score),
                    "document": {
                        "id": chunk.document.id,
                        "title": chunk.document.title,
                        "document_type": chunk.document.document_type.value
                        if hasattr(chunk.document, "document_type")
                        else None,
                        "metadata": chunk.document.document_metadata,
                    },
                }
            )

        return serialized_results
