import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, text_enum


class IndexState(enum.StrEnum):
    ACTIVE = "active"
    # Written by changing the model, which a later release adds.
    BUILDING = "building"
    RETIRED = "retired"


class EmbeddingIndex(Base):
    """Which model built a set of vectors, and where they are.

    One active row, enforced in code rather than by a singleton constraint: a
    second row is how changing the model starts.
    """

    __tablename__ = "embedding_indexes"

    id: Mapped[int] = mapped_column(primary_key=True)
    spec: Mapped[dict[str, Any]] = mapped_column(JSON)
    vector_table: Mapped[str]
    state: Mapped[IndexState] = mapped_column(text_enum(IndexState))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
