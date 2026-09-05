import enum
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, text_enum


class ModelRole(enum.StrEnum):
    GENERATION = "generation"


class SelectedModel(Base):
    __tablename__ = "selected_models"

    # One row per role, so the role is the key: choosing again updates in place.
    role: Mapped[ModelRole] = mapped_column(text_enum(ModelRole), primary_key=True)
    provider: Mapped[str]
    name: Mapped[str]
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
