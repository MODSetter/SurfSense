from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class EgressDestination(Base):
    __tablename__ = "egress_destinations"

    # "host:<hostname>": one row per host, built in or discovered from a provider.
    destination: Mapped[str] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=False)
    last_call_at: Mapped[datetime | None]
