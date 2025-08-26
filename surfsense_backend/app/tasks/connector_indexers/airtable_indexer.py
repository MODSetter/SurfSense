"""
Airtable connector indexer.
"""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.airtable_connector import AirtableConnector
from app.db import Document, DocumentType, SearchSourceConnectorType
from app.schemas.airtable_auth_credentials import AirtableAuthCredentialsBase
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_document_summary,
)

from .base import (
    calculate_date_range,
    check_duplicate_document_by_hash,
    get_connector_by_id,
    logger,
    update_connector_last_indexed,
)


async def index_airtable_records(
    session: AsyncSession,
    connector_id: int,
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
        start_date: Start date for filtering records (YYYY-MM-DD)
        end_date: End date for filtering records (YYYY-MM-DD)
        max_records: Maximum number of records to fetch per table
        update_last_indexed: Whether to update the last_indexed_at timestamp

    Returns:
        Tuple of (number_of_documents_processed, error_message)
    """
    task_logger = TaskLoggingService(session)
    log_entry = await task_logger.create_task_log(
        task_name="index_airtable_records",
        task_params={
            "connector_id": connector_id,
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
            return 0, "Airtable credentials have expired. Please re-authenticate."

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
                                date_field="createdTime",
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

                    # Process each record
                    for record in records:
                        try:
                            # Generate markdown content
                            markdown_content = (
                                airtable_connector.format_record_to_markdown(
                                    record, f"{base_name} - {table_name}"
                                )
                            )

                            # Generate content hash
                            content_hash = generate_content_hash(markdown_content)

                            # Check for duplicates
                            existing_doc = await check_duplicate_document_by_hash(
                                session, content_hash
                            )
                            if existing_doc:
                                logger.debug(
                                    f"Skipping duplicate record {record.get('id')}"
                                )
                                continue

                            # Generate document summary
                            llm = get_user_long_context_llm(connector.user_id)
                            summary = await generate_document_summary(
                                markdown_content, llm
                            )

                            # Create document
                            document = Document(
                                title=f"{base_name} - {table_name} - Record {record.get('id', 'Unknown')}",
                                content=markdown_content,
                                content_hash=content_hash,
                                summary=summary,
                                document_type=DocumentType.AIRTABLE_CONNECTOR,
                                source_url=f"https://airtable.com/{base_id}/{table_id}",
                                metadata={
                                    "base_id": base_id,
                                    "base_name": base_name,
                                    "table_id": table_id,
                                    "table_name": table_name,
                                    "record_id": record.get("id"),
                                    "created_time": record.get("createdTime"),
                                    "connector_id": connector_id,
                                },
                                user_id=connector.user_id,
                            )

                            session.add(document)
                            await session.flush()

                            # Create document chunks
                            await create_document_chunks(
                                session, document, markdown_content, llm
                            )

                            total_processed += 1
                            logger.debug(
                                f"Processed record {record.get('id')} from {table_name}"
                            )

                        except Exception as e:
                            logger.error(
                                f"Error processing record {record.get('id')}: {e!s}"
                            )
                            continue

            # Update last indexed timestamp
            if update_last_indexed:
                await update_connector_last_indexed(
                    session, connector, update_last_indexed
                )

            await session.commit()

            success_msg = f"Successfully indexed {total_processed} Airtable records"
            await task_logger.log_task_success(
                log_entry,
                success_msg,
                {
                    "records_processed": total_processed,
                    "bases_count": len(bases),
                    "date_range": f"{start_date_str} to {end_date_str}",
                },
            )

            logger.info(success_msg)
            return total_processed, None

        finally:
            airtable_connector.close()

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
