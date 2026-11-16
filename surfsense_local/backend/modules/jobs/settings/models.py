from datetime import datetime

from sqlalchemy import JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class JobSettings(Base):
    """A firm's choices for one job, kept for every run of it: the settings its pack declares,
    by key, and the model that makes the second checks."""

    __tablename__ = "job_settings"

    job: Mapped[str] = mapped_column(primary_key=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    # A text model by provider, name and connection_id; null checks on the answering model.
    checker: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
