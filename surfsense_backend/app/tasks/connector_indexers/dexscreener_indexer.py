"""
DexScreener connector indexer.
"""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.dexscreener_connector import DexScreenerConnector
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
    check_duplicate_document_by_hash,
    get_connector_by_id,
    get_current_timestamp,
    logger,
    update_connector_last_indexed,
)


async def index_dexscreener_pairs(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index DexScreener trading pairs.

    Args:
        session: Database session
        connector_id: ID of the DexScreener connector
        search_space_id: ID of the search space to store documents in
        user_id: User ID
        start_date: Not used for DexScreener (included for consistency with other indexers)
        end_date: Not used for DexScreener (included for consistency with other indexers)
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="dexscreener_pairs_indexing",
        source="connector_indexing_task",
        message=f"Starting DexScreener pairs indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
        },
    )

    try:
        # Get the connector
        await task_logger.log_task_progress(
            log_entry,
            f"Retrieving DexScreener connector {connector_id} from database",
            {"stage": "connector_retrieval"},
        )

        # Get the connector from the database
        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.DEXSCREENER_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not a DexScreener connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return (
                0,
                f"Connector with ID {connector_id} not found or is not a DexScreener connector",
            )

        # Get the tokens list from the connector config
        tokens = connector.config.get("tokens", [])

        if not tokens:
            await task_logger.log_task_failure(
                log_entry,
                f"No tokens configured for connector {connector_id}",
                "Missing token configuration",
                {"error_type": "MissingConfiguration"},
            )
            return 0, "No tokens configured for connector"

        logger.info(f"Starting DexScreener indexing for connector {connector_id} with {len(tokens)} tokens")

        # Initialize DexScreener client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing DexScreener client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        dexscreener_client = DexScreenerConnector()

        documents_indexed = 0
        documents_skipped = 0
        skipped_pairs = []
        batch_size = 10  # Commit every 10 documents for performance

        # Process each tracked token
        for token_idx, token in enumerate(tokens):
            try:
                chain = token.get("chain")
                address = token.get("address")
                token_name = token.get("name", "")

                if not chain or not address:
                    logger.warning(f"Skipping token with missing chain or address: {token}")
                    continue

                await task_logger.log_task_progress(
                    log_entry,
                    f"Fetching pairs for {token_name or address} on {chain} ({token_idx + 1}/{len(tokens)})",
                    {
                        "stage": "fetching_pairs",
                        "token": token_name or address,
                        "chain": chain,
                        "progress": f"{token_idx + 1}/{len(tokens)}",
                    },
                )

                # Get trading pairs for this token
                pairs, error = await dexscreener_client.get_token_pairs(chain, address)

                if error:
                    logger.warning(f"Error fetching pairs for {chain}/{address}: {error}")
                    skipped_pairs.append(f"{token_name or address} ({error})")
                    continue

                if not pairs:
                    logger.info(f"No pairs found for {chain}/{address}")
                    continue

                logger.info(f"Retrieved {len(pairs)} pairs for {token_name or address} on {chain}")

                # Process each pair
                for pair in pairs:
                    try:
                        pair_address = pair.get("pairAddress")
                        
                        if not pair_address:
                            logger.warning(f"Skipping pair with missing pairAddress")
                            documents_skipped += 1
                            continue

                        # Format pair to markdown
                        pair_markdown = dexscreener_client.format_pair_to_markdown(pair, token_name)
                        
                        if not pair_markdown.strip():
                            logger.warning(f"Skipping pair with no content: {pair_address}")
                            documents_skipped += 1
                            continue

                        # Extract pair metadata
                        base_token = pair.get("baseToken", {})
                        quote_token = pair.get("quoteToken", {})
                        base_symbol = base_token.get("symbol", "Unknown")
                        quote_symbol = quote_token.get("symbol", "Unknown")
                        dex_id = pair.get("dexId", "Unknown")
                        price_usd = pair.get("priceUsd", "N/A")
                        liquidity_usd = pair.get("liquidity", {}).get("usd", 0)
                        volume_24h = pair.get("volume", {}).get("h24", 0)
                        price_change_24h = pair.get("priceChange", {}).get("h24", 0)

                        # Generate unique identifier hash for this pair
                        # Use chain + pair_address as unique identifier
                        unique_id = f"{chain}:{pair_address}"
                        unique_identifier_hash = generate_unique_identifier_hash(
                            DocumentType.DEXSCREENER_CONNECTOR, unique_id, search_space_id
                        )

                        # Generate content hash
                        content_hash = generate_content_hash(pair_markdown, search_space_id)

                        # Check if document with this unique identifier already exists
                        existing_document = await check_document_by_unique_identifier(
                            session, unique_identifier_hash
                        )

                        if existing_document:
                            # Document exists - check if content has changed
                            if existing_document.content_hash == content_hash:
                                logger.info(
                                    f"Document for pair {base_symbol}/{quote_symbol} unchanged. Skipping."
                                )
                                documents_skipped += 1
                                continue
                            else:
                                # Content has changed - update the existing document
                                logger.info(
                                    f"Content changed for pair {base_symbol}/{quote_symbol}. Updating document."
                                )

                                # Generate summary with metadata
                                user_llm = await get_user_long_context_llm(
                                    session, user_id, search_space_id
                                )

                                if user_llm:
                                    document_metadata = {
                                        "pair_address": pair_address,
                                        "chain_id": chain,
                                        "dex": dex_id,
                                        "base_symbol": base_symbol,
                                        "quote_symbol": quote_symbol,
                                        "price_usd": price_usd,
                                        "liquidity_usd": liquidity_usd,
                                        "volume_24h": volume_24h,
                                        "price_change_24h": price_change_24h,
                                        "document_type": "DexScreener Trading Pair",
                                        "connector_type": "DexScreener",
                                    }
                                    (
                                        summary_content,
                                        summary_embedding,
                                    ) = await generate_document_summary(
                                        pair_markdown, user_llm, document_metadata
                                    )
                                else:
                                    summary_content = f"DexScreener Pair: {base_symbol}/{quote_symbol}\n\n"
                                    summary_content += f"Chain: {chain}\n"
                                    summary_content += f"DEX: {dex_id}\n"
                                    summary_content += f"Pair Address: {pair_address}\n"
                                    summary_content += f"Price (USD): ${price_usd}\n"
                                    summary_content += f"Liquidity: ${liquidity_usd:,.2f}\n"
                                    summary_content += f"24h Volume: ${volume_24h:,.2f}\n"
                                    summary_content += f"24h Change: {price_change_24h:+.2f}%\n"
                                    summary_embedding = config.embedding_model_instance.embed(
                                        summary_content
                                    )

                                # Process chunks
                                chunks = await create_document_chunks(pair_markdown)

                                # Update existing document
                                existing_document.title = f"DexScreener - {base_symbol}/{quote_symbol} on {chain}"
                                existing_document.content = summary_content
                                existing_document.content_hash = content_hash
                                existing_document.embedding = summary_embedding
                                existing_document.document_metadata = {
                                    "pair_address": pair_address,
                                    "chain_id": chain,
                                    "dex": dex_id,
                                    "base_symbol": base_symbol,
                                    "quote_symbol": quote_symbol,
                                    "price_usd": price_usd,
                                    "liquidity_usd": liquidity_usd,
                                    "volume_24h": volume_24h,
                                    "price_change_24h": price_change_24h,
                                    "token_name": token_name,
                                    "token_address": address,
                                }
                                existing_document.chunks = chunks
                                existing_document.updated_at = get_current_timestamp()

                                documents_indexed += 1
                                logger.info(f"Updated document for pair {base_symbol}/{quote_symbol}")

                        else:
                            # New document - create it
                            logger.info(f"Creating new document for pair {base_symbol}/{quote_symbol}")

                            # Generate summary with metadata
                            user_llm = await get_user_long_context_llm(
                                session, user_id, search_space_id
                            )

                            if user_llm:
                                document_metadata = {
                                    "pair_address": pair_address,
                                    "chain_id": chain,
                                    "dex": dex_id,
                                    "base_symbol": base_symbol,
                                    "quote_symbol": quote_symbol,
                                    "price_usd": price_usd,
                                    "liquidity_usd": liquidity_usd,
                                    "volume_24h": volume_24h,
                                    "price_change_24h": price_change_24h,
                                    "document_type": "DexScreener Trading Pair",
                                    "connector_type": "DexScreener",
                                }
                                (
                                    summary_content,
                                    summary_embedding,
                                ) = await generate_document_summary(
                                    pair_markdown, user_llm, document_metadata
                                )
                            else:
                                summary_content = f"DexScreener Pair: {base_symbol}/{quote_symbol}\n\n"
                                summary_content += f"Chain: {chain}\n"
                                summary_content += f"DEX: {dex_id}\n"
                                summary_content += f"Pair Address: {pair_address}\n"
                                summary_content += f"Price (USD): ${price_usd}\n"
                                summary_content += f"Liquidity: ${liquidity_usd:,.2f}\n"
                                summary_content += f"24h Volume: ${volume_24h:,.2f}\n"
                                summary_content += f"24h Change: {price_change_24h:+.2f}%\n"
                                summary_embedding = config.embedding_model_instance.embed(
                                    summary_content
                                )

                            # Process chunks
                            chunks = await create_document_chunks(pair_markdown)

                            # Create new document
                            new_document = Document(
                                title=f"DexScreener - {base_symbol}/{quote_symbol} on {chain}",
                                content=summary_content,
                                content_hash=content_hash,
                                unique_identifier_hash=unique_identifier_hash,
                                embedding=summary_embedding,
                                document_type=DocumentType.DEXSCREENER_CONNECTOR,
                                document_metadata={
                                    "pair_address": pair_address,
                                    "chain_id": chain,
                                    "dex": dex_id,
                                    "base_symbol": base_symbol,
                                    "quote_symbol": quote_symbol,
                                    "price_usd": price_usd,
                                    "liquidity_usd": liquidity_usd,
                                    "volume_24h": volume_24h,
                                    "price_change_24h": price_change_24h,
                                    "token_name": token_name,
                                    "token_address": address,
                                },
                                chunks=chunks,
                                search_space_id=search_space_id,
                                created_at=get_current_timestamp(),
                                updated_at=get_current_timestamp(),
                            )

                            session.add(new_document)
                            documents_indexed += 1
                            logger.info(f"Created new document for pair {base_symbol}/{quote_symbol}")

                        # Batch commit every N documents
                        if documents_indexed % batch_size == 0:
                            await session.commit()
                            logger.info(f"Committed batch of {batch_size} documents")

                    except Exception as e:
                        logger.error(f"Error processing pair {pair.get('pairAddress', 'unknown')}: {e!s}", exc_info=True)
                        documents_skipped += 1
                        continue

            except Exception as e:
                logger.error(f"Error processing token {token.get('name', token.get('address', 'unknown'))}: {e!s}", exc_info=True)
                continue

        # Final commit for any remaining documents
        if documents_indexed % batch_size != 0:
            await session.commit()
            logger.info(f"Committed final batch of documents")

        # Update last_indexed_at timestamp
        if update_last_indexed:
            await update_connector_last_indexed(session, connector, update_last_indexed)
            await session.commit()
            logger.info(f"Updated last_indexed_at to {connector.last_indexed_at}")

        # Log task completion
        await task_logger.log_task_success(
            log_entry,
            f"Successfully indexed {documents_indexed} DexScreener pairs",
            {
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "tokens_processed": len(tokens),
            },
        )

        logger.info(
            f"DexScreener indexing completed: {documents_indexed} documents indexed, {documents_skipped} skipped"
        )

        return documents_indexed, None

    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Database error during DexScreener indexing: {e!s}", exc_info=True)
        await task_logger.log_task_failure(
            log_entry,
            f"Database error: {e!s}",
            "Database Error",
            {"error_type": "DatabaseError"},
        )
        return 0, f"Database error: {e!s}"

    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error during DexScreener indexing: {e!s}", exc_info=True)
        await task_logger.log_task_failure(
            log_entry,
            f"Unexpected error: {e!s}",
            "Unexpected Error",
            {"error_type": "UnexpectedError"},
        )
        return 0, f"Unexpected error: {e!s}"
