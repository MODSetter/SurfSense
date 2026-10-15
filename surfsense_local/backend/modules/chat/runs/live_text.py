import asyncio
import logging
from collections.abc import Callable

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session, sessionmaker

from modules.chat.models import ChatMessage

logger = logging.getLogger(__name__)

# How much text a crash may lose. One small write per running reply at this
# pace stays far below the write traffic ingest already puts on the file.
SAVE_EVERY_SECONDS = 5.0


async def save_while_running(
    session_factory: sessionmaker[Session],
    message_id: int,
    snapshot: Callable[[], tuple[str, list[dict]] | None],
) -> None:
    """Store the reply's text so far, every few seconds, until cancelled.

    Off the stream's path and in its own session, so a write waiting on the
    lock never holds up a token. A save that fails is skipped: the run's final
    write does not depend on it. `snapshot` gives the text with its citations
    resolved, or None while there is nothing new to store.
    """
    while True:
        await asyncio.sleep(SAVE_EVERY_SECONDS)
        current = snapshot()
        if current is None:
            continue
        try:
            await run_in_threadpool(_store, session_factory, message_id, *current)
        except Exception:
            logger.warning("Could not save reply %s mid-run", message_id, exc_info=True)


def _store(
    session_factory: sessionmaker[Session],
    message_id: int,
    text: str,
    cited: list[dict],
) -> None:
    with session_factory() as session:
        message = session.get(ChatMessage, message_id)
        if message is None or message.completed_at is not None:
            return
        message.content = {**message.content, "text": text, "citations": cited}
        session.commit()
