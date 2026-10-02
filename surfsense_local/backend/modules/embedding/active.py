from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.embedding.models import EmbeddingIndex, IndexState
from modules.embedding.spec import EmbedderSpec


class EmbeddingNotChosenError(Exception):
    """Nothing may be embedded before onboarding fixes the model."""

    def __init__(self) -> None:
        super().__init__("no embedding model has been chosen yet")


@dataclass(frozen=True)
class ActiveIndex:
    id: int
    spec: EmbedderSpec
    vector_table: str


def active_index(session: Session) -> ActiveIndex | None:
    """The index search reads and ingest writes. None before onboarding chooses."""
    row = session.scalars(
        select(EmbeddingIndex).where(EmbeddingIndex.state == IndexState.ACTIVE)
    ).one_or_none()
    if row is None:
        return None
    return ActiveIndex(row.id, EmbedderSpec.model_validate(row.spec), row.vector_table)


def require_active_index(session: Session) -> ActiveIndex:
    index = active_index(session)
    if index is None:
        raise EmbeddingNotChosenError
    return index
