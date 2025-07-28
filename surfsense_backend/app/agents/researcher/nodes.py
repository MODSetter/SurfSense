import asyncio
import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import StreamWriter
from sqlalchemy.ext.asyncio import AsyncSession

# Additional imports for document fetching
from sqlalchemy.future import select

from app.db import Document, SearchSpace
from app.services.connector_service import ConnectorService
from app.services.query_service import QueryService

from .configuration import Configuration, SearchMode
from .prompts import (
    get_answer_outline_system_prompt,
    get_further_questions_system_prompt,
)
from .qna_agent.graph import graph as qna_agent_graph
from .state import State
from .sub_section_writer.configuration import SubSectionType
from .sub_section_writer.graph import graph as sub_section_writer_graph
from .utils import AnswerOutline, get_connector_emoji, get_connector_friendly_name


async def fetch_documents_by_ids(
    document_ids: list[int], user_id: str, db_session: AsyncSession
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Fetch documents by their IDs with ownership check using DOCUMENTS mode approach.

    This function ensures that only documents belonging to the user are fetched,
    providing security by checking ownership through SearchSpace association.
    Similar to SearchMode.DOCUMENTS, it fetches full documents and concatenates their chunks.
    Also creates source objects for UI display, grouped by document type.

    Args:
        document_ids: List of document IDs to fetch
        user_id: The user ID to check ownership
        db_session: The database session

    Returns:
        Tuple of (source_objects, document_chunks) - similar to ConnectorService pattern
    """
    if not document_ids:
        return [], []

    try:
        # Query documents with ownership check
        result = await db_session.execute(
            select(Document)
            .join(SearchSpace)
            .filter(Document.id.in_(document_ids), SearchSpace.user_id == user_id)
        )
        documents = result.scalars().all()

        # Group documents by type for source object creation
        documents_by_type = {}
        formatted_documents = []

        for doc in documents:
            # Fetch associated chunks for this document (similar to DocumentHybridSearchRetriever)
            from app.db import Chunk

            chunks_query = (
                select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.id)
            )
            chunks_result = await db_session.execute(chunks_query)
            chunks = chunks_result.scalars().all()

            # Concatenate chunks content (similar to SearchMode.DOCUMENTS approach)
            concatenated_chunks_content = (
                " ".join([chunk.content for chunk in chunks]) if chunks else doc.content
            )

            # Format to match connector service return format
            formatted_doc = {
                "chunk_id": f"user_doc_{doc.id}",
                "content": concatenated_chunks_content,  # Use concatenated content like DOCUMENTS mode
                "score": 0.5,  # High score since user explicitly selected these
                "document": {
                    "id": doc.id,
                    "title": doc.title,
                    "document_type": (
                        doc.document_type.value if doc.document_type else "UNKNOWN"
                    ),
                    "metadata": doc.document_metadata or {},
                },
                "source": doc.document_type.value if doc.document_type else "UNKNOWN",
            }
            formatted_documents.append(formatted_doc)

            # Group by document type for source objects
            doc_type = doc.document_type.value if doc.document_type else "UNKNOWN"
            if doc_type not in documents_by_type:
                documents_by_type[doc_type] = []
            documents_by_type[doc_type].append(doc)

        # Create source objects for each document type (similar to ConnectorService)
        source_objects = []
        connector_id_counter = (
            100  # Start from 100 to avoid conflicts with regular connectors
        )

        for doc_type, docs in documents_by_type.items():
            sources_list = []

            for doc in docs:
                metadata = doc.document_metadata or {}

                # Create type-specific source formatting (similar to ConnectorService)
                if doc_type == "LINEAR_CONNECTOR":
                    # Extract Linear-specific metadata
                    issue_identifier = metadata.get("issue_identifier", "")
                    issue_title = metadata.get("issue_title", doc.title)
                    issue_state = metadata.get("state", "")
                    comment_count = metadata.get("comment_count", 0)

                    # Create a more descriptive title for Linear issues
                    title = (
                        f"Linear: {issue_identifier} - {issue_title}"
                        if issue_identifier
                        else f"Linear: {issue_title}"
                    )
                    if issue_state:
                        title += f" ({issue_state})"

                    # Create description
                    description = (
                        doc.content[:100] + "..."
                        if len(doc.content) > 100
                        else doc.content
                    )
                    if comment_count:
                        description += f" | Comments: {comment_count}"

                    # Create URL
                    url = (
                        f"https://linear.app/issue/{issue_identifier}"
                        if issue_identifier
                        else ""
                    )

                elif doc_type == "SLACK_CONNECTOR":
                    # Extract Slack-specific metadata
                    channel_name = metadata.get("channel_name", "Unknown Channel")
                    channel_id = metadata.get("channel_id", "")
                    message_date = metadata.get("start_date", "")

                    title = f"Slack: {channel_name}"
                    if message_date:
                        title += f" ({message_date})"

                    description = (
                        doc.content[:100] + "..."
                        if len(doc.content) > 100
                        else doc.content
                    )
                    url = (
                        f"https://slack.com/app_redirect?channel={channel_id}"
                        if channel_id
                        else ""
                    )

                elif doc_type == "NOTION_CONNECTOR":
                    # Extract Notion-specific metadata
                    page_title = metadata.get("page_title", doc.title)
                    page_id = metadata.get("page_id", "")

                    title = f"Notion: {page_title}"
                    description = (
                        doc.content[:100] + "..."
                        if len(doc.content) > 100
                        else doc.content
                    )
                    url = (
                        f"https://notion.so/{page_id.replace('-', '')}"
                        if page_id
                        else ""
                    )

                elif doc_type == "GITHUB_CONNECTOR":
                    title = f"GitHub: {doc.title}"
                    description = metadata.get(
                        "description",
                        (
                            doc.content[:100] + "..."
                            if len(doc.content) > 100
                            else doc.content
                        ),
                    )
                    url = metadata.get("url", "")

                elif doc_type == "YOUTUBE_VIDEO":
                    # Extract YouTube-specific metadata
                    video_title = metadata.get("video_title", doc.title)
                    video_id = metadata.get("video_id", "")
                    channel_name = metadata.get("channel_name", "")

                    title = video_title
                    if channel_name:
                        title += f" - {channel_name}"

                    description = metadata.get(
                        "description",
                        (
                            doc.content[:100] + "..."
                            if len(doc.content) > 100
                            else doc.content
                        ),
                    )
                    url = (
                        f"https://www.youtube.com/watch?v={video_id}"
                        if video_id
                        else ""
                    )

                elif doc_type == "DISCORD_CONNECTOR":
                    # Extract Discord-specific metadata
                    channel_name = metadata.get("channel_name", "Unknown Channel")
                    channel_id = metadata.get("channel_id", "")
                    guild_id = metadata.get("guild_id", "")
                    message_date = metadata.get("start_date", "")

                    title = f"Discord: {channel_name}"
                    if message_date:
                        title += f" ({message_date})"

                    description = (
                        doc.content[:100] + "..."
                        if len(doc.content) > 100
                        else doc.content
                    )

                    if guild_id and channel_id:
                        url = f"https://discord.com/channels/{guild_id}/{channel_id}"
                    elif channel_id:
                        url = f"https://discord.com/channels/@me/{channel_id}"
                    else:
                        url = ""

                elif doc_type == "JIRA_CONNECTOR":
                    # Extract Jira-specific metadata
                    issue_key = metadata.get("issue_key", "Unknown Issue")
                    issue_title = metadata.get("issue_title", "Untitled Issue")
                    status = metadata.get("status", "")
                    priority = metadata.get("priority", "")
                    issue_type = metadata.get("issue_type", "")

                    title = f"Jira: {issue_key} - {issue_title}"
                    if status:
                        title += f" ({status})"

                    description = (
                        doc.content[:100] + "..."
                        if len(doc.content) > 100
                        else doc.content
                    )
                    if priority:
                        description += f" | Priority: {priority}"
                    if issue_type:
                        description += f" | Type: {issue_type}"

                    # Construct Jira URL if we have the base URL
                    base_url = metadata.get("base_url", "")
                    if base_url and issue_key:
                        url = f"{base_url}/browse/{issue_key}"
                    else:
                        url = ""

                elif doc_type == "EXTENSION":
                    # Extract Extension-specific metadata
                    webpage_title = metadata.get("VisitedWebPageTitle", doc.title)
                    webpage_url = metadata.get("VisitedWebPageURL", "")
                    visit_date = metadata.get(
                        "VisitedWebPageDateWithTimeInISOString", ""
                    )

                    title = webpage_title
                    if visit_date:
                        formatted_date = (
                            visit_date.split("T")[0]
                            if "T" in visit_date
                            else visit_date
                        )
                        title += f" (visited: {formatted_date})"

                    description = (
                        doc.content[:100] + "..."
                        if len(doc.content) > 100
                        else doc.content
                    )
                    url = webpage_url

                elif doc_type == "CRAWLED_URL":
                    title = doc.title
                    description = metadata.get(
                        "og:description",
                        metadata.get(
                            "ogDescription",
                            (
                                doc.content[:100] + "..."
                                if len(doc.content) > 100
                                else doc.content
                            ),
                        ),
                    )
                    url = metadata.get("url", "")

                else:  # FILE and other types
                    title = doc.title
                    description = (
                        doc.content[:100] + "..."
                        if len(doc.content) > 100
                        else doc.content
                    )
                    url = metadata.get("url", "")

                # Create source entry
                source = {
                    "id": doc.id,
                    "title": title,
                    "description": description,
                    "url": url,
                }
                sources_list.append(source)

            # Create source object for this document type
            friendly_type_names = {
                "LINEAR_CONNECTOR": "Linear Issues (Selected)",
                "SLACK_CONNECTOR": "Slack (Selected)",
                "NOTION_CONNECTOR": "Notion (Selected)",
                "GITHUB_CONNECTOR": "GitHub (Selected)",
                "YOUTUBE_VIDEO": "YouTube Videos (Selected)",
                "DISCORD_CONNECTOR": "Discord (Selected)",
                "JIRA_CONNECTOR": "Jira Issues (Selected)",
                "EXTENSION": "Browser Extension (Selected)",
                "CRAWLED_URL": "Web Pages (Selected)",
                "FILE": "Files (Selected)",
            }

            source_object = {
                "id": connector_id_counter,
                "name": friendly_type_names.get(doc_type, f"{doc_type} (Selected)"),
                "type": f"USER_SELECTED_{doc_type}",
                "sources": sources_list,
            }
            source_objects.append(source_object)
            connector_id_counter += 1

        print(
            f"Fetched {len(formatted_documents)} user-selected documents (with concatenated chunks) from {len(document_ids)} requested IDs"
        )
        print(f"Created {len(source_objects)} source objects for UI display")

        return source_objects, formatted_documents

    except Exception as e:
        print(f"Error fetching documents by IDs: {e!s}")
        return [], []


async def write_answer_outline(
    state: State, config: RunnableConfig, writer: StreamWriter
) -> dict[str, Any]:
    """
    Create a structured answer outline based on the user query.

    This node takes the user query and number of sections from the configuration and uses
    an LLM to generate a comprehensive outline with logical sections and research questions
    for each section.

    Returns:
        Dict containing the answer outline in the "answer_outline" key for state update.
    """
    from app.services.llm_service import get_user_strategic_llm

    streaming_service = state.streaming_service

    writer(
        {
            "yield_value": streaming_service.format_terminal_info_delta(
                "🔍 Generating answer outline..."
            )
        }
    )
    # Get configuration from runnable config
    configuration = Configuration.from_runnable_config(config)
    reformulated_query = state.reformulated_query
    user_query = configuration.user_query
    num_sections = configuration.num_sections
    user_id = configuration.user_id

    writer(
        {
            "yield_value": streaming_service.format_terminal_info_delta(
                f'🤔 Planning research approach for: "{user_query[:100]}..."'
            )
        }
    )

    # Get user's strategic LLM
    llm = await get_user_strategic_llm(state.db_session, user_id)
    if not llm:
        error_message = f"No strategic LLM configured for user {user_id}"
        writer({"yield_value": streaming_service.format_error(error_message)})
        raise RuntimeError(error_message)

    # Create the human message content
    human_message_content = f"""
    Now Please create an answer outline for the following query:

    User Query: {reformulated_query}
    Number of Sections: {num_sections}

    Remember to format your response as valid JSON exactly matching this structure:
    {{
      "answer_outline": [
        {{
          "section_id": 0,
          "section_title": "Section Title",
          "questions": [
            "Question 1 to research for this section",
            "Question 2 to research for this section"
          ]
        }}
      ]
    }}

    Your output MUST be valid JSON in exactly this format. Do not include any other text or explanation.
    """

    writer(
        {
            "yield_value": streaming_service.format_terminal_info_delta(
                "📝 Designing structured outline with AI..."
            )
        }
    )

    # Create messages for the LLM
    messages = [
        SystemMessage(content=get_answer_outline_system_prompt()),
        HumanMessage(content=human_message_content),
    ]

    # Call the LLM directly without using structured output
    writer(
        {
            "yield_value": streaming_service.format_terminal_info_delta(
                "⚙️ Processing answer structure..."
            )
        }
    )

    response = await llm.ainvoke(messages)

    # Parse the JSON response manually
    try:
        # Extract JSON content from the response
        content = response.content

        # Find the JSON in the content (handle case where LLM might add additional text)
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = content[json_start:json_end]

            # Parse the JSON string
            parsed_data = json.loads(json_str)

            # Convert to Pydantic model
            answer_outline = AnswerOutline(**parsed_data)

            total_questions = sum(
                len(section.questions) for section in answer_outline.answer_outline
            )

            writer(
                {
                    "yield_value": streaming_service.format_terminal_info_delta(
                        f"✅ Successfully generated outline with {len(answer_outline.answer_outline)} sections and {total_questions} research questions!"
                    )
                }
            )

            print(
                f"Successfully generated answer outline with {len(answer_outline.answer_outline)} sections"
            )

            # Return state update
            return {"answer_outline": answer_outline}
        else:
            # If JSON structure not found, raise a clear error
            error_message = (
                f"Could not find valid JSON in LLM response. Raw response: {content}"
            )
            writer({"yield_value": streaming_service.format_error(error_message)})
            raise ValueError(error_message)

    except (json.JSONDecodeError, ValueError) as e:
        # Log the error and re-raise it
        error_message = f"Error parsing LLM response: {e!s}"
        writer({"yield_value": streaming_service.format_error(error_message)})

        print(f"Error parsing LLM response: {e!s}")
        print(f"Raw response: {response.content}")
        raise


async def fetch_relevant_documents(
    research_questions: list[str],
    user_id: str,
    search_space_id: int,
    db_session: AsyncSession,
    connectors_to_search: list[str],
    writer: StreamWriter = None,
    state: State = None,
    top_k: int = 10,
    connector_service: ConnectorService = None,
    search_mode: SearchMode = SearchMode.CHUNKS,
    user_selected_sources: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch relevant documents for research questions using the provided connectors.

    This function searches across multiple data sources for information related to the
    research questions. It provides user-friendly feedback during the search process by
    displaying connector names (like "Web Search" instead of "TAVILY_API") and adding
    relevant emojis to indicate the type of source being searched.

    Args:
        research_questions: List of research questions to find documents for
        user_id: The user ID
        search_space_id: The search space ID
        db_session: The database session
        connectors_to_search: List of connectors to search
        writer: StreamWriter for sending progress updates
        state: The current state containing the streaming service
        top_k: Number of top results to retrieve per connector per question
        connector_service: An initialized connector service to use for searching

    Returns:
        List of relevant documents
    """
    # Initialize services
    # connector_service = ConnectorService(db_session)

    # Only use streaming if both writer and state are provided
    streaming_service = state.streaming_service if state is not None else None

    # Handle case when no connectors are selected
    if not connectors_to_search or len(connectors_to_search) == 0:
        if streaming_service and writer:
            writer(
                {
                    "yield_value": streaming_service.format_terminal_info_delta(
                        "📹 No data sources selected. Research will be generated using general knowledge and any user-selected documents."
                    )
                }
            )
        print("No connectors selected for research. Returning empty document list.")
        return []  # Return empty list gracefully

    # Stream initial status update
    if streaming_service and writer:
        connector_names = [
            get_connector_friendly_name(connector) for connector in connectors_to_search
        ]
        connector_names_str = ", ".join(connector_names)
        writer(
            {
                "yield_value": streaming_service.format_terminal_info_delta(
                    f"🔎 Starting research on {len(research_questions)} questions using {connector_names_str} data sources"
                )
            }
        )

    all_raw_documents = []  # Store all raw documents
    all_sources = []  # Store all sources

    for i, user_query in enumerate(research_questions):
        # Stream question being researched
        if streaming_service and writer:
            writer(
                {
                    "yield_value": streaming_service.format_terminal_info_delta(
                        f'🧠 Researching question {i + 1}/{len(research_questions)}: "{user_query[:100]}..."'
                    )
                }
            )

        # Use original research question as the query
        reformulated_query = user_query

        # Process each selected connector
        for connector in connectors_to_search:
            # Stream connector being searched
            if streaming_service and writer:
                connector_emoji = get_connector_emoji(connector)
                friendly_name = get_connector_friendly_name(connector)
                writer(
                    {
                        "yield_value": streaming_service.format_terminal_info_delta(
                            f"{connector_emoji} Searching {friendly_name} for relevant information..."
                        )
                    }
                )

            try:
                if connector == "YOUTUBE_VIDEO":
                    (
                        source_object,
                        youtube_chunks,
                    ) = await connector_service.search_youtube(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k,
                        search_mode=search_mode,
                    )

                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(youtube_chunks)

                    # Stream found document count
                    if streaming_service and writer:
                        writer(
                            {
                                "yield_value": streaming_service.format_terminal_info_delta(
                                    f"📹 Found {len(youtube_chunks)} YouTube chunks related to your query"
                                )
                            }
                        )

                elif connector == "EXTENSION":
                    (
                        source_object,
                        extension_chunks,
                    ) = await connector_service.search_extension(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k,
                        search_mode=search_mode,
                    )

                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(extension_chunks)

                    # Stream found document count
                    if streaming_service and writer:
                        writer(
                            {
                                "yield_value": streaming_service.format_terminal_info_delta(
                                    f"🧩 Found {len(extension_chunks)} Browser Extension chunks related to your query"
                                )
                            }
                        )

                elif connector == "CRAWLED_URL":
                    (
                        source_object,
                        crawled_urls_chunks,
                    ) = await connector_service.search_crawled_urls(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k,
                        search_mode=search_mode,
                    )

                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(crawled_urls_chunks)

                    # Stream found document count
                    if streaming_service and writer:
                        writer(
                            {
                                "yield_value": streaming_service.format_terminal_info_delta(
                                    f"🌐 Found {len(crawled_urls_chunks)} Web Pages chunks related to your query"
                                )
                            }
                        )

                elif connector == "FILE":
                    source_object, files_chunks = await connector_service.search_files(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k,
                        search_mode=search_mode,
                    )

                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(files_chunks)

                    # Stream found document count
                    if streaming_service and writer:
                        writer(
                            {
                                "yield_value": streaming_service.format_terminal_info_delta(
                                    f"📄 Found {len(files_chunks)} Files chunks related to your query"
                                )
                            }
                        )

                elif connector == "SLACK_CONNECTOR":
                    source_object, slack_chunks = await connector_service.search_slack(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k,
                        search_mode=search_mode,
                    )

                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(slack_chunks)

                    # Stream found document count
                    if streaming_service and writer:
                        writer(
                            {
                                "yield_value": streaming_service.format_terminal_info_delta(
                                    f"💬 Found {len(slack_chunks)} Slack messages related to your query"
                                )
                            }
                        )

                elif connector == "NOTION_CONNECTOR":
                    (
                        source_object,
                        notion_chunks,
                    ) = await connector_service.search_notion(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k,
                        search_mode=search_mode,
                    )

                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(notion_chunks)

                    # Stream found document count
                    if streaming_service and writer:
                        writer(
                            {
                                "yield_value": streaming_service.format_terminal_info_delta(
                                    f"📘 Found {len(notion_chunks)} Notion pages/blocks related to your query"
                                )
                            }
                        )

                elif connector == "GITHUB_CONNECTOR":
                    (
                        source_object,
                        github_chunks,
                    ) = await connector_service.search_github(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k,
                        search_mode=search_mode,
                    )

                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(github_chunks)

                    # Stream found document count
                    if streaming_service and writer:
                        writer(
                            {
                                "yield_value": streaming_service.format_terminal_info_delta(
                                    f"🐙 Found {len(github_chunks)} GitHub files/issues related to your query"
                                )
                            }
                        )

                elif connector == "LINEAR_CONNECTOR":
                    (
                        source_object,
                        linear_chunks,
                    ) = await connector_service.search_linear(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k,
                        search_mode=search_mode,
                    )

                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(linear_chunks)

                    # Stream found document count
                    if streaming_service and writer:
                        writer(
                            {
                                "yield_value": streaming_service.format_terminal_info_delta(
                                    f"📊 Found {len(linear_chunks)} Linear issues related to your query"
                                )
                            }
                        )

                elif connector == "TAVILY_API":
                    (
                        source_object,
                        tavily_chunks,
                    ) = await connector_service.search_tavily(
                        user_query=reformulated_query, user_id=user_id, top_k=top_k
                    )

                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(tavily_chunks)

                    # Stream found document count
                    if streaming_service and writer:
                        writer(
                            {
                                "yield_value": streaming_service.format_terminal_info_delta(
                                    f"🔍 Found {len(tavily_chunks)} Web Search results related to your query"
                                )
                            }
                        )

                elif connector == "LINKUP_API":
                    linkup_mode = "standard"

                    (
                        source_object,
                        linkup_chunks,
                    ) = await connector_service.search_linkup(
                        user_query=reformulated_query,
                        user_id=user_id,
                        mode=linkup_mode,
                    )

                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(linkup_chunks)

                    # Stream found document count
                    if streaming_service and writer:
                        writer(
                            {
                                "yield_value": streaming_service.format_terminal_info_delta(
                                    f"🔗 Found {len(linkup_chunks)} Linkup results related to your query"
                                )
                            }
                        )

                elif connector == "DISCORD_CONNECTOR":
                    (
                        source_object,
                        discord_chunks,
                    ) = await connector_service.search_discord(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k,
                        search_mode=search_mode,
                    )
                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(discord_chunks)
                    # Stream found document count
                    if streaming_service and writer:
                        writer(
                            {
                                "yield_value": streaming_service.format_terminal_info_delta(
                                    f"🗨️ Found {len(discord_chunks)} Discord messages related to your query"
                                )
                            }
                        )

                elif connector == "JIRA_CONNECTOR":
                    source_object, jira_chunks = await connector_service.search_jira(
                        user_query=reformulated_query,
                        user_id=user_id,
                        search_space_id=search_space_id,
                        top_k=top_k,
                        search_mode=search_mode,
                    )

                    # Add to sources and raw documents
                    if source_object:
                        all_sources.append(source_object)
                    all_raw_documents.extend(jira_chunks)

                    # Stream found document count
                    if streaming_service and writer:
                        writer(
                            {
                                "yield_value": streaming_service.format_terminal_info_delta(
                                    f"🎫 Found {len(jira_chunks)} Jira issues related to your query"
                                )
                            }
                        )

            except Exception as e:
                error_message = f"Error searching connector {connector}: {e!s}"
                print(error_message)

                # Stream error message
                if streaming_service and writer:
                    friendly_name = get_connector_friendly_name(connector)
                    writer(
                        {
                            "yield_value": streaming_service.format_error(
                                f"Error searching {friendly_name}: {e!s}"
                            )
                        }
                    )

                # Continue with other connectors on error
                continue

    # Deduplicate source objects by ID before streaming
    deduplicated_sources = []
    seen_source_keys = set()

    # First add user-selected sources (if any)
    if user_selected_sources:
        for source_obj in user_selected_sources:
            source_id = source_obj.get("id")
            source_type = source_obj.get("type")

            if source_id and source_type:
                source_key = f"{source_type}_{source_id}"
                if source_key not in seen_source_keys:
                    seen_source_keys.add(source_key)
                    deduplicated_sources.append(source_obj)
            else:
                deduplicated_sources.append(source_obj)

    # Then add connector sources
    for source_obj in all_sources:
        # Use combination of source ID and type as a unique identifier
        # This ensures we don't accidentally deduplicate sources from different connectors
        source_id = source_obj.get("id")
        source_type = source_obj.get("type")

        if source_id and source_type:
            source_key = f"{source_type}_{source_id}"
            current_sources_count = len(source_obj.get("sources", []))

            if source_key not in seen_source_keys:
                seen_source_keys.add(source_key)
                deduplicated_sources.append(source_obj)
                print(
                    f"Debug: Added source - ID: {source_id}, Type: {source_type}, Key: {source_key}, Sources count: {current_sources_count}"
                )
            else:
                # Check if this source object has more sources than the existing one
                existing_index = None
                for i, existing_source in enumerate(deduplicated_sources):
                    existing_id = existing_source.get("id")
                    existing_type = existing_source.get("type")
                    if existing_id == source_id and existing_type == source_type:
                        existing_index = i
                        break

                if existing_index is not None:
                    existing_sources_count = len(
                        deduplicated_sources[existing_index].get("sources", [])
                    )
                    if current_sources_count > existing_sources_count:
                        # Replace the existing source object with the new one that has more sources
                        deduplicated_sources[existing_index] = source_obj
                        print(
                            f"Debug: Replaced source - ID: {source_id}, Type: {source_type}, Key: {source_key}, Sources count: {existing_sources_count} -> {current_sources_count}"
                        )
                    else:
                        print(
                            f"Debug: Skipped duplicate source - ID: {source_id}, Type: {source_type}, Key: {source_key}, Sources count: {current_sources_count} <= {existing_sources_count}"
                        )
                else:
                    print(
                        f"Debug: Skipped duplicate source - ID: {source_id}, Type: {source_type}, Key: {source_key} (couldn't find existing)"
                    )
        else:
            # If there's no ID or type, just add it to be safe
            deduplicated_sources.append(source_obj)
            print(
                f"Debug: Added source without ID/type - {source_obj.get('name', 'UNKNOWN')}"
            )

    # Stream info about deduplicated sources
    if streaming_service and writer:
        user_source_count = len(user_selected_sources) if user_selected_sources else 0
        connector_source_count = len(deduplicated_sources) - user_source_count
        writer(
            {
                "yield_value": streaming_service.format_terminal_info_delta(
                    f"📚 Collected {len(deduplicated_sources)} total sources ({user_source_count} user-selected + {connector_source_count} from connectors)"
                )
            }
        )

    # After all sources are collected and deduplicated, stream them
    if streaming_service and writer:
        writer(
            {
                "yield_value": streaming_service.format_sources_delta(
                    deduplicated_sources
                )
            }
        )

    # Deduplicate raw documents based on chunk_id or content
    seen_chunk_ids = set()
    seen_content_hashes = set()
    deduplicated_docs = []

    for doc in all_raw_documents:
        chunk_id = doc.get("chunk_id")
        content = doc.get("content", "")
        content_hash = hash(content)

        # Skip if we've seen this chunk_id or content before
        if (
            chunk_id and chunk_id in seen_chunk_ids
        ) or content_hash in seen_content_hashes:
            continue

        # Add to our tracking sets and keep this document
        if chunk_id:
            seen_chunk_ids.add(chunk_id)
        seen_content_hashes.add(content_hash)
        deduplicated_docs.append(doc)

    # Stream info about deduplicated documents
    if streaming_service and writer:
        writer(
            {
                "yield_value": streaming_service.format_terminal_info_delta(
                    f"🧹 Found {len(deduplicated_docs)} unique document chunks after removing duplicates"
                )
            }
        )

    # Return deduplicated documents
    return deduplicated_docs


async def process_sections(
    state: State, config: RunnableConfig, writer: StreamWriter
) -> dict[str, Any]:
    """
    Process all sections in parallel and combine the results.

    This node takes the answer outline from the previous step, fetches relevant documents
    for all questions across all sections once, and then processes each section in parallel
    using the sub_section_writer graph with the shared document pool.

    Returns:
        Dict containing the final written report in the "final_written_report" key.
    """
    # Get configuration and answer outline from state
    configuration = Configuration.from_runnable_config(config)
    answer_outline = state.answer_outline
    streaming_service = state.streaming_service

    # Initialize a dictionary to track content for all sections
    # This is used to maintain section content while streaming multiple sections
    section_contents = {}

    writer(
        {
            "yield_value": streaming_service.format_terminal_info_delta(
                "🚀 Starting to process research sections..."
            )
        }
    )

    print(f"Processing sections from outline: {answer_outline is not None}")

    if not answer_outline:
        error_message = "No answer outline was provided. Cannot generate report."
        writer({"yield_value": streaming_service.format_error(error_message)})
        return {
            "final_written_report": "No answer outline was provided. Cannot generate final report."
        }

    # Collect all questions from all sections
    all_questions = []
    for section in answer_outline.answer_outline:
        all_questions.extend(section.questions)

    print(f"Collected {len(all_questions)} questions from all sections")
    writer(
        {
            "yield_value": streaming_service.format_terminal_info_delta(
                f"🧩 Found {len(all_questions)} research questions across {len(answer_outline.answer_outline)} sections"
            )
        }
    )

    # Fetch relevant documents once for all questions
    writer(
        {
            "yield_value": streaming_service.format_terminal_info_delta(
                "🔍 Searching for relevant information across all connectors..."
            )
        }
    )

    if configuration.num_sections == 1:
        top_k = 10
    elif configuration.num_sections == 3:
        top_k = 20
    elif configuration.num_sections == 6:
        top_k = 30
    else:
        top_k = 10

    relevant_documents = []
    user_selected_documents = []
    user_selected_sources = []

    try:
        # First, fetch user-selected documents if any
        if configuration.document_ids_to_add_in_context:
            writer(
                {
                    "yield_value": streaming_service.format_terminal_info_delta(
                        f"📋 Including {len(configuration.document_ids_to_add_in_context)} user-selected documents..."
                    )
                }
            )

            (
                user_selected_sources,
                user_selected_documents,
            ) = await fetch_documents_by_ids(
                document_ids=configuration.document_ids_to_add_in_context,
                user_id=configuration.user_id,
                db_session=state.db_session,
            )

            if user_selected_documents:
                writer(
                    {
                        "yield_value": streaming_service.format_terminal_info_delta(
                            f"✅ Successfully added {len(user_selected_documents)} user-selected documents to context"
                        )
                    }
                )

        # Create connector service using state db_session
        connector_service = ConnectorService(
            state.db_session, user_id=configuration.user_id
        )
        await connector_service.initialize_counter()

        relevant_documents = await fetch_relevant_documents(
            research_questions=all_questions,
            user_id=configuration.user_id,
            search_space_id=configuration.search_space_id,
            db_session=state.db_session,
            connectors_to_search=configuration.connectors_to_search,
            writer=writer,
            state=state,
            top_k=top_k,
            connector_service=connector_service,
            search_mode=configuration.search_mode,
            user_selected_sources=user_selected_sources,
        )
    except Exception as e:
        error_message = f"Error fetching relevant documents: {e!s}"
        print(error_message)
        writer({"yield_value": streaming_service.format_error(error_message)})
        # Log the error and continue with an empty list of documents
        # This allows the process to continue, but the report might lack information
        relevant_documents = []

    # Combine user-selected documents with connector-fetched documents
    all_documents = user_selected_documents + relevant_documents

    print(f"Fetched {len(relevant_documents)} relevant documents for all sections")
    print(
        f"Added {len(user_selected_documents)} user-selected documents for all sections"
    )
    print(f"Total documents for sections: {len(all_documents)}")

    writer(
        {
            "yield_value": streaming_service.format_terminal_info_delta(
                f"✨ Starting to draft {len(answer_outline.answer_outline)} sections using {len(all_documents)} total document chunks ({len(user_selected_documents)} user-selected + {len(relevant_documents)} connector-found)"
            )
        }
    )

    # Create tasks to process each section in parallel with the same document set
    section_tasks = []
    writer(
        {
            "yield_value": streaming_service.format_terminal_info_delta(
                "⚙️ Creating processing tasks for each section..."
            )
        }
    )

    for i, section in enumerate(answer_outline.answer_outline):
        if i == 0:
            sub_section_type = SubSectionType.START
        elif i == len(answer_outline.answer_outline) - 1:
            sub_section_type = SubSectionType.END
        else:
            sub_section_type = SubSectionType.MIDDLE

        # Initialize the section_contents entry for this section
        section_contents[i] = {
            "title": section.section_title,
            "content": "",
            "index": i,
        }

        section_tasks.append(
            process_section_with_documents(
                section_id=i,
                section_title=section.section_title,
                section_questions=section.questions,
                user_query=configuration.user_query,
                user_id=configuration.user_id,
                search_space_id=configuration.search_space_id,
                relevant_documents=all_documents,  # Use combined documents
                state=state,
                writer=writer,
                sub_section_type=sub_section_type,
                section_contents=section_contents,
            )
        )

    # Run all section processing tasks in parallel
    print(f"Running {len(section_tasks)} section processing tasks in parallel")
    writer(
        {
            "yield_value": streaming_service.format_terminal_info_delta(
                f"⏳ Processing {len(section_tasks)} sections simultaneously..."
            )
        }
    )

    section_results = await asyncio.gather(*section_tasks, return_exceptions=True)

    # Handle any exceptions in the results
    writer(
        {
            "yield_value": streaming_service.format_terminal_info_delta(
                "🧵 Combining section results into final report..."
            )
        }
    )

    processed_results = []
    for i, result in enumerate(section_results):
        if isinstance(result, Exception):
            section_title = answer_outline.answer_outline[i].section_title
            error_message = f"Error processing section '{section_title}': {result!s}"
            print(error_message)
            writer({"yield_value": streaming_service.format_error(error_message)})
            processed_results.append(error_message)
        else:
            processed_results.append(result)

    # Combine the results into a final report with section titles
    final_report = []
    for _i, (section, content) in enumerate(
        zip(answer_outline.answer_outline, processed_results, strict=False)
    ):
        # Skip adding the section header since the content already contains the title
        final_report.append(content)
        final_report.append("\n")

        # Stream each section with its title
        writer(
            {
                "yield_value": state.streaming_service.format_text_chunk(
                    f"# {section.section_title}\n\n{content}"
                )
            }
        )

    # Join all sections with newlines
    final_written_report = "\n".join(final_report)
    print(f"Generated final report with {len(final_report)} parts")

    writer(
        {
            "yield_value": streaming_service.format_terminal_info_delta(
                "🎉 Final research report generated successfully!"
            )
        }
    )

    # Use the shared documents for further question generation
    # Since all sections used the same document pool, we can use it directly
    return {
        "final_written_report": final_written_report,
        "reranked_documents": all_documents,
    }


async def process_section_with_documents(
    section_id: int,
    section_title: str,
    section_questions: list[str],
    user_id: str,
    search_space_id: int,
    relevant_documents: list[dict[str, Any]],
    user_query: str,
    state: State = None,
    writer: StreamWriter = None,
    sub_section_type: SubSectionType = SubSectionType.MIDDLE,
    section_contents: dict[int, dict[str, Any]] | None = None,
) -> str:
    """
    Process a single section using pre-fetched documents.

    Args:
        section_id: The ID of the section
        section_title: The title of the section
        section_questions: List of research questions for this section
        user_id: The user ID
        search_space_id: The search space ID
        relevant_documents: Pre-fetched documents to use for this section
        state: The current state
        writer: StreamWriter for sending progress updates
        sub_section_type: The type of section (start, middle, end)
        section_contents: Dictionary to track content across multiple sections

    Returns:
        The written section content
    """
    try:
        # Use the provided documents
        documents_to_use = relevant_documents

        # Send status update via streaming if available
        if state and state.streaming_service and writer:
            writer(
                {
                    "yield_value": state.streaming_service.format_terminal_info_delta(
                        f'📝 Writing section: "{section_title}" with {len(section_questions)} research questions'
                    )
                }
            )

        # Fallback if no documents found
        if not documents_to_use:
            print(f"No relevant documents found for section: {section_title}")
            if state and state.streaming_service and writer:
                writer(
                    {
                        "yield_value": state.streaming_service.format_terminal_info_delta(
                            f'📝 Writing section "{section_title}" using general knowledge (no specific sources found)'
                        )
                    }
                )

            documents_to_use = [
                {"content": f"No specific information was found for: {question}"}
                for question in section_questions
            ]

        # Call the sub_section_writer graph with the appropriate config
        config = {
            "configurable": {
                "sub_section_title": section_title,
                "sub_section_questions": section_questions,
                "sub_section_type": sub_section_type,
                "user_query": user_query,
                "relevant_documents": documents_to_use,
                "user_id": user_id,
                "search_space_id": search_space_id,
            }
        }

        # Create the initial state with db_session and chat_history
        sub_state = {"db_session": state.db_session, "chat_history": state.chat_history}

        # Invoke the sub-section writer graph with streaming
        print(f"Invoking sub_section_writer for: {section_title}")
        if state and state.streaming_service and writer:
            writer(
                {
                    "yield_value": state.streaming_service.format_terminal_info_delta(
                        f'🧠 Analyzing information and drafting content for section: "{section_title}"'
                    )
                }
            )

        # Variables to track streaming state
        complete_content = ""  # Tracks the complete content received so far

        async for _chunk_type, chunk in sub_section_writer_graph.astream(
            sub_state, config, stream_mode=["values"]
        ):
            if "final_answer" in chunk:
                new_content = chunk["final_answer"]
                if new_content and new_content != complete_content:
                    # Extract only the new content (delta)
                    delta = new_content[len(complete_content) :]

                    # Update what we've processed so far
                    complete_content = new_content

                    # Only stream if there's actual new content
                    if delta and state and state.streaming_service and writer:
                        # Update terminal with real-time progress indicator
                        writer(
                            {
                                "yield_value": state.streaming_service.format_terminal_info_delta(
                                    f"✍️ Writing section {section_id + 1}... ({len(complete_content.split())} words)"
                                )
                            }
                        )

                        # Update section_contents with just the new delta
                        section_contents[section_id]["content"] += delta

                        # Build UI-friendly content for all sections
                        complete_answer = []
                        for i in range(len(section_contents)):
                            if i in section_contents and section_contents[i]["content"]:
                                # Add section header
                                complete_answer.append(
                                    f"# {section_contents[i]['title']}"
                                )
                                complete_answer.append("")  # Empty line after title

                                # Add section content
                                content_lines = section_contents[i]["content"].split(
                                    "\n"
                                )
                                complete_answer.extend(content_lines)
                                complete_answer.append("")  # Empty line after content

        # Set default if no content was received
        if not complete_content:
            complete_content = "No content was generated for this section."
            section_contents[section_id]["content"] = complete_content

        # Final terminal update
        if state and state.streaming_service and writer:
            writer(
                {
                    "yield_value": state.streaming_service.format_terminal_info_delta(
                        f'✅ Completed section: "{section_title}"'
                    )
                }
            )

        return complete_content
    except Exception as e:
        print(f"Error processing section '{section_title}': {e!s}")

        # Send error update via streaming if available
        if state and state.streaming_service and writer:
            writer(
                {
                    "yield_value": state.streaming_service.format_error(
                        f'Error processing section "{section_title}": {e!s}'
                    )
                }
            )

        return f"Error processing section: {section_title}. Details: {e!s}"


async def reformulate_user_query(
    state: State, config: RunnableConfig, writer: StreamWriter
) -> dict[str, Any]:
    """
    Reforms the user query based on the chat history.
    """

    configuration = Configuration.from_runnable_config(config)
    user_query = configuration.user_query
    chat_history_str = await QueryService.langchain_chat_history_to_str(
        state.chat_history
    )
    if len(state.chat_history) == 0:
        reformulated_query = user_query
    else:
        reformulated_query = await QueryService.reformulate_query_with_chat_history(
            user_query=user_query,
            session=state.db_session,
            user_id=configuration.user_id,
            chat_history_str=chat_history_str,
        )

    return {"reformulated_query": reformulated_query}


async def handle_qna_workflow(
    state: State, config: RunnableConfig, writer: StreamWriter
) -> dict[str, Any]:
    """
    Handle the QNA research workflow.

    This node fetches relevant documents for the user query and then uses the QNA agent
    to generate a comprehensive answer with proper citations.

    Returns:
        Dict containing the final answer in the "final_written_report" key for consistency.
    """
    streaming_service = state.streaming_service
    configuration = Configuration.from_runnable_config(config)

    reformulated_query = state.reformulated_query
    user_query = configuration.user_query

    writer(
        {
            "yield_value": streaming_service.format_terminal_info_delta(
                "🤔 Starting Q&A research workflow..."
            )
        }
    )

    writer(
        {
            "yield_value": streaming_service.format_terminal_info_delta(
                f'🔍 Researching: "{user_query[:100]}..."'
            )
        }
    )

    # Fetch relevant documents for the QNA query
    writer(
        {
            "yield_value": streaming_service.format_terminal_info_delta(
                "🔍 Searching for relevant information across all connectors..."
            )
        }
    )

    # Use a reasonable top_k for QNA - not too many documents to avoid overwhelming the LLM
    top_k = 15

    relevant_documents = []
    user_selected_documents = []
    user_selected_sources = []

    try:
        # First, fetch user-selected documents if any
        if configuration.document_ids_to_add_in_context:
            writer(
                {
                    "yield_value": streaming_service.format_terminal_info_delta(
                        f"📋 Including {len(configuration.document_ids_to_add_in_context)} user-selected documents..."
                    )
                }
            )

            (
                user_selected_sources,
                user_selected_documents,
            ) = await fetch_documents_by_ids(
                document_ids=configuration.document_ids_to_add_in_context,
                user_id=configuration.user_id,
                db_session=state.db_session,
            )

            if user_selected_documents:
                writer(
                    {
                        "yield_value": streaming_service.format_terminal_info_delta(
                            f"✅ Successfully added {len(user_selected_documents)} user-selected documents to context"
                        )
                    }
                )

        # Create connector service using state db_session
        connector_service = ConnectorService(
            state.db_session, user_id=configuration.user_id
        )
        await connector_service.initialize_counter()

        # Use the reformulated query as a single research question
        research_questions = [reformulated_query, user_query]

        relevant_documents = await fetch_relevant_documents(
            research_questions=research_questions,
            user_id=configuration.user_id,
            search_space_id=configuration.search_space_id,
            db_session=state.db_session,
            connectors_to_search=configuration.connectors_to_search,
            writer=writer,
            state=state,
            top_k=top_k,
            connector_service=connector_service,
            search_mode=configuration.search_mode,
            user_selected_sources=user_selected_sources,
        )
    except Exception as e:
        error_message = f"Error fetching relevant documents for QNA: {e!s}"
        print(error_message)
        writer({"yield_value": streaming_service.format_error(error_message)})
        # Continue with empty documents - the QNA agent will handle this gracefully
        relevant_documents = []

    # Combine user-selected documents with connector-fetched documents
    all_documents = user_selected_documents + relevant_documents

    print(f"Fetched {len(relevant_documents)} relevant documents for QNA")
    print(f"Added {len(user_selected_documents)} user-selected documents for QNA")
    print(f"Total documents for QNA: {len(all_documents)}")

    writer(
        {
            "yield_value": streaming_service.format_terminal_info_delta(
                f"🧠 Generating comprehensive answer using {len(all_documents)} total sources ({len(user_selected_documents)} user-selected + {len(relevant_documents)} connector-found)..."
            )
        }
    )

    # Prepare configuration for the QNA agent
    qna_config = {
        "configurable": {
            "user_query": user_query,  # Use the reformulated query
            "reformulated_query": reformulated_query,
            "relevant_documents": all_documents,  # Use combined documents
            "user_id": configuration.user_id,
            "search_space_id": configuration.search_space_id,
        }
    }

    # Create the state for the QNA agent (it has a different state structure)
    qna_state = {"db_session": state.db_session, "chat_history": state.chat_history}

    try:
        writer(
            {
                "yield_value": streaming_service.format_terminal_info_delta(
                    "✍️ Writing comprehensive answer with citations..."
                )
            }
        )

        # Track streaming content for real-time updates
        complete_content = ""
        captured_reranked_documents = []

        # Call the QNA agent with streaming
        async for _chunk_type, chunk in qna_agent_graph.astream(
            qna_state, qna_config, stream_mode=["values"]
        ):
            if "final_answer" in chunk:
                new_content = chunk["final_answer"]
                if new_content and new_content != complete_content:
                    # Extract only the new content (delta)
                    delta = new_content[len(complete_content) :]
                    complete_content = new_content

                    # Stream the real-time answer if there's new content
                    if delta:
                        # Update terminal with progress
                        word_count = len(complete_content.split())
                        writer(
                            {
                                "yield_value": streaming_service.format_terminal_info_delta(
                                    f"✍️ Writing answer... ({word_count} words)"
                                )
                            }
                        )

                        writer(
                            {"yield_value": streaming_service.format_text_chunk(delta)}
                        )

            # Capture reranked documents from QNA agent for further question generation
            if "reranked_documents" in chunk:
                captured_reranked_documents = chunk["reranked_documents"]

        # Set default if no content was received
        if not complete_content:
            complete_content = "I couldn't find relevant information in your knowledge base to answer this question."

        writer(
            {
                "yield_value": streaming_service.format_terminal_info_delta(
                    "🎉 Q&A answer generated successfully!"
                )
            }
        )

        # Return the final answer and captured reranked documents for further question generation
        return {
            "final_written_report": complete_content,
            "reranked_documents": captured_reranked_documents,
        }

    except Exception as e:
        error_message = f"Error generating QNA answer: {e!s}"
        print(error_message)
        writer({"yield_value": streaming_service.format_error(error_message)})

        return {"final_written_report": f"Error generating answer: {e!s}"}


async def generate_further_questions(
    state: State, config: RunnableConfig, writer: StreamWriter
) -> dict[str, Any]:
    """
    Generate contextually relevant follow-up questions based on chat history and available documents.

    This node takes the chat history and reranked documents from sub-agents (qna_agent or sub_section_writer)
    and uses an LLM to generate follow-up questions that would naturally extend the conversation
    and provide additional value to the user.

    Returns:
        Dict containing the further questions in the "further_questions" key for state update.
    """
    from app.services.llm_service import get_user_fast_llm

    # Get configuration and state data
    configuration = Configuration.from_runnable_config(config)
    chat_history = state.chat_history
    user_id = configuration.user_id
    streaming_service = state.streaming_service

    # Get reranked documents from the state (will be populated by sub-agents)
    reranked_documents = getattr(state, "reranked_documents", None) or []

    writer(
        {
            "yield_value": streaming_service.format_terminal_info_delta(
                "🤔 Generating follow-up questions..."
            )
        }
    )

    # Get user's fast LLM
    llm = await get_user_fast_llm(state.db_session, user_id)
    if not llm:
        error_message = f"No fast LLM configured for user {user_id}"
        print(error_message)
        writer({"yield_value": streaming_service.format_error(error_message)})

        # Stream empty further questions to UI
        writer({"yield_value": streaming_service.format_further_questions_delta([])})
        return {"further_questions": []}

    # Format chat history for the prompt
    chat_history_xml = "<chat_history>\n"
    for message in chat_history:
        if hasattr(message, "type"):
            if message.type == "human":
                chat_history_xml += f"<user>{message.content}</user>\n"
            elif message.type == "ai":
                chat_history_xml += f"<assistant>{message.content}</assistant>\n"
        else:
            # Handle other message types if needed
            chat_history_xml += f"<message>{message!s}</message>\n"
    chat_history_xml += "</chat_history>"

    # Format available documents for the prompt
    documents_xml = "<documents>\n"
    for i, doc in enumerate(reranked_documents):
        document_info = doc.get("document", {})
        source_id = document_info.get("id", f"doc_{i}")
        source_type = document_info.get("document_type", "UNKNOWN")
        content = doc.get("content", "")

        documents_xml += "<document>\n"
        documents_xml += "<metadata>\n"
        documents_xml += f"<source_id>{source_id}</source_id>\n"
        documents_xml += f"<source_type>{source_type}</source_type>\n"
        documents_xml += "</metadata>\n"
        documents_xml += f"<content>\n{content}</content>\n"
        documents_xml += "</document>\n"
    documents_xml += "</documents>"

    # Create the human message content
    human_message_content = f"""
    {chat_history_xml}

    {documents_xml}

    Based on the chat history and available documents above, generate 3-5 contextually relevant follow-up questions that would naturally extend the conversation and provide additional value to the user. Make sure the questions can be reasonably answered using the available documents or knowledge base.

    Your response MUST be valid JSON in exactly this format:
    {{
      "further_questions": [
        {{
          "id": 0,
          "question": "further qn 1"
        }},
        {{
          "id": 1,
          "question": "further qn 2"
        }}
      ]
    }}

    Do not include any other text or explanation. Only return the JSON.
    """

    writer(
        {
            "yield_value": streaming_service.format_terminal_info_delta(
                "🧠 Analyzing conversation context to suggest relevant questions..."
            )
        }
    )

    # Create messages for the LLM
    messages = [
        SystemMessage(content=get_further_questions_system_prompt()),
        HumanMessage(content=human_message_content),
    ]

    try:
        # Call the LLM
        response = await llm.ainvoke(messages)

        # Parse the JSON response
        content = response.content

        # Find the JSON in the content
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = content[json_start:json_end]

            # Parse the JSON string
            parsed_data = json.loads(json_str)

            # Extract the further_questions array
            further_questions = parsed_data.get("further_questions", [])

            writer(
                {
                    "yield_value": streaming_service.format_terminal_info_delta(
                        f"✅ Generated {len(further_questions)} contextual follow-up questions!"
                    )
                }
            )

            # Stream the further questions to the UI
            writer(
                {
                    "yield_value": streaming_service.format_further_questions_delta(
                        further_questions
                    )
                }
            )

            print(f"Successfully generated {len(further_questions)} further questions")

            return {"further_questions": further_questions}
        else:
            # If JSON structure not found, return empty list
            error_message = (
                "Could not find valid JSON in LLM response for further questions"
            )
            print(error_message)
            writer(
                {
                    "yield_value": streaming_service.format_error(
                        f"Warning: {error_message}"
                    )
                }
            )

            # Stream empty further questions to UI
            writer(
                {"yield_value": streaming_service.format_further_questions_delta([])}
            )
            return {"further_questions": []}

    except (json.JSONDecodeError, ValueError) as e:
        # Log the error and return empty list
        error_message = f"Error parsing further questions response: {e!s}"
        print(error_message)
        writer(
            {"yield_value": streaming_service.format_error(f"Warning: {error_message}")}
        )

        # Stream empty further questions to UI
        writer({"yield_value": streaming_service.format_further_questions_delta([])})
        return {"further_questions": []}

    except Exception as e:
        # Handle any other errors
        error_message = f"Error generating further questions: {e!s}"
        print(error_message)
        writer(
            {"yield_value": streaming_service.format_error(f"Warning: {error_message}")}
        )

        # Stream empty further questions to UI
        writer({"yield_value": streaming_service.format_further_questions_delta([])})
        return {"further_questions": []}
