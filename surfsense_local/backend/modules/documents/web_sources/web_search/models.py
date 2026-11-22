from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class WebSearchSettings(Base):
    """One row: the SearXNG server the user chose, or none for SurfSense's."""

    __tablename__ = "web_search_settings"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    searxng_url: Mapped[str | None] = mapped_column(default=None)
