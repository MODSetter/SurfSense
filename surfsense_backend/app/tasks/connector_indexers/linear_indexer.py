"""
Linear connector indexer.
"""

from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.linear_connector import LinearConnector
from app.db import Document, DocumentType, SearchSourceConnectorType
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)

from .base import (
    calculate_date_range,
    check_document_by_unique_identifier,
    get_connector_by_id,
    logger,
    update_connector_last_indexed,
)


async def index_linear_issues(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index Linear issues and comments.

    Args:
        session: Database session
        connector_id: ID of the Linear connector
        search_space_id: ID of the search space to store documents in
        user_id: ID of the user
        start_date: Start date for indexing (YYYY-MM-DD format)
        end_date: End date for indexing (YYYY-MM-DD format)
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="linear_issues_indexing",
        source="connector_indexing_task",
        message=f"Starting Linear issues indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    try:
        # Get the connector
        await task_logger.log_task_progress(
            log_entry,
            f"Retrieving Linear connector {connector_id} from database",
            {"stage": "connector_retrieval"},
        )

        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.LINEAR_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not a Linear connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return (
                0,
                f"Connector with ID {connector_id} not found or is not a Linear connector",
            )

        # Get the Linear token from the connector config
        linear_token = connector.config.get("LINEAR_API_KEY")
        if not linear_token:
            await task_logger.log_task_failure(
                log_entry,
                f"Linear API token not found in connector config for connector {connector_id}",
                "Missing Linear token",
                {"error_type": "MissingToken"},
            )
            return 0, "Linear API token not found in connector config"

        # Initialize Linear client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Linear client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        linear_client = LinearConnector(token=linear_token)

        # Calculate date range
        start_date_str, end_date_str = calculate_date_range(
            connector, start_date, end_date, default_days_back=365
        )

        logger.info(f"Fetching Linear issues from {start_date_str} to {end_date_str}")

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Linear issues from {start_date_str} to {end_date_str}",
            {
                "stage": "fetch_issues",
                "start_date": start_date_str,
                "end_date": end_date_str,
            },
        )

        # Get issues within date range
        try:
            issues, error = linear_client.get_issues_by_date_range(
                start_date=start_date_str, end_date=end_date_str, include_comments=True
            )

            if error:
                logger.error(f"Failed to get Linear issues: {error}")

                # Don't treat "No issues found" as an error that should stop indexing
                if "No issues found" in error:
                    logger.info(
                        "No issues found is not a critical error, continuing with update"
                    )
                    if update_last_indexed:
                        await update_connector_last_indexed(
                            session, connector, update_last_indexed
                        )
                        await session.commit()
                        logger.info(
                            f"Updated last_indexed_at to {connector.last_indexed_at} despite no issues found"
                        )
                    return 0, None
                else:
                    return 0, f"Failed to get Linear issues: {error}"

            logger.info(f"Retrieved {len(issues)} issues from Linear API")

        except Exception as e:
            logger.error(f"Exception when calling Linear API: {e!s}", exc_info=True)
            return 0, f"Failed to get Linear issues: {e!s}"

        if not issues:
            logger.info("No Linear issues found for the specified date range")
            if update_last_indexed:
                await update_connector_last_indexed(
                    session, connector, update_last_indexed
                )
                await session.commit()
                logger.info(
                    f"Updated last_indexed_at to {connector.last_indexed_at} despite no issues found"
                )
            return 0, None  # Return None instead of error message when no issues found

        # Track the number of documents indexed
        documents_indexed = 0
        documents_skipped = 0
        skipped_issues = []

        await task_logger.log_task_progress(
            log_entry,
            f"Starting to process {len(issues)} Linear issues",
            {"stage": "process_issues", "total_issues": len(issues)},
        )

        # Process each issue
        for issue in issues:
            try:
                issue_id = issue.get("id", "")
                issue_identifier = issue.get("identifier", "")
                issue_title = issue.get("title", "")

                if not issue_id or not issue_title:
                    logger.warning(
                        f"Skipping issue with missing ID or title: {issue_id or 'Unknown'}"
                    )
                    skipped_issues.append(
                        f"{issue_identifier or 'Unknown'} (missing data)"
                    )
                    documents_skipped += 1
                    continue

                # Format the issue first to get well-structured data
                formatted_issue = linear_client.format_issue(issue)

                # Convert issue to markdown format
                issue_content = linear_client.format_issue_to_markdown(formatted_issue)

                if not issue_content:
                    logger.warning(
                        f"Skipping issue with no content: {issue_identifier} - {issue_title}"
                    )
                    skipped_issues.append(f"{issue_identifier} (no content)")
                    documents_skipped += 1
                    continue

                # Generate unique identifier hash for this Linear issue
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.LINEAR_CONNECTOR, issue_id, search_space_id
                )

                # Generate content hash
                content_hash = generate_content_hash(issue_content, search_space_id)

                # Check if document with this unique identifier already exists
                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                state = formatted_issue.get("state", "Unknown")
                description = formatted_issue.get("description", "")
                comment_count = len(formatted_issue.get("comments", []))

                if existing_document:
                    # Document exists - check if content has changed
                    if existing_document.content_hash == content_hash:
                        logger.info(
                            f"Document for Linear issue {issue_identifier} unchanged. Skipping."
                        )
                        documents_skipped += 1
                        continue
                    else:
                        # Content has changed - update the existing document
                        logger.info(
                            f"Content changed for Linear issue {issue_identifier}. Updating document."
                        )

                        # Generate summary with metadata
                        user_llm = await get_user_long_context_llm(
                            session, user_id, search_space_id
                        )

                        if user_llm:
                            document_metadata = {
                                "issue_id": issue_identifier,
                                "issue_title": issue_title,
                                "state": state,
                                "priority": formatted_issue.get("priority", "Unknown"),
                                "comment_count": comment_count,
                                "document_type": "Linear Issue",
                                "connector_type": "Linear",
                            }
                            (
                                summary_content,
                                summary_embedding,
                            ) = await generate_document_summary(
                                issue_content, user_llm, document_metadata
                            )
                        else:
                            # Fallback to simple summary if no LLM configured
                            if description and len(description) > 1000:
                                description = description[:997] + "..."
                            summary_content = f"Linear Issue {issue_identifier}: {issue_title}\n\nStatus: {state}\n\n"
                            if description:
                                summary_content += f"Description: {description}\n\n"
                            summary_content += f"Comments: {comment_count}"
                            summary_embedding = config.embedding_model_instance.embed(
                                summary_content
                            )

                        # Process chunks
                        chunks = await create_document_chunks(issue_content)

                        # Update existing document
                        existing_document.title = (
                            f"Linear - {issue_identifier}: {issue_title}"
                        )
                        existing_document.content = summary_content
                        existing_document.content_hash = content_hash
                        existing_document.embedding = summary_embedding
                        existing_document.document_metadata = {
                            "issue_id": issue_id,
                            "issue_identifier": issue_identifier,
                            "issue_title": issue_title,
                            "state": state,
                            "comment_count": comment_count,
                            "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                        existing_document.chunks = chunks

                        documents_indexed += 1
                        logger.info(
                            f"Successfully updated Linear issue {issue_identifier}"
                        )
                        continue

                # Document doesn't exist - create new one
                # Generate summary with metadata
                user_llm = await get_user_long_context_llm(
                    session, user_id, search_space_id
                )

                if user_llm:
                    document_metadata = {
                        "issue_id": issue_identifier,
                        "issue_title": issue_title,
                        "state": state,
                        "priority": formatted_issue.get("priority", "Unknown"),
                        "comment_count": comment_count,
                        "document_type": "Linear Issue",
                        "connector_type": "Linear",
                    }
                    (
                        summary_content,
                        summary_embedding,
                    ) = await generate_document_summary(
                        issue_content, user_llm, document_metadata
                    )
                else:
                    # Fallback to simple summary if no LLM configured
                    # Truncate description if it's too long for the summary
                    if description and len(description) > 1000:
                        description = description[:997] + "..."
                    summary_content = f"Linear Issue {issue_identifier}: {issue_title}\n\nStatus: {state}\n\n"
                    if description:
                        summary_content += f"Description: {description}\n\n"
                    summary_content += f"Comments: {comment_count}"
                    summary_embedding = config.embedding_model_instance.embed(
                        summary_content
                    )

                # Process chunks - using the full issue content with comments
                chunks = await create_document_chunks(issue_content)

                # Create and store new document
                logger.info(
                    f"Creating new document for issue {issue_identifier} - {issue_title}"
                )
                document = Document(
                    search_space_id=search_space_id,
                    title=f"Linear - {issue_identifier}: {issue_title}",
                    document_type=DocumentType.LINEAR_CONNECTOR,
                    document_metadata={
                        "issue_id": issue_id,
                        "issue_identifier": issue_identifier,
                        "issue_title": issue_title,
                        "state": state,
                        "comment_count": comment_count,
                        "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    content=summary_content,
                    content_hash=content_hash,
                    unique_identifier_hash=unique_identifier_hash,
                    embedding=summary_embedding,
                    chunks=chunks,
                )

                session.add(document)
                documents_indexed += 1
                logger.info(
                    f"Successfully indexed new issue {issue_identifier} - {issue_title}"
                )

                # Batch commit every 10 documents
                if documents_indexed % 10 == 0:
                    logger.info(
                        f"Committing batch: {documents_indexed} Linear issues processed so far"
                    )
                    await session.commit()

            except Exception as e:
                logger.error(
                    f"Error processing issue {issue.get('identifier', 'Unknown')}: {e!s}",
                    exc_info=True,
                )
                skipped_issues.append(
                    f"{issue.get('identifier', 'Unknown')} (processing error)"
                )
                documents_skipped += 1
                continue  # Skip this issue and continue with others

        # Update the last_indexed_at timestamp for the connector only if requested
        total_processed = documents_indexed
        if update_last_indexed:
            await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit for any remaining documents not yet committed in batches
        logger.info(f"Final commit: Total {documents_indexed} Linear issues processed")
        await session.commit()
        logger.info("Successfully committed all Linear document changes to database")

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Linear indexing for connector {connector_id}",
            {
                "issues_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "skipped_issues_count": len(skipped_issues),
            },
        )

        logger.info(
            f"Linear indexing completed: {documents_indexed} new issues, {documents_skipped} skipped"
        )
        return (
            total_processed,
            None,
        )  # Return None as the error message to indicate success

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Linear indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Linear issues for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Linear issues: {e!s}", exc_info=True)
        return 0, f"Failed to index Linear issues: {e!s}"
