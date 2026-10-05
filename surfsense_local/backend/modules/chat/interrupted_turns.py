from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.chat.models import ChatMessage, MessageRole


def settle_interrupted_turns(session: Session) -> int:
    """Mark the replies the last run of the app left unfinished.

    Called at startup, before anything is served, so every reply without an end
    is one a quit or a crash cut off. Kept with or without text: a reply that
    vanished would take the person's question with it.
    """
    replies = session.scalars(
        select(ChatMessage).where(
            ChatMessage.role == MessageRole.ASSISTANT,
            ChatMessage.completed_at.is_(None),
        )
    ).all()
    now = datetime.now(UTC)
    for reply in replies:
        reply.content = {**reply.content, "ending": {"type": "interrupted"}}
        reply.completed_at = now
    return len(replies)
