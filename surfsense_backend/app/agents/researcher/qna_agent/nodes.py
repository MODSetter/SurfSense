import datetime
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import StreamWriter
from sqlalchemy import select

from app.db import SearchSpace
from app.services.reranker_service import RerankerService

from ..utils import (
    calculate_token_count,
    format_documents_section,
    langchain_chat_history_to_str,
    optimize_documents_for_token_limit,
)
from .configuration import Configuration
from .default_prompts import (
    DEFAULT_QNA_BASE_PROMPT,
    DEFAULT_QNA_CITATION_INSTRUCTIONS,
    DEFAULT_QNA_NO_DOCUMENTS_PROMPT,
)
from .state import State


def _build_language_instruction(language: str | None = None):
    """Build language instruction for prompts."""
    if language:
        return f"\n\nIMPORTANT: Please respond in {language} language. All your responses, explanations, and analysis should be written in {language}."
    return ""


def _build_chat_history_section(chat_history: str | None = None):
    """Build chat history section for prompts."""
    if chat_history:
        return f"""
<chat_history>
{chat_history if chat_history else "NO CHAT HISTORY PROVIDED"}
</chat_history>
"""
    return """
<chat_history>
NO CHAT HISTORY PROVIDED
</chat_history>
"""


def _format_system_prompt(
    prompt_template: str,
    chat_history: str | None = None,
    language: str | None = None,
):
    """Format a system prompt template with dynamic values."""
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    language_instruction = _build_language_instruction(language)
    chat_history_section = _build_chat_history_section(chat_history)

    return prompt_template.format(
        date=date,
        language_instruction=language_instruction,
        chat_history_section=chat_history_section,
    )


async def rerank_documents(state: State, config: RunnableConfig) -> dict[str, Any]:
    """
    Rerank the documents based on relevance to the user's question.

    This node takes the relevant documents provided in the configuration,
    reranks them using the reranker service based on the user's query,
    and updates the state with the reranked documents.

    If reranking is disabled, returns the original documents without processing.

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
        return {"reranked_documents": []}

    # Get reranker service from app config
    reranker_service = RerankerService.get_reranker_instance()

    # If reranking is not enabled, sort by existing score and return
    if not reranker_service:
        print("Reranking is disabled. Sorting documents by existing score.")
        sorted_documents = sorted(
            documents, key=lambda x: x.get("score", 0), reverse=True
        )
        return {"reranked_documents": sorted_documents}

    # Perform reranking
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
                    "metadata": doc.get("document", {}).get("metadata", {}),
                },
            }
            for i, doc in enumerate(documents)
        ]

        # Rerank documents using the user's query
        reranked_docs = reranker_service.rerank_documents(
            user_query + "\n" + reformulated_query, reranker_input_docs
        )

        # Sort by score in descending order
        reranked_docs.sort(key=lambda x: x.get("score", 0), reverse=True)

        print(f"Reranked {len(reranked_docs)} documents for Q&A query: {user_query}")

        return {"reranked_documents": reranked_docs}

    except Exception as e:
        print(f"Error during reranking: {e!s}")
        # Fall back to original documents if reranking fails
        return {"reranked_documents": documents}


async def answer_question(
    state: State, config: RunnableConfig, writer: StreamWriter
) -> dict[str, Any]:
    """
    Answer the user's question using the provided documents with real-time streaming.

    This node takes the relevant documents provided in the configuration and uses
    an LLM to generate a comprehensive answer to the user's question with
    proper citations. The citations follow [citation:source_id] format using source IDs from the
    documents. If no documents are provided, it will use chat history to generate
    an answer.

    The response is streamed token-by-token for real-time updates to the frontend.

    Returns:
        Dict containing the final answer in the "final_answer" key.
    """
    from app.services.llm_service import get_fast_llm

    # Get configuration and relevant documents from configuration
    configuration = Configuration.from_runnable_config(config)
    documents = state.reranked_documents
    user_query = configuration.user_query
    search_space_id = configuration.search_space_id
    language = configuration.language

    # Get streaming service from state
    streaming_service = state.streaming_service

    # Fetch search space to get QnA configuration
    result = await state.db_session.execute(
        select(SearchSpace).where(SearchSpace.id == search_space_id)
    )
    search_space = result.scalar_one_or_none()

    if not search_space:
        error_message = f"Search space {search_space_id} not found"
        print(error_message)
        raise RuntimeError(error_message)

    # Get QnA configuration from search space
    citations_enabled = search_space.citations_enabled
    custom_instructions_text = search_space.qna_custom_instructions or ""

    # Use constants for base prompt and citation instructions
    qna_base_prompt = DEFAULT_QNA_BASE_PROMPT
    qna_citation_instructions = (
        DEFAULT_QNA_CITATION_INSTRUCTIONS if citations_enabled else ""
    )
    qna_custom_instructions = (
        f"\n<special_important_custom_instructions>\n{custom_instructions_text}\n</special_important_custom_instructions>"
        if custom_instructions_text
        else ""
    )

    # Get search space's fast LLM
    llm = await get_fast_llm(state.db_session, search_space_id)
    if not llm:
        error_message = f"No fast LLM configured for search space {search_space_id}"
        print(error_message)
        raise RuntimeError(error_message)

    # Determine if we have documents and optimize for token limits
    has_documents_initially = documents and len(documents) > 0
    chat_history_str = langchain_chat_history_to_str(state.chat_history)

    if has_documents_initially:
        # Compose the full citation prompt: base + citation instructions + custom instructions
        full_citation_prompt_template = (
            qna_base_prompt + qna_citation_instructions + qna_custom_instructions
        )

        # Create base message template for token calculation (without documents)
        base_human_message_template = f"""
        
        User's question:
        <user_query>
            {user_query}
        </user_query>
        
        Please provide a detailed, comprehensive answer to the user's question using the information from their personal knowledge sources. Make sure to cite all information appropriately and engage in a conversational manner.
        """

        # Use initial system prompt for token calculation
        initial_system_prompt = _format_system_prompt(
            full_citation_prompt_template, chat_history_str, language
        )
        base_messages = [
            SystemMessage(content=initial_system_prompt),
            HumanMessage(content=base_human_message_template),
        ]

        # Optimize documents to fit within token limits
        optimized_documents, has_optimized_documents = (
            optimize_documents_for_token_limit(documents, base_messages, llm.model)
        )

        # Update state based on optimization result
        documents = optimized_documents
        has_documents = has_optimized_documents
    else:
        has_documents = False

    # Choose system prompt based on final document availability
    # With documents: use base + citation instructions + custom instructions
    # Without documents: use the default no-documents prompt from constants
    if has_documents:
        full_citation_prompt_template = (
            qna_base_prompt + qna_citation_instructions + qna_custom_instructions
        )
        system_prompt = _format_system_prompt(
            full_citation_prompt_template, chat_history_str, language
        )
    else:
        system_prompt = _format_system_prompt(
            DEFAULT_QNA_NO_DOCUMENTS_PROMPT + qna_custom_instructions,
            chat_history_str,
            language,
        )

    # Generate documents section
    documents_text = (
        format_documents_section(
            documents, "Source material from your personal knowledge base"
        )
        if has_documents
        else ""
    )

    # Create final human message content
    instruction_text = (
        "Please provide a detailed, comprehensive answer to the user's question using the information from their personal knowledge sources. Make sure to cite all information appropriately and engage in a conversational manner."
        if has_documents
        else "Please provide a helpful answer to the user's question based on our conversation history and your general knowledge. Engage in a conversational manner."
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
    messages_with_chat_history = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_message_content),
    ]

    # Log final token count
    total_tokens = calculate_token_count(messages_with_chat_history, llm.model)
    print(f"Final token count: {total_tokens}")

    # Stream the LLM response token by token
    final_answer = ""

    async for chunk in llm.astream(messages_with_chat_history):
        # Extract the content from the chunk
        if hasattr(chunk, "content") and chunk.content:
            token = chunk.content
            final_answer += token

            # Stream the token to the frontend via custom stream
            if streaming_service:
                writer({"yield_value": streaming_service.format_text_chunk(token)})

    return {"final_answer": final_answer}
