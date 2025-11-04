"""
GitHub connector indexer.
"""

from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.github_connector import GitHubConnector
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
)


async def index_github_repos(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index code and documentation files from accessible GitHub repositories.

    Args:
        session: Database session
        connector_id: ID of the GitHub connector
        search_space_id: ID of the search space to store documents in
        user_id: ID of the user
        start_date: Start date for filtering (YYYY-MM-DD format) - Note: GitHub indexing processes all files regardless of dates
        end_date: End date for filtering (YYYY-MM-DD format) - Note: GitHub indexing processes all files regardless of dates
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="github_repos_indexing",
        source="connector_indexing_task",
        message=f"Starting GitHub repositories indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    documents_processed = 0
    errors = []

    try:
        # 1. Get the GitHub connector from the database
        await task_logger.log_task_progress(
            log_entry,
            f"Retrieving GitHub connector {connector_id} from database",
            {"stage": "connector_retrieval"},
        )

        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.GITHUB_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not a GitHub connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return (
                0,
                f"Connector with ID {connector_id} not found or is not a GitHub connector",
            )

        # 2. Get the GitHub PAT and selected repositories from the connector config
        github_pat = connector.config.get("GITHUB_PAT")
        repo_full_names_to_index = connector.config.get("repo_full_names")

        if not github_pat:
            await task_logger.log_task_failure(
                log_entry,
                f"GitHub Personal Access Token (PAT) not found in connector config for connector {connector_id}",
                "Missing GitHub PAT",
                {"error_type": "MissingToken"},
            )
            return 0, "GitHub Personal Access Token (PAT) not found in connector config"

        if not repo_full_names_to_index or not isinstance(
            repo_full_names_to_index, list
        ):
            await task_logger.log_task_failure(
                log_entry,
                f"'repo_full_names' not found or is not a list in connector config for connector {connector_id}",
                "Invalid repo configuration",
                {"error_type": "InvalidConfiguration"},
            )
            return 0, "'repo_full_names' not found or is not a list in connector config"

        # 3. Initialize GitHub connector client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing GitHub client for connector {connector_id}",
            {
                "stage": "client_initialization",
                "repo_count": len(repo_full_names_to_index),
            },
        )

        try:
            github_client = GitHubConnector(token=github_pat)
        except ValueError as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to initialize GitHub client for connector {connector_id}",
                str(e),
                {"error_type": "ClientInitializationError"},
            )
            return 0, f"Failed to initialize GitHub client: {e!s}"

        # 4. Validate selected repositories
        await task_logger.log_task_progress(
            log_entry,
            f"Starting indexing for {len(repo_full_names_to_index)} selected repositories",
            {
                "stage": "repo_processing",
                "repo_count": len(repo_full_names_to_index),
                "start_date": start_date,
                "end_date": end_date,
            },
        )

        logger.info(
            f"Starting indexing for {len(repo_full_names_to_index)} selected repositories."
        )
        if start_date and end_date:
            logger.info(
                f"Date range requested: {start_date} to {end_date} (Note: GitHub indexing processes all files regardless of dates)"
            )

        # 6. Iterate through selected repositories and index files
        for repo_full_name in repo_full_names_to_index:
            if not repo_full_name or not isinstance(repo_full_name, str):
                logger.warning(f"Skipping invalid repository entry: {repo_full_name}")
                continue

            logger.info(f"Processing repository: {repo_full_name}")
            try:
                files_to_index = github_client.get_repository_files(repo_full_name)
                if not files_to_index:
                    logger.info(
                        f"No indexable files found in repository: {repo_full_name}"
                    )
                    continue

                logger.info(
                    f"Found {len(files_to_index)} files to process in {repo_full_name}"
                )

                for file_info in files_to_index:
                    file_path = file_info.get("path")
                    file_url = file_info.get("url")
                    file_sha = file_info.get("sha")
                    file_type = file_info.get("type")  # 'code' or 'doc'
                    full_path_key = f"{repo_full_name}/{file_path}"

                    if not file_path or not file_url or not file_sha:
                        logger.warning(
                            f"Skipping file with missing info in {repo_full_name}: {file_info}"
                        )
                        continue

                    # Get file content
                    file_content = github_client.get_file_content(
                        repo_full_name, file_path
                    )

                    if file_content is None:
                        logger.warning(
                            f"Could not retrieve content for {full_path_key}. Skipping."
                        )
                        continue  # Skip if content fetch failed

                    # Generate unique identifier hash for this GitHub file
                    unique_identifier_hash = generate_unique_identifier_hash(
                        DocumentType.GITHUB_CONNECTOR, file_sha, search_space_id
                    )

                    # Generate content hash
                    content_hash = generate_content_hash(file_content, search_space_id)

                    # Check if document with this unique identifier already exists
                    existing_document = await check_document_by_unique_identifier(
                        session, unique_identifier_hash
                    )

                    if existing_document:
                        # Document exists - check if content has changed
                        if existing_document.content_hash == content_hash:
                            logger.info(
                                f"Document for GitHub file {full_path_key} unchanged. Skipping."
                            )
                            continue
                        else:
                            # Content has changed - update the existing document
                            logger.info(
                                f"Content changed for GitHub file {full_path_key}. Updating document."
                            )

                            # Generate summary with metadata
                            user_llm = await get_user_long_context_llm(
                                session, user_id, search_space_id
                            )
                            if user_llm:
                                file_extension = (
                                    file_path.split(".")[-1]
                                    if "." in file_path
                                    else None
                                )
                                document_metadata = {
                                    "file_path": full_path_key,
                                    "repository": repo_full_name,
                                    "file_type": file_extension or "unknown",
                                    "document_type": "GitHub Repository File",
                                    "connector_type": "GitHub",
                                }
                                (
                                    summary_content,
                                    summary_embedding,
                                ) = await generate_document_summary(
                                    file_content, user_llm, document_metadata
                                )
                            else:
                                summary_content = f"GitHub file: {full_path_key}\n\n{file_content[:1000]}..."
                                summary_embedding = (
                                    config.embedding_model_instance.embed(
                                        summary_content
                                    )
                                )

                            # Chunk the content
                            try:
                                if hasattr(config, "code_chunker_instance"):
                                    chunks_data = [
                                        await create_document_chunks(file_content)
                                    ][0]
                                else:
                                    chunks_data = await create_document_chunks(
                                        file_content
                                    )
                            except Exception as chunk_err:
                                logger.error(
                                    f"Failed to chunk file {full_path_key}: {chunk_err}"
                                )
                                continue

                            # Update existing document
                            existing_document.title = f"GitHub - {full_path_key}"
                            existing_document.content = summary_content
                            existing_document.content_hash = content_hash
                            existing_document.embedding = summary_embedding
                            existing_document.document_metadata = {
                                "file_path": file_path,
                                "file_sha": file_sha,
                                "file_url": file_url,
                                "repository": repo_full_name,
                                "indexed_at": datetime.now(UTC).strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                            }
                            existing_document.chunks = chunks_data

                            logger.info(
                                f"Successfully updated GitHub file {full_path_key}"
                            )
                            continue

                    # Document doesn't exist - create new one
                    # Generate summary with metadata
                    user_llm = await get_user_long_context_llm(
                        session, user_id, search_space_id
                    )
                    if user_llm:
                        # Extract file extension from file path
                        file_extension = (
                            file_path.split(".")[-1] if "." in file_path else None
                        )
                        document_metadata = {
                            "file_path": full_path_key,
                            "repository": repo_full_name,
                            "file_type": file_extension or "unknown",
                            "document_type": "GitHub Repository File",
                            "connector_type": "GitHub",
                        }
                        (
                            summary_content,
                            summary_embedding,
                        ) = await generate_document_summary(
                            file_content, user_llm, document_metadata
                        )
                    else:
                        # Fallback to simple summary if no LLM configured
                        summary_content = (
                            f"GitHub file: {full_path_key}\n\n{file_content[:1000]}..."
                        )
                        summary_embedding = config.embedding_model_instance.embed(
                            summary_content
                        )

                    # Chunk the content
                    try:
                        chunks_data = [await create_document_chunks(file_content)][0]

                        # Use code chunker if available, otherwise regular chunker
                        if hasattr(config, "code_chunker_instance"):
                            chunks_data = [
                                {
                                    "content": chunk.text,
                                    "embedding": config.embedding_model_instance.embed(
                                        chunk.text
                                    ),
                                }
                                for chunk in config.code_chunker_instance.chunk(
                                    file_content
                                )
                            ]
                        else:
                            chunks_data = await create_document_chunks(file_content)

                    except Exception as chunk_err:
                        logger.error(
                            f"Failed to chunk file {full_path_key}: {chunk_err}"
                        )
                        errors.append(
                            f"Chunking failed for {full_path_key}: {chunk_err}"
                        )
                        continue  # Skip this file if chunking fails

                    doc_metadata = {
                        "repository_full_name": repo_full_name,
                        "file_path": file_path,
                        "full_path": full_path_key,  # For easier lookup
                        "url": file_url,
                        "sha": file_sha,
                        "type": file_type,
                        "indexed_at": datetime.now(UTC).isoformat(),
                    }

                    # Create new document
                    logger.info(f"Creating new document for file: {full_path_key}")
                    document = Document(
                        title=f"GitHub - {file_path}",
                        document_type=DocumentType.GITHUB_CONNECTOR,
                        document_metadata=doc_metadata,
                        content=summary_content,  # Store summary
                        content_hash=content_hash,
                        unique_identifier_hash=unique_identifier_hash,
                        embedding=summary_embedding,
                        search_space_id=search_space_id,
                        chunks=chunks_data,  # Associate chunks directly
                    )
                    session.add(document)
                    documents_processed += 1

                    # Batch commit every 10 documents
                    if documents_processed % 10 == 0:
                        logger.info(
                            f"Committing batch: {documents_processed} GitHub files processed so far"
                        )
                        await session.commit()

            except Exception as repo_err:
                logger.error(
                    f"Failed to process repository {repo_full_name}: {repo_err}"
                )
                errors.append(f"Failed processing {repo_full_name}: {repo_err}")

        # Final commit for any remaining documents not yet committed in batches
        logger.info(f"Final commit: Total {documents_processed} GitHub files processed")
        await session.commit()
        logger.info(
            f"Finished GitHub indexing for connector {connector_id}. Processed {documents_processed} files."
        )

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed GitHub indexing for connector {connector_id}",
            {
                "documents_processed": documents_processed,
                "errors_count": len(errors),
                "repo_count": len(repo_full_names_to_index),
            },
        )

    except SQLAlchemyError as db_err:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during GitHub indexing for connector {connector_id}",
            str(db_err),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(
            f"Database error during GitHub indexing for connector {connector_id}: {db_err}"
        )
        errors.append(f"Database error: {db_err}")
        return documents_processed, "; ".join(errors) if errors else str(db_err)
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Unexpected error during GitHub indexing for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(
            f"Unexpected error during GitHub indexing for connector {connector_id}: {e}",
            exc_info=True,
        )
        errors.append(f"Unexpected error: {e}")
        return documents_processed, "; ".join(errors) if errors else str(e)

    error_message = "; ".join(errors) if errors else None
    return documents_processed, error_message
