import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, text_enum


class ModelRole(enum.StrEnum):
    GENERATION = "generation"


class OnboardingCompletion(Base):
    __tablename__ = "onboarding_completion"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)

    # Presence of this singleton row means model onboarding has finished.
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    completed_at: Mapped[datetime] = mapped_column(server_default=func.now())


class SelectedModel(Base):
    __tablename__ = "selected_models"

    # One row per role, so the role is the key: choosing again updates in place.
    role: Mapped[ModelRole] = mapped_column(text_enum(ModelRole), primary_key=True)
    provider: Mapped[str]
    name: Mapped[str]
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class ProviderCredential(Base):
    __tablename__ = "provider_credentials"

    # One key per provider (BYO); the provider name is the key.
    # ponytail: plaintext — the db is one user's local file. Upgrade path: hold
    # the secret in the OS keyring and keep only a presence flag here.
    provider: Mapped[str] = mapped_column(primary_key=True)
    api_key: Mapped[str]
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
