"""
Jira connector indexer.
"""

from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.jira_connector import JiraConnector
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


async def index_jira_issues(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index Jira issues and comments.

    Args:
        session: Database session
        connector_id: ID of the Jira connector
        search_space_id: ID of the search space to store documents in
        user_id: User ID
        start_date: Start date for indexing (YYYY-MM-DD format)
        end_date: End date for indexing (YYYY-MM-DD format)
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="jira_issues_indexing",
        source="connector_indexing_task",
        message=f"Starting Jira issues indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    try:
        # Get the connector from the database
        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.JIRA_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return 0, f"Connector with ID {connector_id} not found"

        # Get the Jira credentials from the connector config
        jira_email = connector.config.get("JIRA_EMAIL")
        jira_api_token = connector.config.get("JIRA_API_TOKEN")
        jira_base_url = connector.config.get("JIRA_BASE_URL")

        if not jira_email or not jira_api_token or not jira_base_url:
            await task_logger.log_task_failure(
                log_entry,
                f"Jira credentials not found in connector config for connector {connector_id}",
                "Missing Jira credentials",
                {"error_type": "MissingCredentials"},
            )
            return 0, "Jira credentials not found in connector config"

        # Initialize Jira client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Jira client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        jira_client = JiraConnector(
            base_url=jira_base_url, email=jira_email, api_token=jira_api_token
        )

        # Calculate date range
        start_date_str, end_date_str = calculate_date_range(
            connector, start_date, end_date, default_days_back=365
        )

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Jira issues from {start_date_str} to {end_date_str}",
            {
                "stage": "fetching_issues",
                "start_date": start_date_str,
                "end_date": end_date_str,
            },
        )

        # Get issues within date range
        try:
            issues, error = jira_client.get_issues_by_date_range(
                start_date=start_date_str, end_date=end_date_str, include_comments=True
            )

            if error:
                logger.error(f"Failed to get Jira issues: {error}")

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

                    await task_logger.log_task_success(
                        log_entry,
                        f"No Jira issues found in date range {start_date_str} to {end_date_str}",
                        {"issues_found": 0},
                    )
                    return 0, None
                else:
                    await task_logger.log_task_failure(
                        log_entry,
                        f"Failed to get Jira issues: {error}",
                        "API Error",
                        {"error_type": "APIError"},
                    )
                    return 0, f"Failed to get Jira issues: {error}"

            logger.info(f"Retrieved {len(issues)} issues from Jira API")

        except Exception as e:
            logger.error(f"Error fetching Jira issues: {e!s}", exc_info=True)
            return 0, f"Error fetching Jira issues: {e!s}"

        # Process and index each issue
        documents_indexed = 0
        skipped_issues = []
        documents_skipped = 0

        for issue in issues:
            try:
                issue_id = issue.get("key")
                issue_identifier = issue.get("key", "")
                issue_title = issue.get("id", "")

                if not issue_id or not issue_title:
                    logger.warning(
                        f"Skipping issue with missing ID or title: {issue_id or 'Unknown'}"
                    )
                    skipped_issues.append(
                        f"{issue_identifier or 'Unknown'} (missing data)"
                    )
                    documents_skipped += 1
                    continue

                # Format the issue for better readability
                formatted_issue = jira_client.format_issue(issue)

                # Convert to markdown
                issue_content = jira_client.format_issue_to_markdown(formatted_issue)

                if not issue_content:
                    logger.warning(
                        f"Skipping issue with no content: {issue_identifier} - {issue_title}"
                    )
                    skipped_issues.append(f"{issue_identifier} (no content)")
                    documents_skipped += 1
                    continue

                # Generate unique identifier hash for this Jira issue
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.JIRA_CONNECTOR, issue_id, search_space_id
                )

                # Generate content hash
                content_hash = generate_content_hash(issue_content, search_space_id)

                # Check if document with this unique identifier already exists
                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                comment_count = len(formatted_issue.get("comments", []))

                if existing_document:
                    # Document exists - check if content has changed
                    if existing_document.content_hash == content_hash:
                        logger.info(
                            f"Document for Jira issue {issue_identifier} unchanged. Skipping."
                        )
                        documents_skipped += 1
                        continue
                    else:
                        # Content has changed - update the existing document
                        logger.info(
                            f"Content changed for Jira issue {issue_identifier}. Updating document."
                        )

                        # Generate summary with metadata
                        user_llm = await get_user_long_context_llm(
                            session, user_id, search_space_id
                        )

                        if user_llm:
                            document_metadata = {
                                "issue_key": issue_identifier,
                                "issue_title": issue_title,
                                "status": formatted_issue.get("status", "Unknown"),
                                "priority": formatted_issue.get("priority", "Unknown"),
                                "comment_count": comment_count,
                                "document_type": "Jira Issue",
                                "connector_type": "Jira",
                            }
                            (
                                summary_content,
                                summary_embedding,
                            ) = await generate_document_summary(
                                issue_content, user_llm, document_metadata
                            )
                        else:
                            summary_content = f"Jira Issue {issue_identifier}: {issue_title}\n\nStatus: {formatted_issue.get('status', 'Unknown')}\n\n"
                            if formatted_issue.get("description"):
                                summary_content += f"Description: {formatted_issue.get('description')}\n\n"
                            summary_content += f"Comments: {comment_count}"
                            summary_embedding = config.embedding_model_instance.embed(
                                summary_content
                            )

                        # Process chunks
                        chunks = await create_document_chunks(issue_content)

                        # Update existing document
                        existing_document.title = (
                            f"Jira - {issue_identifier}: {issue_title}"
                        )
                        existing_document.content = summary_content
                        existing_document.content_hash = content_hash
                        existing_document.embedding = summary_embedding
                        existing_document.document_metadata = {
                            "issue_id": issue_id,
                            "issue_identifier": issue_identifier,
                            "issue_title": issue_title,
                            "state": formatted_issue.get("status", "Unknown"),
                            "comment_count": comment_count,
                            "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                        existing_document.chunks = chunks

                        documents_indexed += 1
                        logger.info(
                            f"Successfully updated Jira issue {issue_identifier}"
                        )
                        continue

                # Document doesn't exist - create new one
                # Generate summary with metadata
                user_llm = await get_user_long_context_llm(
                    session, user_id, search_space_id
                )

                if user_llm:
                    document_metadata = {
                        "issue_key": issue_identifier,
                        "issue_title": issue_title,
                        "status": formatted_issue.get("status", "Unknown"),
                        "priority": formatted_issue.get("priority", "Unknown"),
                        "comment_count": comment_count,
                        "document_type": "Jira Issue",
                        "connector_type": "Jira",
                    }
                    (
                        summary_content,
                        summary_embedding,
                    ) = await generate_document_summary(
                        issue_content, user_llm, document_metadata
                    )
                else:
                    # Fallback to simple summary if no LLM configured
                    summary_content = f"Jira Issue {issue_identifier}: {issue_title}\n\nStatus: {formatted_issue.get('status', 'Unknown')}\n\n"
                    if formatted_issue.get("description"):
                        summary_content += (
                            f"Description: {formatted_issue.get('description')}\n\n"
                        )
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
                    title=f"Jira - {issue_identifier}: {issue_title}",
                    document_type=DocumentType.JIRA_CONNECTOR,
                    document_metadata={
                        "issue_id": issue_id,
                        "issue_identifier": issue_identifier,
                        "issue_title": issue_title,
                        "state": formatted_issue.get("status", "Unknown"),
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
                        f"Committing batch: {documents_indexed} Jira issues processed so far"
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
        logger.info(f"Final commit: Total {documents_indexed} Jira issues processed")
        await session.commit()
        logger.info("Successfully committed all JIRA document changes to database")

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed JIRA indexing for connector {connector_id}",
            {
                "issues_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "skipped_issues_count": len(skipped_issues),
            },
        )

        logger.info(
            f"JIRA indexing completed: {documents_indexed} new issues, {documents_skipped} skipped"
        )
        return (
            total_processed,
            None,
        )  # Return None as the error message to indicate success

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during JIRA indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index JIRA issues for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index JIRA issues: {e!s}", exc_info=True)
        return 0, f"Failed to index JIRA issues: {e!s}"
