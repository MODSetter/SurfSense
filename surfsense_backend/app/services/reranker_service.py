import logging
from typing import Any, Optional

from rerankers import Document as RerankerDocument


class RerankerService:
    """
    Service for reranking documents using a configured reranker
    """

    def __init__(self, reranker_instance=None):
        """
        Initialize the reranker service

        Args:
            reranker_instance: The reranker instance to use for reranking
        """
        self.reranker_instance = reranker_instance

    def rerank_documents(
        self, query_text: str, documents: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Rerank documents using the configured reranker.

        Documents can be either:
        - Document-grouped (new format): Has `document_id`, `chunks` list, and `content` (concatenated)
        - Chunk-based (legacy format): Individual chunks with `chunk_id` and `content`

        Args:
            query_text: The query text to use for reranking
            documents: List of document dictionaries to rerank

        Returns:
            List[Dict[str, Any]]: Reranked documents with preserved structure
        """
        if not self.reranker_instance or not documents:
            return documents

        try:
            # Create Document objects for the rerankers library
            reranker_docs = []
            for i, doc in enumerate(documents):
                # Use document_id for matching
                doc_id = doc.get("document_id") or f"doc_{i}"
                # Use concatenated content for reranking
                content = doc.get("content", "")
                score = doc.get("score", 0.0)
                document_info = doc.get("document", {})

                reranker_docs.append(
                    RerankerDocument(
                        text=content,
                        doc_id=doc_id,
                        metadata={
                            "document_id": document_info.get("id", ""),
                            "document_title": document_info.get("title", ""),
                            "document_type": document_info.get("document_type", ""),
                            "rrf_score": score,
                            # Track original index for fallback matching
                            "original_index": i,
                        },
                    )
                )

            # Rerank using the configured reranker
            reranking_results = self.reranker_instance.rank(
                query=query_text, docs=reranker_docs
            )

            # Process the results from the reranker
            # Convert to serializable dictionaries while preserving full structure
            serialized_results = []
            for result in reranking_results.results:
                result_doc_id = result.document.doc_id
                original_index = result.document.metadata.get("original_index")

                # Find the original document by document_id
                original_doc = None
                for doc in documents:
                    if doc.get("document_id") == result_doc_id:
                        original_doc = doc
                        break

                # Fallback to original index if ID matching fails
                if (
                    original_doc is None
                    and original_index is not None
                    and 0 <= original_index < len(documents)
                ):
                    original_doc = documents[original_index]

                if original_doc:
                    # Create a deep copy to preserve the full structure including chunks
                    reranked_doc = original_doc.copy()
                    # Preserve chunks list if present (important for citation formatting)
                    if "chunks" in original_doc:
                        reranked_doc["chunks"] = original_doc["chunks"]
                    reranked_doc["score"] = float(result.score)
                    reranked_doc["rank"] = result.rank
                    serialized_results.append(reranked_doc)

            return serialized_results

        except Exception as e:
            # Log the error
            logging.error(f"Error during reranking: {e!s}")
            # Fall back to original documents without reranking
            return documents

    @staticmethod
    def get_reranker_instance() -> Optional["RerankerService"]:
        """
        Get a reranker service instance from the global configuration.

        Returns:
            Optional[RerankerService]: A reranker service instance if configured, None otherwise
        """
        from app.config import config

        if hasattr(config, "reranker_instance") and config.reranker_instance:
            return RerankerService(config.reranker_instance)
        return None
