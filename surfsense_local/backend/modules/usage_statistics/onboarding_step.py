"""The furthest step of getting started this library shows, read from what is in it now."""

from collections.abc import Callable

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from modules.chat.models import ChatMessage, MessageRole
from modules.documents.models import Document, DocumentType
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.providers import llamacpp
from modules.usage_statistics.activity_counts import ActivityCounts

# What the user added, as opposed to what Studio made.
LIBRARY_TYPES = (DocumentType.FILE, DocumentType.NOTE)


def onboarding_step(
    session: Session,
    counts: ActivityCounts | None,
    holds_local_model: Callable[[str], bool],
) -> str:
    """Checked furthest first, so a library that skipped a step still reads as past it."""
    if _answered(session) or (counts is not None and counts.answered):
        return "first_answer"
    if session.scalar(
        select(exists().where(Document.document_type.in_(LIBRARY_TYPES)))
    ):
        return "first_source"
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    if selected is None:
        return "not_started"
    # A connection is ready once chosen; SurfSense's own model once its file is here.
    if selected.provider != llamacpp.PROVIDER or holds_local_model(selected.name):
        return "model_ready"
    return "model_chosen"


def _answered(session: Session) -> bool:
    """A Basic chat reply that ended with text; a failure stores none."""
    return bool(
        session.scalar(
            select(
                exists().where(
                    ChatMessage.role == MessageRole.ASSISTANT,
                    ChatMessage.completed_at.is_not(None),
                    func.coalesce(func.json_extract(ChatMessage.content, "$.text"), "")
                    != "",
                )
            )
        )
    )
