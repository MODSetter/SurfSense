import logging
from typing import Any, Coroutine, Dict, List, Tuple
from sqlalchemy.future import select
from app.connectors.trello_connector import TrelloConnector
from app.db import SearchSourceConnector, Document, DocumentType, async_session_maker
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def index_trello_boards(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
    update_last_indexed: bool = True,
) -> Coroutine[Any, Any, Tuple[int, str | None]]:
    """
    Index Trello boards, lists, and cards into the search space.

    Args:
        session: The database session.
        connector_id: The ID of the Trello connector.
        search_space_id: The ID of the search space.
        user_id: The ID of the user.
        start_date: The start date for indexing.
        end_date: The end date for indexing.
        update_last_indexed: Whether to update the last indexed timestamp.

    Returns:
        A tuple containing the number of documents processed and an error message if any.
    """
    logger.info(f"Starting Trello indexing for connector {connector_id}...")

    result = await session.execute(
        select(SearchSourceConnector).filter(SearchSourceConnector.id == connector_id)
    )
    connector = result.scalars().first()

    if not connector:
        return 0, "Connector not found."

    config = connector.config
    api_key = config.get("TRELLO_API_KEY")
    token = config.get("TRELLO_API_TOKEN")
    board_ids = config.get("board_ids", [])

    if not all([api_key, token, board_ids]):
        return 0, "Invalid Trello connector configuration."

    trello_client = TrelloConnector(api_key=api_key, token=token)
    documents_processed = 0

    for board_id in board_ids:
        logger.info(f"Fetching cards for board {board_id}...")
        cards = trello_client.get_board_data(board_id)

        for card in cards:
            card_details = trello_client.get_card_details(card["id"])
            if not card_details:
                continue

            content = f"Card: {card_details['name']}\n\nDescription: {card_details['desc']}\n\n"
            if card_details.get("comments"):
                content += "Comments:\n"
                for comment in card_details["comments"]:
                    content += f"- {comment}\n"

            document = Document(
                title=card_details["name"],
                content=content,
                document_type=DocumentType.TRELLO_CONNECTOR,
                search_space_id=search_space_id,
                document_metadata={
                    "board_id": board_id,
                    "card_id": card["id"],
                    "url": card_details["url"],
                },
            )
            session.add(document)
            documents_processed += 1

    if documents_processed > 0:
        await session.commit()

    logger.info(f"Trello indexing finished. Processed {documents_processed} documents.")
    return documents_processed, None
