from .configuration import Configuration
from langchain_core.runnables import RunnableConfig
from .state import State
from typing import Any, Dict
from app.services.reranker_service import RerankerService
from .prompts import get_citation_system_prompt, get_no_documents_system_prompt
from langchain_core.messages import HumanMessage, SystemMessage
from .configuration import SubSectionType
from ..utils import (
    optimize_documents_for_token_limit, 
    calculate_token_count,
    format_documents_section
)

async def rerank_documents(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """
    Rerank the documents based on relevance to the sub-section title.
    
    This node takes the relevant documents provided in the configuration,
    reranks them using the reranker service based on the sub-section title,
    and updates the state with the reranked documents.
    
    Returns:
        Dict containing the reranked documents.
    """
    # Get configuration and relevant documents
    configuration = Configuration.from_runnable_config(config)
    documents = configuration.relevant_documents
    sub_section_questions = configuration.sub_section_questions

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
            # Use the sub-section questions for reranking context
            # rerank_query = "\n".join(sub_section_questions)
            # rerank_query = configuration.user_query
            
            rerank_query = configuration.user_query + "\n" + "\n".join(sub_section_questions)

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
            
            # Rerank documents using the section title
            reranked_docs = reranker_service.rerank_documents(rerank_query, reranker_input_docs)
            
            # Sort by score in descending order
            reranked_docs.sort(key=lambda x: x.get("score", 0), reverse=True)
            
            print(f"Reranked {len(reranked_docs)} documents for section: {configuration.sub_section_title}")
        except Exception as e:
            print(f"Error during reranking: {str(e)}")
            # Use original docs if reranking fails
    
    return {
        "reranked_documents": reranked_docs
    }

async def write_sub_section(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """
    Write the sub-section using the provided documents.
    
    This node takes the relevant documents provided in the configuration and uses
    an LLM to generate a comprehensive answer to the sub-section title with
    proper citations. The citations follow IEEE format using source IDs from the
    documents. If no documents are provided, it will use chat history to generate
    content.
    
    Returns:
        Dict containing the final answer in the "final_answer" key.
    """
    from app.services.llm_service import get_user_fast_llm
    
    # Get configuration and relevant documents from configuration
    configuration = Configuration.from_runnable_config(config)
    documents = state.reranked_documents
    user_id = configuration.user_id
    
    # Get user's fast LLM
    llm = await get_user_fast_llm(state.db_session, user_id)
    if not llm:
        error_message = f"No fast LLM configured for user {user_id}"
        print(error_message)
        raise RuntimeError(error_message)
    
    # Extract configuration data
    section_title = configuration.sub_section_title
    sub_section_questions = configuration.sub_section_questions
    user_query = configuration.user_query
    sub_section_type = configuration.sub_section_type

    # Format the questions as bullet points for clarity
    questions_text = "\n".join([f"- {question}" for question in sub_section_questions])
    
    # Provide context based on the subsection type
    section_position_context_map = {
        SubSectionType.START: "This is the INTRODUCTION section.",
        SubSectionType.MIDDLE: "This is a MIDDLE section. Ensure this content flows naturally from previous sections and into subsequent ones. This could be any middle section in the document, so maintain coherence with the overall structure while addressing the specific topic of this section. Do not provide any conclusions in this section, as conclusions should only appear in the final section.",
        SubSectionType.END: "This is the CONCLUSION section. Focus on summarizing key points, providing closure."
    }
    section_position_context = section_position_context_map.get(sub_section_type, "")
    
    # Determine if we have documents and optimize for token limits
    has_documents_initially = documents and len(documents) > 0
    
    if has_documents_initially:
        # Create base message template for token calculation (without documents)
        base_human_message_template = f"""
        
        Now user's query is: 
        <user_query>
            {user_query}
        </user_query>
        
        The sub-section title is:
        <sub_section_title>
            {section_title}
        </sub_section_title>

        <section_position>
            {section_position_context}
        </section_position>
        
        <guiding_questions>
            {questions_text}
        </guiding_questions>
        
        Please write content for this sub-section using the provided source material and cite all information appropriately.
        """
        
        # Use initial system prompt for token calculation
        initial_system_prompt = get_citation_system_prompt()
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
    system_prompt = get_citation_system_prompt() if has_documents else get_no_documents_system_prompt()
    
    # Generate documents section
    documents_text = format_documents_section(documents, "Source material") if has_documents else ""
    
    # Create final human message content
    instruction_text = (
        "Please write content for this sub-section using the provided source material and cite all information appropriately."
        if has_documents else
        "Please write content for this sub-section based on our conversation history and your general knowledge."
    )
    
    human_message_content = f"""
    {documents_text}
    
    Now user's query is: 
    <user_query>
        {user_query}
    </user_query>
    
    The sub-section title is:
    <sub_section_title>
        {section_title}
    </sub_section_title>

    <section_position>
        {section_position_context}
    </section_position>
    
    <guiding_questions>
        {questions_text}
    </guiding_questions>
    
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

