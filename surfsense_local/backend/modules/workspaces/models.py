from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db import Base

if TYPE_CHECKING:
    from modules.chat.models import ChatThread
    from modules.documents.models import Document


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan", passive_deletes=True
    )
    chat_threads: Mapped[list["ChatThread"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan", passive_deletes=True
    )
