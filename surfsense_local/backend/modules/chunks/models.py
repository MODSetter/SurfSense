from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db import Base

if TYPE_CHECKING:
    from modules.documents.models import Document


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        Index("chunks_document_position", "document_id", "position", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE")
    )
    position: Mapped[int]
    content: Mapped[str]
    # Kept so a re-index can rebuild the vector table without re-embedding.
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary)
    start_line: Mapped[int | None]
    end_line: Mapped[int | None]

    document: Mapped["Document"] = relationship(back_populates="chunks")
