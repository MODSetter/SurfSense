"""
Airtable connector indexer.
"""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.airtable_connector import AirtableConnector
from app.db import Document, DocumentType, SearchSourceConnectorType
from app.routes.airtable_add_connector_route import refresh_airtable_token
from app.schemas.airtable_auth_credentials import AirtableAuthCredentialsBase
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


async def index_airtable_records(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    max_records: int = 2500,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index Airtable records for a given connector.

    Args:
        session: Database session
        connector_id: ID of the Airtable connector
        search_space_id: ID of the search space to store documents in
        user_id: ID of the user
        start_date: Start date for filtering records (YYYY-MM-DD)
        end_date: End date for filtering records (YYYY-MM-DD)
        max_records: Maximum number of records to fetch per table
        update_last_indexed: Whether to update the last_indexed_at timestamp

    Returns:
        Tuple of (number_of_documents_processed, error_message)
    """
    task_logger = TaskLoggingService(session, search_space_id)
    log_entry = await task_logger.log_task_start(
        task_name="airtable_indexing",
        source="connector_indexing_task",
        message=f"Starting Airtable indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
            "max_records": max_records,
        },
    )

    try:
        # Get the connector from the database
        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.AIRTABLE_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return 0, f"Connector with ID {connector_id} not found"

        # Create credentials from connector config
        config_data = connector.config
        try:
            credentials = AirtableAuthCredentialsBase.from_dict(config_data)
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Invalid Airtable credentials in connector {connector_id}",
                str(e),
                {"error_type": "InvalidCredentials"},
            )
            return 0, f"Invalid Airtable credentials: {e!s}"

        # Check if credentials are expired
        if credentials.is_expired:
            await task_logger.log_task_failure(
                log_entry,
                f"Airtable credentials expired for connector {connector_id}",
                "Credentials expired",
                {"error_type": "ExpiredCredentials"},
            )

            connector = await refresh_airtable_token(session, connector)

            # return 0, "Airtable credentials have expired. Please re-authenticate."

        # Calculate date range for indexing
        start_date_str, end_date_str = calculate_date_range(
            connector, start_date, end_date, default_days_back=365
        )

        logger.info(
            f"Starting Airtable indexing for connector {connector_id} "
            f"from {start_date_str} to {end_date_str}"
        )

        # Initialize Airtable connector
        airtable_connector = AirtableConnector(credentials)
        total_processed = 0

        try:
            # Get accessible bases
            logger.info(f"Fetching Airtable bases for connector {connector_id}")
            bases, error = airtable_connector.get_bases()

            if error:
                await task_logger.log_task_failure(
                    log_entry,
                    f"Failed to fetch Airtable bases: {error}",
                    "API Error",
                    {"error_type": "APIError"},
                )
                return 0, f"Failed to fetch Airtable bases: {error}"

            if not bases:
                success_msg = "No Airtable bases found or accessible"
                await task_logger.log_task_success(
                    log_entry, success_msg, {"bases_count": 0}
                )
                return 0, success_msg

            logger.info(f"Found {len(bases)} Airtable bases to process")

            # Process each base
            for base in bases:
                base_id = base.get("id")
                base_name = base.get("name", "Unknown Base")

                if not base_id:
                    logger.warning(f"Skipping base without ID: {base}")
                    continue

                logger.info(f"Processing base: {base_name} ({base_id})")

                # Get base schema to find tables
                schema_data, schema_error = airtable_connector.get_base_schema(base_id)

                if schema_error:
                    logger.warning(
                        f"Failed to get schema for base {base_id}: {schema_error}"
                    )
                    continue

                if not schema_data or "tables" not in schema_data:
                    logger.warning(f"No tables found in base {base_id}")
                    continue

                tables = schema_data["tables"]
                logger.info(f"Found {len(tables)} tables in base {base_name}")

                # Process each table
                for table in tables:
                    table_id = table.get("id")
                    table_name = table.get("name", "Unknown Table")

                    if not table_id:
                        logger.warning(f"Skipping table without ID: {table}")
                        continue

                    logger.info(f"Processing table: {table_name} ({table_id})")

                    # Fetch records
                    if start_date_str and end_date_str:
                        # Use date filtering if available
                        records, records_error = (
                            airtable_connector.get_records_by_date_range(
                                base_id=base_id,
                                table_id=table_id,
                                date_field="CREATED_TIME()",
                                start_date=start_date_str,
                                end_date=end_date_str,
                                max_records=max_records,
                            )
                        )

                    else:
                        # Fetch all records
                        records, records_error = airtable_connector.get_all_records(
                            base_id=base_id,
                            table_id=table_id,
                            max_records=max_records,
                        )

                    if records_error:
                        logger.warning(
                            f"Failed to fetch records from table {table_name}: {records_error}"
                        )
                        continue

                    if not records:
                        logger.info(f"No records found in table {table_name}")
                        continue

                    logger.info(f"Found {len(records)} records in table {table_name}")

                    documents_indexed = 0
                    skipped_messages = []
                    documents_skipped = 0
                    # Process each record
                    for record in records:
                        try:
                            # Generate markdown content
                            markdown_content = (
                                airtable_connector.format_record_to_markdown(
                                    record, f"{base_name} - {table_name}"
                                )
                            )

                            if not markdown_content.strip():
                                logger.warning(
                                    f"Skipping message with no content: {record.get('id')}"
                                )
                                skipped_messages.append(
                                    f"{record.get('id')} (no content)"
                                )
                                documents_skipped += 1
                                continue

                            record_id = record.get("id", "Unknown")

                            # Generate unique identifier hash for this Airtable record
                            unique_identifier_hash = generate_unique_identifier_hash(
                                DocumentType.AIRTABLE_CONNECTOR,
                                record_id,
                                search_space_id,
                            )

                            # Generate content hash
                            content_hash = generate_content_hash(
                                markdown_content, search_space_id
                            )

                            # Check if document with this unique identifier already exists
                            existing_document = (
                                await check_document_by_unique_identifier(
                                    session, unique_identifier_hash
                                )
                            )

                            if existing_document:
                                # Document exists - check if content has changed
                                if existing_document.content_hash == content_hash:
                                    logger.info(
                                        f"Document for Airtable record {record_id} unchanged. Skipping."
                                    )
                                    documents_skipped += 1
                                    continue
                                else:
                                    # Content has changed - update the existing document
                                    logger.info(
                                        f"Content changed for Airtable record {record_id}. Updating document."
                                    )

                                    # Generate document summary
                                    user_llm = await get_user_long_context_llm(
                                        session, user_id, search_space_id
                                    )

                                    if user_llm:
                                        document_metadata = {
                                            "record_id": record_id,
                                            "created_time": record.get(
                                                "CREATED_TIME()", ""
                                            ),
                                            "document_type": "Airtable Record",
                                            "connector_type": "Airtable",
                                        }
                                        (
                                            summary_content,
                                            summary_embedding,
                                        ) = await generate_document_summary(
                                            markdown_content,
                                            user_llm,
                                            document_metadata,
                                        )
                                    else:
                                        summary_content = (
                                            f"Airtable Record: {record_id}\n\n"
                                        )
                                        summary_embedding = (
                                            config.embedding_model_instance.embed(
                                                summary_content
                                            )
                                        )

                                    # Process chunks
                                    chunks = await create_document_chunks(
                                        markdown_content
                                    )

                                    # Update existing document
                                    existing_document.title = (
                                        f"Airtable Record: {record_id}"
                                    )
                                    existing_document.content = summary_content
                                    existing_document.content_hash = content_hash
                                    existing_document.embedding = summary_embedding
                                    existing_document.document_metadata = {
                                        "record_id": record_id,
                                        "created_time": record.get(
                                            "CREATED_TIME()", ""
                                        ),
                                    }
                                    existing_document.chunks = chunks

                                    documents_indexed += 1
                                    logger.info(
                                        f"Successfully updated Airtable record {record_id}"
                                    )
                                    continue

                            # Document doesn't exist - create new one
                            # Generate document summary
                            user_llm = await get_user_long_context_llm(
                                session, user_id, search_space_id
                            )

                            if user_llm:
                                document_metadata = {
                                    "record_id": record_id,
                                    "created_time": record.get("CREATED_TIME()", ""),
                                    "document_type": "Airtable Record",
                                    "connector_type": "Airtable",
                                }
                                (
                                    summary_content,
                                    summary_embedding,
                                ) = await generate_document_summary(
                                    markdown_content, user_llm, document_metadata
                                )
                            else:
                                # Fallback to simple summary if no LLM configured
                                summary_content = f"Airtable Record: {record_id}\n\n"
                                summary_embedding = (
                                    config.embedding_model_instance.embed(
                                        summary_content
                                    )
                                )

                            # Process chunks
                            chunks = await create_document_chunks(markdown_content)

                            # Create and store new document
                            logger.info(
                                f"Creating new document for Airtable record: {record_id}"
                            )
                            document = Document(
                                search_space_id=search_space_id,
                                title=f"Airtable Record: {record_id}",
                                document_type=DocumentType.AIRTABLE_CONNECTOR,
                                document_metadata={
                                    "record_id": record_id,
                                    "created_time": record.get("CREATED_TIME()", ""),
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
                                f"Successfully indexed new Airtable record {summary_content}"
                            )

                            # Batch commit every 10 documents
                            if documents_indexed % 10 == 0:
                                logger.info(
                                    f"Committing batch: {documents_indexed} Airtable records processed so far"
                                )
                                await session.commit()

                        except Exception as e:
                            logger.error(
                                f"Error processing the Airtable record {record.get('id', 'Unknown')}: {e!s}",
                                exc_info=True,
                            )
                            skipped_messages.append(
                                f"{record.get('id', 'Unknown')} (processing error)"
                            )
                            documents_skipped += 1
                            continue  # Skip this message and continue with others

                    # Update the last_indexed_at timestamp for the connector only if requested
                    total_processed = documents_indexed
                    if total_processed > 0:
                        await update_connector_last_indexed(
                            session, connector, update_last_indexed
                        )

                    # Final commit for any remaining documents not yet committed in batches
                    logger.info(
                        f"Final commit: Total {documents_indexed} Airtable records processed"
                    )
                    await session.commit()
                    logger.info(
                        "Successfully committed all Airtable document changes to database"
                    )

                    # Log success
                    await task_logger.log_task_success(
                        log_entry,
                        f"Successfully completed Airtable indexing for connector {connector_id}",
                        {
                            "events_processed": total_processed,
                            "documents_indexed": documents_indexed,
                            "documents_skipped": documents_skipped,
                            "skipped_messages_count": len(skipped_messages),
                        },
                    )

                    logger.info(
                        f"Airtable indexing completed: {documents_indexed} new records, {documents_skipped} skipped"
                    )
                    return (
                        total_processed,
                        None,
                    )  # Return None as the error message to indicate success

        except Exception as e:
            logger.error(
                f"Fetching Airtable bases for connector {connector_id} failed: {e!s}",
                exc_info=True,
            )

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Airtable indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(
            f"Database error during Airtable indexing: {db_error!s}", exc_info=True
        )
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Airtable records for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Error during Airtable indexing: {e!s}", exc_info=True)
        return 0, f"Failed to index Airtable records: {e!s}"
