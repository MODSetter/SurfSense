"""
ClickUp connector indexer.
"""

from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.clickup_connector import ClickUpConnector
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
    check_document_by_unique_identifier,
    get_connector_by_id,
    logger,
    update_connector_last_indexed,
)


async def index_clickup_tasks(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index tasks from ClickUp workspace.

    Args:
        session: Database session
        connector_id: ID of the ClickUp connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Start date for filtering tasks (YYYY-MM-DD format)
        end_date: End date for filtering tasks (YYYY-MM-DD format)
        update_last_indexed: Whether to update the last_indexed_at timestamp

    Returns:
        Tuple of (number of indexed tasks, error message if any)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="clickup_tasks_indexing",
        source="connector_indexing_task",
        message=f"Starting ClickUp tasks indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    try:
        # Get connector configuration
        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.CLICKUP_CONNECTOR
        )

        if not connector:
            error_msg = f"ClickUp connector with ID {connector_id} not found"
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not a ClickUp connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return 0, error_msg

        # Extract ClickUp configuration
        clickup_api_token = connector.config.get("CLICKUP_API_TOKEN")

        if not clickup_api_token:
            error_msg = "ClickUp API token not found in connector configuration"
            await task_logger.log_task_failure(
                log_entry,
                f"ClickUp API token not found in connector config for connector {connector_id}",
                "Missing ClickUp token",
                {"error_type": "MissingToken"},
            )
            return 0, error_msg

        await task_logger.log_task_progress(
            log_entry,
            f"Initializing ClickUp client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        clickup_client = ClickUpConnector(api_token=clickup_api_token)

        # Get authorized workspaces
        await task_logger.log_task_progress(
            log_entry,
            "Fetching authorized ClickUp workspaces",
            {"stage": "workspace_fetching"},
        )

        workspaces_response = clickup_client.get_authorized_workspaces()
        workspaces = workspaces_response.get("teams", [])

        if not workspaces:
            error_msg = "No authorized ClickUp workspaces found"
            await task_logger.log_task_failure(
                log_entry,
                f"No authorized ClickUp workspaces found for connector {connector_id}",
                "No workspaces found",
                {"error_type": "NoWorkspacesFound"},
            )
            return 0, error_msg

        documents_indexed = 0
        documents_skipped = 0

        # Iterate workspaces and fetch tasks
        for workspace in workspaces:
            workspace_id = workspace.get("id")
            workspace_name = workspace.get("name", "Unknown Workspace")
            if not workspace_id:
                continue

            await task_logger.log_task_progress(
                log_entry,
                f"Processing workspace: {workspace_name}",
                {"stage": "workspace_processing", "workspace_id": workspace_id},
            )

            # Fetch tasks for date range if provided
            if start_date and end_date:
                tasks, error = clickup_client.get_tasks_in_date_range(
                    workspace_id=workspace_id,
                    start_date=start_date,
                    end_date=end_date,
                    include_closed=True,
                )
                if error:
                    logger.warning(
                        f"Error fetching tasks from workspace {workspace_name}: {error}"
                    )
                    continue
            else:
                tasks = clickup_client.get_workspace_tasks(
                    workspace_id=workspace_id, include_closed=True
                )

            await task_logger.log_task_progress(
                log_entry,
                f"Found {len(tasks)} tasks in workspace {workspace_name}",
                {"stage": "tasks_found", "task_count": len(tasks)},
            )

            for task in tasks:
                try:
                    task_id = task.get("id")
                    task_name = task.get("name", "Untitled Task")
                    task_description = task.get("description", "")
                    task_status = task.get("status", {}).get("status", "Unknown")
                    task_priority = (
                        task.get("priority", {}).get("priority", "Unknown")
                        if task.get("priority")
                        else "None"
                    )
                    task_assignees = task.get("assignees", [])
                    task_due_date = task.get("due_date")
                    task_created = task.get("date_created")
                    task_updated = task.get("date_updated")

                    task_list = task.get("list", {})
                    task_list_name = task_list.get("name", "Unknown List")
                    task_space = task.get("space", {})
                    task_space_name = task_space.get("name", "Unknown Space")

                    # Build task content string
                    content_parts: list[str] = [f"Task: {task_name}"]
                    if task_description:
                        content_parts.append(f"Description: {task_description}")
                    content_parts.extend(
                        [
                            f"Status: {task_status}",
                            f"Priority: {task_priority}",
                            f"List: {task_list_name}",
                            f"Space: {task_space_name}",
                        ]
                    )
                    if task_assignees:
                        assignee_names = [
                            assignee.get("username", "Unknown")
                            for assignee in task_assignees
                        ]
                        content_parts.append(f"Assignees: {', '.join(assignee_names)}")
                    if task_due_date:
                        content_parts.append(f"Due Date: {task_due_date}")

                    task_content = "\n".join(content_parts)
                    if not task_content.strip():
                        logger.warning(f"Skipping task with no content: {task_name}")
                        documents_skipped += 1
                        continue

                    # Generate unique identifier hash for this ClickUp task
                    unique_identifier_hash = generate_unique_identifier_hash(
                        DocumentType.CLICKUP_CONNECTOR, task_id, search_space_id
                    )

                    # Generate content hash
                    content_hash = generate_content_hash(task_content, search_space_id)

                    # Check if document with this unique identifier already exists
                    existing_document = await check_document_by_unique_identifier(
                        session, unique_identifier_hash
                    )

                    if existing_document:
                        # Document exists - check if content has changed
                        if existing_document.content_hash == content_hash:
                            logger.info(
                                f"Document for ClickUp task {task_name} unchanged. Skipping."
                            )
                            documents_skipped += 1
                            continue
                        else:
                            # Content has changed - update the existing document
                            logger.info(
                                f"Content changed for ClickUp task {task_name}. Updating document."
                            )

                            # Generate summary with metadata
                            user_llm = await get_user_long_context_llm(
                                session, user_id, search_space_id
                            )

                            if user_llm:
                                document_metadata = {
                                    "task_id": task_id,
                                    "task_name": task_name,
                                    "task_status": task_status,
                                    "task_priority": task_priority,
                                    "task_list": task_list_name,
                                    "task_space": task_space_name,
                                    "assignees": len(task_assignees),
                                    "document_type": "ClickUp Task",
                                    "connector_type": "ClickUp",
                                }
                                (
                                    summary_content,
                                    summary_embedding,
                                ) = await generate_document_summary(
                                    task_content, user_llm, document_metadata
                                )
                            else:
                                summary_content = task_content
                                summary_embedding = (
                                    config.embedding_model_instance.embed(task_content)
                                )

                            # Process chunks
                            chunks = await create_document_chunks(task_content)

                            # Update existing document
                            existing_document.title = f"Task - {task_name}"
                            existing_document.content = summary_content
                            existing_document.content_hash = content_hash
                            existing_document.embedding = summary_embedding
                            existing_document.document_metadata = {
                                "task_id": task_id,
                                "task_name": task_name,
                                "task_status": task_status,
                                "task_priority": task_priority,
                                "task_assignees": task_assignees,
                                "task_due_date": task_due_date,
                                "task_created": task_created,
                                "task_updated": task_updated,
                                "indexed_at": datetime.now().strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                            }
                            existing_document.chunks = chunks

                            documents_indexed += 1
                            logger.info(
                                f"Successfully updated ClickUp task {task_name}"
                            )
                            continue

                    # Document doesn't exist - create new one
                    # Generate summary with metadata
                    user_llm = await get_user_long_context_llm(
                        session, user_id, search_space_id
                    )

                    if user_llm:
                        document_metadata = {
                            "task_id": task_id,
                            "task_name": task_name,
                            "task_status": task_status,
                            "task_priority": task_priority,
                            "task_list": task_list_name,
                            "task_space": task_space_name,
                            "assignees": len(task_assignees),
                            "document_type": "ClickUp Task",
                            "connector_type": "ClickUp",
                        }
                        (
                            summary_content,
                            summary_embedding,
                        ) = await generate_document_summary(
                            task_content, user_llm, document_metadata
                        )
                    else:
                        # Fallback to simple summary if no LLM configured
                        summary_content = task_content
                        summary_embedding = config.embedding_model_instance.embed(
                            task_content
                        )

                    chunks = await create_document_chunks(task_content)

                    document = Document(
                        search_space_id=search_space_id,
                        title=f"Task - {task_name}",
                        document_type=DocumentType.CLICKUP_CONNECTOR,
                        document_metadata={
                            "task_id": task_id,
                            "task_name": task_name,
                            "task_status": task_status,
                            "task_priority": task_priority,
                            "task_assignees": task_assignees,
                            "task_due_date": task_due_date,
                            "task_created": task_created,
                            "task_updated": task_updated,
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
                    logger.info(f"Successfully indexed new task {task_name}")

                    # Batch commit every 10 documents
                    if documents_indexed % 10 == 0:
                        logger.info(
                            f"Committing batch: {documents_indexed} ClickUp tasks processed so far"
                        )
                        await session.commit()

                except Exception as e:
                    logger.error(
                        f"Error processing task {task.get('name', 'Unknown')}: {e!s}",
                        exc_info=True,
                    )
                    documents_skipped += 1

        total_processed = documents_indexed

        if total_processed > 0:
            await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit for any remaining documents not yet committed in batches
        logger.info(f"Final commit: Total {documents_indexed} ClickUp tasks processed")
        await session.commit()

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed clickup indexing for connector {connector_id}",
            {
                "pages_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
            },
        )

        logger.info(
            f"clickup indexing completed: {documents_indexed} new tasks, {documents_skipped} skipped"
        )
        return total_processed, None

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during ClickUp indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index ClickUp tasks for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index ClickUp tasks: {e!s}", exc_info=True)
        return 0, f"Failed to index ClickUp tasks: {e!s}"
