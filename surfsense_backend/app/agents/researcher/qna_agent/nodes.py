from .configuration import Configuration
from langchain_core.runnables import RunnableConfig
from .state import State
from typing import Any, Dict
from app.config import config as app_config
from .prompts import get_qna_citation_system_prompt, get_qna_no_documents_system_prompt
from langchain_core.messages import HumanMessage, SystemMessage

async def rerank_documents(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """
    Rerank the documents based on relevance to the user's question.
    
    This node takes the relevant documents provided in the configuration,
    reranks them using the reranker service based on the user's query,
    and updates the state with the reranked documents.
    
    Returns:
        Dict containing the reranked documents.
    """
    # Get configuration and relevant documents
    configuration = Configuration.from_runnable_config(config)
    documents = configuration.relevant_documents
    user_query = configuration.user_query

    # If no documents were provided, return empty list
    if not documents or len(documents) == 0:
        return {
            "reranked_documents": []
        }
    
    # Get reranker service from app config
    reranker_service = getattr(app_config, "reranker_service", None)
    
    # Use documents as is if no reranker service is available
    reranked_docs = documents
    
    if reranker_service:
        try:
            # Convert documents to format expected by reranker if needed
            reranker_input_docs = [
                {
                    "chunk_id": doc.get("chunk_id", f"chunk_{i}"),
                    "content": doc.get("content", ""),
                    "score": doc.get("score", 0.0),
                    "document": {
                        "id": doc.get("document", {}).get("id", ""),
                        "title": doc.get("document", {}).get("title", ""),
                        "document_type": doc.get("document", {}).get("document_type", ""),
                        "metadata": doc.get("document", {}).get("metadata", {})
                    }
                } for i, doc in enumerate(documents)
            ]
            
            # Rerank documents using the user's query
            reranked_docs = reranker_service.rerank_documents(user_query, reranker_input_docs)
            
            # Sort by score in descending order
            reranked_docs.sort(key=lambda x: x.get("score", 0), reverse=True)
            
            print(f"Reranked {len(reranked_docs)} documents for Q&A query: {user_query}")
        except Exception as e:
            print(f"Error during reranking: {str(e)}")
            # Use original docs if reranking fails
    
    return {
        "reranked_documents": reranked_docs
    }

async def answer_question(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """
    Answer the user's question using the provided documents.
    
    This node takes the relevant documents provided in the configuration and uses
    an LLM to generate a comprehensive answer to the user's question with
    proper citations. The citations follow IEEE format using source IDs from the
    documents. If no documents are provided, it will use chat history to generate
    an answer.
    
    Returns:
        Dict containing the final answer in the "final_answer" key.
    """
    
    # Get configuration and relevant documents from configuration
    configuration = Configuration.from_runnable_config(config)
    documents = configuration.relevant_documents
    user_query = configuration.user_query
    
    # Initialize LLM
    llm = app_config.fast_llm_instance
    
    # Check if we have documents to determine which prompt to use
    has_documents = documents and len(documents) > 0
    
    # Prepare documents for citation formatting (if any)
    documents_text = ""
    if has_documents:
        formatted_documents = []
        for _i, doc in enumerate(documents):
            # Extract content and metadata
            content = doc.get("content", "")
            doc_info = doc.get("document", {})
            document_id = doc_info.get("id")  # Use document ID
            
            # Format document according to the citation system prompt's expected format
            formatted_doc = f"""
            <document>
                <metadata>
                    <source_id>{document_id}</source_id>
                    <source_type>{doc_info.get("document_type", "CRAWLED_URL")}</source_type>
                </metadata>
                <content>
                    {content}
                </content>
            </document>
            """
            formatted_documents.append(formatted_doc)
        
        # Create the formatted documents text
        documents_text = f"""
        Source material from your personal knowledge base:
        <documents>
            {"\n".join(formatted_documents)}
        </documents>
        """
    
    # Construct a clear, structured query for the LLM
    human_message_content = f"""
    {documents_text}
    
    User's question:
    <user_query>
        {user_query}
    </user_query>
    
    {"Please provide a detailed, comprehensive answer to the user's question using the information from their personal knowledge sources. Make sure to cite all information appropriately and engage in a conversational manner." if has_documents else "Please provide a helpful answer to the user's question based on our conversation history and your general knowledge. Engage in a conversational manner."}
    """
    
    # Choose the appropriate system prompt based on document availability
    system_prompt = get_qna_citation_system_prompt() if has_documents else get_qna_no_documents_system_prompt()
    
    # Create messages for the LLM, including chat history for context
    messages_with_chat_history = state.chat_history + [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_message_content)
    ]
    
    # Call the LLM and get the response
    response = await llm.ainvoke(messages_with_chat_history)
    final_answer = response.content
    
    return {
        "final_answer": final_answer
    }
