from app.services.reranker_service import RerankerService
from .configuration import Configuration
from langchain_core.runnables import RunnableConfig
from .state import State
from typing import Any, Dict
from .prompts import get_qna_citation_system_prompt, get_qna_no_documents_system_prompt
from langchain_core.messages import HumanMessage, SystemMessage
from ..utils import (
    optimize_documents_for_token_limit, 
    calculate_token_count,
    format_documents_section
) 

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
    reformulated_query = configuration.reformulated_query

    # If no documents were provided, return empty list
    if not documents or len(documents) == 0:
        return {
            "reranked_documents": []
        }
    
    # Get reranker service from app config
    reranker_service = RerankerService.get_reranker_instance()
    
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
            reranked_docs = reranker_service.rerank_documents(user_query + "\n" + reformulated_query, reranker_input_docs)  
            
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
    from app.services.llm_service import get_user_fast_llm
    
    # Get configuration and relevant documents from configuration
    configuration = Configuration.from_runnable_config(config)
    documents = state.reranked_documents
    user_query = configuration.user_query
    user_id = configuration.user_id
    
    # Get user's fast LLM
    llm = await get_user_fast_llm(state.db_session, user_id)
    if not llm:
        error_message = f"No fast LLM configured for user {user_id}"
        print(error_message)
        raise RuntimeError(error_message)
    
    # Determine if we have documents and optimize for token limits
    has_documents_initially = documents and len(documents) > 0
    
    if has_documents_initially:
        # Create base message template for token calculation (without documents)
        base_human_message_template = f"""
        
        User's question:
        <user_query>
            {user_query}
        </user_query>
        
        Please provide a detailed, comprehensive answer to the user's question using the information from their personal knowledge sources. Make sure to cite all information appropriately and engage in a conversational manner.
        """
        
        # Use initial system prompt for token calculation
        initial_system_prompt = get_qna_citation_system_prompt()
        base_messages = state.chat_history + [
            SystemMessage(content=initial_system_prompt),
            HumanMessage(content=base_human_message_template)
        ]
        
        # Optimize documents to fit within token limits
        optimized_documents, has_optimized_documents = optimize_documents_for_token_limit(
            documents, base_messages, llm.model
        )
        
        # Update state based on optimization result
        documents = optimized_documents
        has_documents = has_optimized_documents
    else:
        has_documents = False
    
    # Choose system prompt based on final document availability
    system_prompt = get_qna_citation_system_prompt() if has_documents else get_qna_no_documents_system_prompt()
    
    # Generate documents section
    documents_text = format_documents_section(
        documents, 
        "Source material from your personal knowledge base"
    ) if has_documents else ""
    
    # Create final human message content
    instruction_text = (
        "Please provide a detailed, comprehensive answer to the user's question using the information from their personal knowledge sources. Make sure to cite all information appropriately and engage in a conversational manner."
        if has_documents else
        "Please provide a helpful answer to the user's question based on our conversation history and your general knowledge. Engage in a conversational manner."
    )
    
    human_message_content = f"""
    {documents_text}
    
    User's question:
    <user_query>
        {user_query}
    </user_query>
    
    {instruction_text}
    """
    
    # Create final messages for the LLM
    messages_with_chat_history = state.chat_history + [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_message_content)
    ]
    
    # Log final token count
    total_tokens = calculate_token_count(messages_with_chat_history, llm.model)
    print(f"Final token count: {total_tokens}")
    
    
    # Call the LLM and get the response
    response = await llm.ainvoke(messages_with_chat_history)
    final_answer = response.content
    
    return {
        "final_answer": final_answer
    }
