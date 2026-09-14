from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class EgressDestination(Base):
    __tablename__ = "egress_destinations"

    # "ollama_pull", or "host:<hostname>" for a BYO provider.
    destination: Mapped[str] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=False)
    last_call_at: Mapped[datetime | None]
