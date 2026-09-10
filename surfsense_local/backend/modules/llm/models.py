import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, text_enum


class ModelRole(enum.StrEnum):
    GENERATION = "generation"
    IMAGE_GENERATION = "image_generation"


class OnboardingCompletion(Base):
    __tablename__ = "onboarding_completion"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)

    # Presence of this singleton row means model onboarding has finished.
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    completed_at: Mapped[datetime] = mapped_column(server_default=func.now())


class SelectedModel(Base):
    __tablename__ = "selected_models"
    __table_args__ = (
        CheckConstraint(
            "(provider = 'ollama' AND connection_id IS NULL) OR "
            "(provider = 'openai_compatible' AND connection_id IS NOT NULL)",
            name="provider_connection",
        ),
    )

    # One row per role, so the role is the key: choosing again updates in place.
    role: Mapped[ModelRole] = mapped_column(text_enum(ModelRole), primary_key=True)
    provider: Mapped[str]
    connection_id: Mapped[int | None] = mapped_column(
        ForeignKey("provider_connections.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str]
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class ProviderConnection(Base):
    __tablename__ = "provider_connections"
    __table_args__ = (
        CheckConstraint("provider = 'openai_compatible'", name="provider"),
        UniqueConstraint("label"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(collation="NOCASE"))
    provider: Mapped[str]
    base_url: Mapped[str]
    # ponytail: plaintext is the Phase 5 ceiling; Phase 6 moves this value behind
    # ConnectionSecretStore without changing connection ids or API DTOs.
    api_key: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
