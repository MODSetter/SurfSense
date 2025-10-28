from typing import Any, NamedTuple

from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain_core.messages import BaseMessage
from litellm import get_model_info, token_counter


class DocumentTokenInfo(NamedTuple):
    """Information about a document and its token cost."""

    index: int
    document: dict[str, Any]
    formatted_content: str
    token_count: int


def get_connector_emoji(connector_name: str) -> str:
    """Get an appropriate emoji for a connector type."""
    connector_emojis = {
        "YOUTUBE_VIDEO": "📹",
        "EXTENSION": "🧩",
        "CRAWLED_URL": "🌐",
        "FILE": "📄",
        "SLACK_CONNECTOR": "💬",
        "NOTION_CONNECTOR": "📘",
        "GITHUB_CONNECTOR": "🐙",
        "LINEAR_CONNECTOR": "📊",
        "JIRA_CONNECTOR": "🎫",
        "DISCORD_CONNECTOR": "🗨️",
        "TAVILY_API": "🔍",
        "LINKUP_API": "🔗",
        "BAIDU_SEARCH_API": "🇨🇳",
        "GOOGLE_CALENDAR_CONNECTOR": "📅",
        "AIRTABLE_CONNECTOR": "🗃️",
        "LUMA_CONNECTOR": "✨",
        "ELASTICSEARCH_CONNECTOR": "⚡",
    }
    return connector_emojis.get(connector_name, "🔎")


def get_connector_friendly_name(connector_name: str) -> str:
    """Convert technical connector IDs to user-friendly names."""
    connector_friendly_names = {
        "YOUTUBE_VIDEO": "YouTube",
        "EXTENSION": "Browser Extension",
        "CRAWLED_URL": "Web Pages",
        "FILE": "Files",
        "SLACK_CONNECTOR": "Slack",
        "NOTION_CONNECTOR": "Notion",
        "GITHUB_CONNECTOR": "GitHub",
        "LINEAR_CONNECTOR": "Linear",
        "JIRA_CONNECTOR": "Jira",
        "CONFLUENCE_CONNECTOR": "Confluence",
        "GOOGLE_CALENDAR_CONNECTOR": "Google Calendar",
        "DISCORD_CONNECTOR": "Discord",
        "TAVILY_API": "Tavily Search",
        "LINKUP_API": "Linkup Search",
        "BAIDU_SEARCH_API": "Baidu Search",
        "AIRTABLE_CONNECTOR": "Airtable",
        "LUMA_CONNECTOR": "Luma",
        "ELASTICSEARCH_CONNECTOR": "Elasticsearch",
    }
    return connector_friendly_names.get(connector_name, connector_name)


def convert_langchain_messages_to_dict(
    messages: list[BaseMessage],
) -> list[dict[str, str]]:
    """Convert LangChain messages to format expected by token_counter."""
    role_mapping = {"system": "system", "human": "user", "ai": "assistant"}

    converted_messages = []
    for msg in messages:
        role = role_mapping.get(getattr(msg, "type", None), "user")
        converted_messages.append({"role": role, "content": str(msg.content)})

    return converted_messages


def format_document_for_citation(document: dict[str, Any]) -> str:
    """Format a single document for citation in the standard XML format."""
    content = document.get("content", "")
    doc_info = document.get("document", {})
    document_id = document.get("chunk_id", "")
    document_type = doc_info.get("document_type", "CRAWLED_URL")

    return f"""<document>
    <metadata>
        <source_id>{document_id}</source_id>
        <source_type>{document_type}</source_type>
    </metadata>
    <content>
        {content}
    </content>
    </document>"""


def format_documents_section(
    documents: list[dict[str, Any]], section_title: str = "Source material"
) -> str:
    """Format multiple documents into a complete documents section."""
    if not documents:
        return ""

    formatted_docs = [format_document_for_citation(doc) for doc in documents]

    return f"""{section_title}:
    <documents>
    {chr(10).join(formatted_docs)}
    </documents>"""


def calculate_document_token_costs(
    documents: list[dict[str, Any]], model: str
) -> list[DocumentTokenInfo]:
    """Pre-calculate token costs for each document."""
    document_token_info = []

    for i, doc in enumerate(documents):
        formatted_doc = format_document_for_citation(doc)

        # Calculate token count for this document
        token_count = token_counter(
            messages=[{"role": "user", "content": formatted_doc}], model=model
        )

        document_token_info.append(
            DocumentTokenInfo(
                index=i,
                document=doc,
                formatted_content=formatted_doc,
                token_count=token_count,
            )
        )

    return document_token_info


def find_optimal_documents_with_binary_search(
    document_tokens: list[DocumentTokenInfo], available_tokens: int
) -> list[DocumentTokenInfo]:
    """Use binary search to find the maximum number of documents that fit within token limit."""
    if not document_tokens or available_tokens <= 0:
        return []

    left, right = 0, len(document_tokens)
    optimal_docs = []

    while left <= right:
        mid = (left + right) // 2
        current_docs = document_tokens[:mid]
        current_token_sum = sum(doc_info.token_count for doc_info in current_docs)

        if current_token_sum <= available_tokens:
            optimal_docs = current_docs
            left = mid + 1
        else:
            right = mid - 1

    return optimal_docs


def get_model_context_window(model_name: str) -> int:
    """Get the total context window size for a model (input + output tokens)."""
    try:
        model_info = get_model_info(model_name)
        context_window = model_info.get("max_input_tokens", 4096)  # Default fallback
        return context_window
    except Exception as e:
        print(
            f"Warning: Could not get model info for {model_name}, using default 4096 tokens. Error: {e}"
        )
        return 4096  # Conservative fallback


def optimize_documents_for_token_limit(
    documents: list[dict[str, Any]], base_messages: list[BaseMessage], model_name: str
) -> tuple[list[dict[str, Any]], bool]:
    """
    Optimize documents to fit within token limits using binary search.

    Args:
        documents: List of documents with content and metadata
        base_messages: Base messages without documents (chat history + system + human message template)
        model_name: Model name for token counting (required)
        output_token_buffer: Number of tokens to reserve for model output

    Returns:
        Tuple of (optimized_documents, has_documents_remaining)
    """
    if not documents:
        return [], False

    model = model_name
    context_window = get_model_context_window(model)

    # Calculate base token cost
    base_messages_dict = convert_langchain_messages_to_dict(base_messages)
    base_tokens = token_counter(messages=base_messages_dict, model=model)
    available_tokens_for_docs = context_window - base_tokens

    print(
        f"Token optimization: Context window={context_window}, Base={base_tokens}, Available for docs={available_tokens_for_docs}"
    )

    if available_tokens_for_docs <= 0:
        print("No tokens available for documents after base content and output buffer")
        return [], False

    # Calculate token costs for all documents
    document_token_info = calculate_document_token_costs(documents, model)

    # Find optimal number of documents using binary search
    optimal_doc_info = find_optimal_documents_with_binary_search(
        document_token_info, available_tokens_for_docs
    )

    # Extract the original document objects
    optimized_documents = [doc_info.document for doc_info in optimal_doc_info]
    has_documents_remaining = len(optimized_documents) > 0

    print(
        f"Token optimization result: Using {len(optimized_documents)}/{len(documents)} documents"
    )

    return optimized_documents, has_documents_remaining


def calculate_token_count(messages: list[BaseMessage], model_name: str) -> int:
    """Calculate token count for a list of LangChain messages."""
    model = model_name
    messages_dict = convert_langchain_messages_to_dict(messages)
    return token_counter(messages=messages_dict, model=model)


def langchain_chat_history_to_str(chat_history: list[BaseMessage]) -> str:
    """
    Convert a list of chat history messages to a string.
    """
    chat_history_str = ""

    for chat_message in chat_history:
        if isinstance(chat_message, HumanMessage):
            chat_history_str += f"<user>{chat_message.content}</user>\n"
        elif isinstance(chat_message, AIMessage):
            chat_history_str += f"<assistant>{chat_message.content}</assistant>\n"
        elif isinstance(chat_message, SystemMessage):
            chat_history_str += f"<system>{chat_message.content}</system>\n"

    return chat_history_str
