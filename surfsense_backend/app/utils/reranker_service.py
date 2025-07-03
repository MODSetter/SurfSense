import logging
from typing import List, Dict, Any, Optional
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
    
    def rerank_documents(self, query_text: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rerank documents using the configured reranker
        
        Args:
            query_text: The query text to use for reranking
            documents: List of document dictionaries to rerank
            
        Returns:
            List[Dict[str, Any]]: Reranked documents
        """
        if not self.reranker_instance or not documents:
            return documents
        
        try:
            # Create Document objects for the rerankers library
            reranker_docs = []
            for i, doc in enumerate(documents):
                chunk_id = doc.get("chunk_id", f"chunk_{i}")
                content = doc.get("content", "")
                score = doc.get("score", 0.0)
                document_info = doc.get("document", {})
                
                reranker_docs.append(
                    RerankerDocument(
                        text=content,
                        doc_id=chunk_id,
                        metadata={
                            'document_id': document_info.get("id", ""),
                            'document_title': document_info.get("title", ""),
                            'document_type': document_info.get("document_type", ""),
                            'rrf_score': score
                        }
                    )
                )
            
            # Rerank using the configured reranker
            reranking_results = self.reranker_instance.rank(
                query=query_text,
                docs=reranker_docs
            )
            
            # Process the results from the reranker
            # Convert to serializable dictionaries
            serialized_results = []
            for result in reranking_results.results:
                # Find the original document by id
                original_doc = next((doc for doc in documents if doc.get("chunk_id") == result.document.doc_id), None)
                if original_doc:
                    # Create a new document with the reranked score
                    reranked_doc = original_doc.copy()
                    reranked_doc["score"] = float(result.score)
                    reranked_doc["rank"] = result.rank
                    serialized_results.append(reranked_doc)
            
            return serialized_results
        
        except Exception as e:
            # Log the error
            logging.error(f"Error during reranking: {str(e)}")
            # Fall back to original documents without reranking
            return documents
    
    @staticmethod
    def get_reranker_instance() -> Optional['RerankerService']:
        """
        Get a reranker service instance from the global configuration.
        
        Returns:
            Optional[RerankerService]: A reranker service instance if configured, None otherwise
        """
        from app.config import config
        
        if hasattr(config, 'reranker_instance') and config.reranker_instance:
            return RerankerService(config.reranker_instance)
        return None
        