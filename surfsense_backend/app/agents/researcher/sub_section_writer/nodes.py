from .configuration import Configuration
from langchain_core.runnables import RunnableConfig
from .state import State
from typing import Any, Dict
from app.config import config as app_config
from .prompts import get_citation_system_prompt
from langchain_core.messages import HumanMessage, SystemMessage
from .configuration import SubSectionType

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
    reranker_service = getattr(app_config, "reranker_service", None)
    
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
    documents.
    
    Returns:
        Dict containing the final answer in the "final_answer" key.
    """
    
    # Get configuration and relevant documents from configuration
    configuration = Configuration.from_runnable_config(config)
    documents = configuration.relevant_documents
    
    # Initialize LLM
    llm = app_config.fast_llm_instance
    
    # If no documents were provided, return a message indicating this
    if not documents or len(documents) == 0:
        return {
            "final_answer": "No relevant documents were provided to answer this question. Please provide documents or try a different approach."
        }
    
    # Prepare documents for citation formatting
    formatted_documents = []
    for i, doc in enumerate(documents):
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
    
    # Create the query that uses the section title and questions
    section_title = configuration.sub_section_title
    sub_section_questions = configuration.sub_section_questions
    user_query = configuration.user_query  # Get the original user query
    documents_text = "\n".join(formatted_documents)
    sub_section_type = configuration.sub_section_type

    # Format the questions as bullet points for clarity
    questions_text = "\n".join([f"- {question}" for question in sub_section_questions])
    
    # Provide more context based on the subsection type
    section_position_context = ""
    if sub_section_type == SubSectionType.START:
        section_position_context = "This is the INTRODUCTION section. "
    elif sub_section_type == SubSectionType.MIDDLE:
        section_position_context = "This is a MIDDLE section. Ensure this content flows naturally from previous sections and into subsequent ones. This could be any middle section in the document, so maintain coherence with the overall structure while addressing the specific topic of this section. Do not provide any conclusions in this section, as conclusions should only appear in the final section."
    elif sub_section_type == SubSectionType.END:
        section_position_context = "This is the CONCLUSION section. Focus on summarizing key points, providing closure."
    
    # Construct a clear, structured query for the LLM
    human_message_content = f"""
    Source material:
    <documents>
        {documents_text}
    </documents>
    
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
    """
    
    # Create messages for the LLM
    messages_with_chat_history = state.chat_history + [
        SystemMessage(content=get_citation_system_prompt()),
        HumanMessage(content=human_message_content)
    ]
    
    # Call the LLM and get the response
    response = await llm.ainvoke(messages_with_chat_history)
    final_answer = response.content
    
    return {
        "final_answer": final_answer
    }

