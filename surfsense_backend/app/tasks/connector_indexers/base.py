"""
Base functionality and shared imports for connector indexers.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import (
    Document,
    SearchSourceConnector,
    SearchSourceConnectorType,
)

# Set up logging
logger = logging.getLogger(__name__)


def get_current_timestamp() -> datetime:
    """
    Get the current timestamp with timezone for updated_at field.

    Returns:
        Current datetime with UTC timezone
    """
    return datetime.now(UTC)


def parse_date_flexible(date_str: str) -> datetime:
    """
    Parse date from multiple common formats.

    Args:
        date_str: Date string to parse

    Returns:
        Parsed datetime object

    Raises:
        ValueError: If unable to parse the date string
    """
    formats = ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.rstrip("Z"), fmt)
        except ValueError:
            continue

    # Try ISO format as fallback
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"Unable to parse date: {date_str}")


async def check_duplicate_document_by_hash(
    session: AsyncSession, content_hash: str
) -> Document | None:
    """
    Check if a document with the given content hash already exists.

    Args:
        session: Database session
        content_hash: Hash of the document content

    Returns:
        Existing document if found, None otherwise
    """
    existing_doc_result = await session.execute(
        select(Document).where(Document.content_hash == content_hash)
    )
    return existing_doc_result.scalars().first()


async def check_document_by_unique_identifier(
    session: AsyncSession, unique_identifier_hash: str
) -> Document | None:
    """
    Check if a document with the given unique identifier hash already exists.
    Eagerly loads chunks to avoid lazy loading issues during updates.

    Args:
        session: Database session
        unique_identifier_hash: Hash of the unique identifier from the source system

    Returns:
        Existing document if found, None otherwise
    """
    from sqlalchemy.orm import selectinload

    existing_doc_result = await session.execute(
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.unique_identifier_hash == unique_identifier_hash)
    )
    return existing_doc_result.scalars().first()


async def get_connector_by_id(
    session: AsyncSession, connector_id: int, connector_type: SearchSourceConnectorType
) -> SearchSourceConnector | None:
    """
    Get a connector by ID and type from the database.

    Args:
        session: Database session
        connector_id: ID of the connector
        connector_type: Expected type of the connector

    Returns:
        Connector object if found, None otherwise
    """
    result = await session.execute(
        select(SearchSourceConnector).filter(
            SearchSourceConnector.id == connector_id,
            SearchSourceConnector.connector_type == connector_type,
        )
    )
    return result.scalars().first()


def calculate_date_range(
    connector: SearchSourceConnector,
    start_date: str | None = None,
    end_date: str | None = None,
    default_days_back: int = 365,
) -> tuple[str, str]:
    """
    Calculate date range for indexing based on provided dates or connector's last indexed date.

    Args:
        connector: The connector object
        start_date: Optional start date string (YYYY-MM-DD)
        end_date: Optional end date string (YYYY-MM-DD)
        default_days_back: Default number of days to go back if no last indexed date

    Returns:
        Tuple of (start_date_str, end_date_str)
    """
    # Normalize "undefined" strings to None (from frontend)
    # This prevents parsing errors and ensures consistent behavior across all indexers
    if start_date == "undefined" or start_date == "":
        start_date = None
    if end_date == "undefined" or end_date == "":
        end_date = None

    if start_date is not None and end_date is not None:
        return start_date, end_date

    # Fall back to calculating dates based on last_indexed_at
    calculated_end_date = datetime.now()

    # Use last_indexed_at as start date if available, otherwise use default_days_back
    if connector.last_indexed_at:
        # Convert dates to be comparable (both timezone-naive)
        last_indexed_naive = (
            connector.last_indexed_at.replace(tzinfo=None)
            if connector.last_indexed_at.tzinfo
            else connector.last_indexed_at
        )

        # Check if last_indexed_at is in the future or after end_date
        if last_indexed_naive > calculated_end_date:
            logger.warning(
                f"Last indexed date ({last_indexed_naive.strftime('%Y-%m-%d')}) is in the future. Using {default_days_back} days ago instead."
            )
            calculated_start_date = calculated_end_date - timedelta(
                days=default_days_back
            )
        else:
            calculated_start_date = last_indexed_naive
            logger.info(
                f"Using last_indexed_at ({calculated_start_date.strftime('%Y-%m-%d')}) as start date"
            )
    else:
        calculated_start_date = calculated_end_date - timedelta(days=default_days_back)
        logger.info(
            f"No last_indexed_at found, using {calculated_start_date.strftime('%Y-%m-%d')} ({default_days_back} days ago) as start date"
        )

    # Use calculated dates if not provided
    start_date_str = (
        start_date if start_date else calculated_start_date.strftime("%Y-%m-%d")
    )
    end_date_str = end_date if end_date else calculated_end_date.strftime("%Y-%m-%d")

    # FIX: Ensure end_date is at least 1 day after start_date to avoid
    # "start_date must be strictly before end_date" errors when dates are the same
    # (e.g., when last_indexed_at is today)
    if start_date_str == end_date_str:
        logger.info(
            f"Start date ({start_date_str}) equals end date ({end_date_str}), "
            "adjusting end date to next day to ensure valid date range"
        )
        # Parse end_date and add 1 day
        try:
            end_dt = parse_date_flexible(end_date_str)
        except ValueError:
            logger.warning(
                f"Could not parse end_date '{end_date_str}', using current date"
            )
            end_dt = datetime.now()
        end_dt = end_dt + timedelta(days=1)
        end_date_str = end_dt.strftime("%Y-%m-%d")
        logger.info(f"Adjusted end date to {end_date_str}")

    return start_date_str, end_date_str


async def update_connector_last_indexed(
    session: AsyncSession,
    connector: SearchSourceConnector,
    update_last_indexed: bool = True,
) -> None:
    """
    Update the last_indexed_at timestamp for a connector.

    Args:
        session: Database session
        connector: The connector object
        update_last_indexed: Whether to actually update the timestamp
    """
    if update_last_indexed:
        connector.last_indexed_at = datetime.now()
        logger.info(f"Updated last_indexed_at to {connector.last_indexed_at}")


def build_document_metadata_string(
    metadata_sections: list[tuple[str, list[str]]],
) -> str:
    """
    Build a document string from metadata sections.

    Args:
        metadata_sections: List of (section_title, section_content) tuples

    Returns:
        Combined document string
    """
    document_parts = ["<DOCUMENT>"]

    for section_title, section_content in metadata_sections:
        document_parts.append(f"<{section_title}>")
        document_parts.extend(section_content)
        document_parts.append(f"</{section_title}>")

    document_parts.append("</DOCUMENT>")
    return "\n".join(document_parts)


def build_document_metadata_markdown(
    metadata_sections: list[tuple[str, list[str]]],
) -> str:
    """
    Build a markdown document string from metadata sections.

    Args:
        metadata_sections: List of (section_title, section_content) tuples

    Returns:
        Combined markdown document string
    """
    document_parts = []

    for section_title, section_content in metadata_sections:
        # Convert section title to proper markdown header
        document_parts.append(f"## {section_title.title()}")
        document_parts.append("")  # Empty line after header

        for content_line in section_content:
            # Handle special content formatting
            if content_line == "TEXT_START" or content_line == "TEXT_END":
                continue  # Skip text delimiters in markdown
            elif content_line.startswith("FORMAT: "):
                # Skip format indicators in markdown
                continue
            else:
                document_parts.append(content_line)

        document_parts.append("")  # Empty line after section

    # Remove trailing empty lines
    while document_parts and document_parts[-1] == "":
        document_parts.pop()

    return "\n".join(document_parts)
