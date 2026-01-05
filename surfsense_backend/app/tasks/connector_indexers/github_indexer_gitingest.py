"""GitHub connector indexer using gitingest."""

from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.github import GitHubConnectorGitingest
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
    get_current_timestamp,
    logger,
)


async def index_github_repos_gitingest(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index GitHub repositories using gitingest for bulk processing.

    Args:
        session: Database session
        connector_id: ID of the GitHub connector
        search_space_id: ID of the search space
        user_id: ID of the user
        start_date: Not used in gitingest mode
        end_date: Not used in gitingest mode
        update_last_indexed: Whether to update last_indexed_at timestamp

    Returns:
        Tuple of (documents_processed, error_message)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    log_entry = await task_logger.log_task_start(
        task_name="github_repos_gitingest_indexing",
        source="connector_indexing_task",
        message=f"Starting GitHub repositories indexing with gitingest for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "mode": "gitingest",
        },
    )

    documents_processed = 0
    errors = []

    try:
        await task_logger.log_task_progress(
            log_entry,
            f"Retrieving GitHub connector {connector_id}",
            {"stage": "connector_retrieval"},
        )

        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.GITHUB_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector {connector_id} not found",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return 0, f"Connector {connector_id} not found"

        github_pat = connector.config.get("GITHUB_PAT")
        repo_full_names = connector.config.get("repo_full_names")

        if not github_pat:
            await task_logger.log_task_failure(
                log_entry,
                "GitHub PAT not found in connector config",
                "Missing GitHub PAT",
                {"error_type": "MissingToken"},
            )
            return 0, "GitHub PAT not found in connector config"

        if not repo_full_names or not isinstance(repo_full_names, list):
            await task_logger.log_task_failure(
                log_entry,
                "'repo_full_names' not found or invalid",
                "Invalid repo configuration",
                {"error_type": "InvalidConfiguration"},
            )
            return 0, "'repo_full_names' not found or is not a list"

        await task_logger.log_task_progress(
            log_entry,
            f"Initializing GitHub gitingest client",
            {"stage": "client_initialization", "repo_count": len(repo_full_names)},
        )

        try:
            github_client = GitHubConnectorGitingest(token=github_pat)
        except ValueError as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to initialize GitHub client",
                str(e),
                {"error_type": "ClientInitializationError"},
            )
            return 0, f"Failed to initialize GitHub client: {e!s}"

        await task_logger.log_task_progress(
            log_entry,
            f"Processing {len(repo_full_names)} repositories with gitingest",
            {"stage": "repo_processing", "repo_count": len(repo_full_names)},
        )

        logger.info(f"Processing {len(repo_full_names)} repositories with gitingest")

        for repo_full_name in repo_full_names:
            if not repo_full_name or not isinstance(repo_full_name, str):
                logger.warning(f"Skipping invalid repository entry: {repo_full_name}")
                continue

            logger.info(f"Processing repository: {repo_full_name}")

            try:
                result = github_client.process_repository(repo_full_name)

                content = result["content"]
                tree = result.get("tree", "")
                summary = result.get("summary", "")
                metadata = result["metadata"]

                if not content:
                    logger.warning(f"No content extracted for {repo_full_name}")
                    continue

                unique_identifier = f"{repo_full_name}:gitingest"
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.GITHUB_CONNECTOR, unique_identifier, search_space_id
                )

                content_hash = generate_content_hash(content, search_space_id)

                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                if existing_document:
                    if existing_document.content_hash == content_hash:
                        logger.info(
                            f"Repository {repo_full_name} unchanged, skipping"
                        )
                        continue
                    else:
                        logger.info(f"Updating repository {repo_full_name}")

                        user_llm = await get_user_long_context_llm(
                            session, user_id, search_space_id
                        )

                        if user_llm:
                            doc_metadata = {
                                "repository": repo_full_name,
                                "document_type": "GitHub Repository (gitingest)",
                                "connector_type": "GitHub",
                            }
                            summary_content, summary_embedding = (
                                await generate_document_summary(
                                    content, user_llm, doc_metadata
                                )
                            )
                        else:
                            summary_content = (
                                summary
                                or f"GitHub Repository: {repo_full_name}\n\n{content[:1000]}..."
                            )
                            summary_embedding = config.embedding_model_instance.embed(
                                summary_content
                            )

                        chunks_data = await create_document_chunks(content)

                        existing_document.title = f"GitHub - {repo_full_name}"
                        existing_document.content = summary_content
                        existing_document.content_hash = content_hash
                        existing_document.embedding = summary_embedding
                        existing_document.document_metadata = {
                            "repository": repo_full_name,
                            "branch": metadata.get("branch", "main"),
                            "tree_structure": tree[:5000] if tree else "",
                            "indexed_at": datetime.now(UTC).isoformat(),
                            **metadata,
                        }
                        existing_document.chunks = chunks_data
                        existing_document.updated_at = get_current_timestamp()

                        logger.info(f"Updated repository {repo_full_name}")
                        continue

                logger.info(f"Creating new document for {repo_full_name}")

                user_llm = await get_user_long_context_llm(
                    session, user_id, search_space_id
                )

                if user_llm:
                    doc_metadata = {
                        "repository": repo_full_name,
                        "document_type": "GitHub Repository (gitingest)",
                        "connector_type": "GitHub",
                    }
                    summary_content, summary_embedding = (
                        await generate_document_summary(
                            content, user_llm, doc_metadata
                        )
                    )
                else:
                    summary_content = (
                        summary
                        or f"GitHub Repository: {repo_full_name}\n\n{content[:1000]}..."
                    )
                    summary_embedding = config.embedding_model_instance.embed(
                        summary_content
                    )

                chunks_data = await create_document_chunks(content)

                document = Document(
                    title=f"GitHub - {repo_full_name}",
                    document_type=DocumentType.GITHUB_CONNECTOR,
                    document_metadata={
                        "repository": repo_full_name,
                        "branch": metadata.get("branch", "main"),
                        "tree_structure": tree[:5000] if tree else "",
                        "indexed_at": datetime.now(UTC).isoformat(),
                        **metadata,
                    },
                    content=summary_content,
                    content_hash=content_hash,
                    unique_identifier_hash=unique_identifier_hash,
                    embedding=summary_embedding,
                    search_space_id=search_space_id,
                    chunks=chunks_data,
                    updated_at=get_current_timestamp(),
                )

                session.add(document)
                documents_processed += 1

                if documents_processed % 5 == 0:
                    await session.commit()
                    logger.info(f"Committed {documents_processed} repositories")

            except Exception as repo_err:
                logger.error(f"Failed to process {repo_full_name}: {repo_err}")
                errors.append(f"Failed processing {repo_full_name}: {repo_err}")

        await session.commit()
        logger.info(f"Completed: {documents_processed} repositories processed")

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed GitHub gitingest indexing",
            {
                "documents_processed": documents_processed,
                "errors_count": len(errors),
                "repo_count": len(repo_full_names),
            },
        )

    except SQLAlchemyError as db_err:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during indexing",
            str(db_err),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_err}")
        errors.append(f"Database error: {db_err}")
        return documents_processed, "; ".join(errors) if errors else str(db_err)
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Unexpected error during indexing",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Unexpected error: {e}", exc_info=True)
        errors.append(f"Unexpected error: {e}")
        return documents_processed, "; ".join(errors) if errors else str(e)

    error_message = "; ".join(errors) if errors else None
    return documents_processed, error_message

