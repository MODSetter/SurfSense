from datetime import datetime

from cryptography.fernet import InvalidToken
from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from modules.llm.model_type import ModelType
from modules.llm.profile import Fingerprint, Line, Tier, classify, from_name
from shared.db import Base, text_enum
from shared.secrets import decrypt, encrypt


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
            # A connection is required exactly when the runtime is remote;
            # the local text runtime and the bundled sd-server and audio.cpp
            # all answer on this machine, so none carries a connection.
            "(provider IN ('llamacpp', 'sdcpp', 'audiocpp') AND connection_id IS NULL) OR "
            "(provider = 'openai_compatible' AND connection_id IS NOT NULL)",
            name="provider_connection",
        ),
        CheckConstraint(
            # Each local runtime serves its own types: llama.cpp answers text,
            # sd-server draws, edits and animates, audio.cpp speaks.
            "(provider <> 'llamacpp' OR model_type = 'text_gen') AND "
            "(provider <> 'sdcpp' OR model_type IN ('image_gen', 'image_edit', 'video_gen')) AND "
            "(provider <> 'audiocpp' OR model_type = 'audio_gen')",
            name="local_runtime_type",
        ),
    )

    # One row per type, so the type is the key: choosing again updates in place.
    model_type: Mapped[ModelType] = mapped_column(
        text_enum(ModelType), primary_key=True
    )
    provider: Mapped[str]
    connection_id: Mapped[int | None] = mapped_column(
        ForeignKey("provider_connections.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str]
    # Collected when the model was chosen, so generation needs no network to
    # know how to prompt it. Null on a row chosen before tiering shipped.
    params_b: Mapped[float | None]
    vendor: Mapped[str | None]
    line: Mapped[Line | None] = mapped_column(text_enum(Line))
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    @property
    def fingerprint(self) -> Fingerprint:
        """What was collected when this model was chosen, else what its name says."""
        if self.params_b is None and self.vendor is None and self.line is None:
            return from_name(self.provider, self.name)
        return Fingerprint(
            provider=self.provider,
            name=self.name,
            params_b=self.params_b,
            vendor=self.vendor,
            line=self.line,
        )

    @property
    def tier(self) -> Tier:
        """Which of the three prompts this model gets."""
        return classify(self.fingerprint)


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
    # The manifest provider this reaches, so its models are read from that
    # provider's own entries; `custom` for anything the manifest does not list.
    catalog_provider: Mapped[str] = mapped_column(server_default="custom")
    api_key_ciphertext: Mapped[bytes | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    @property
    def api_key(self) -> str | None:
        if self.api_key_ciphertext is None:
            return None
        try:
            return decrypt(self.api_key_ciphertext)
        except InvalidToken:
            # ponytail: SURFSENSE_LOCAL_SECRET rotated (secret.bin reminted).
            # Drop the unreadable blob so the UI asks for a new key; a 500
            # here takes down model discovery for an otherwise healthy API.
            self.api_key_ciphertext = None
            return None

    @api_key.setter
    def api_key(self, value: str | None) -> None:
        self.api_key_ciphertext = None if value is None else encrypt(value)
