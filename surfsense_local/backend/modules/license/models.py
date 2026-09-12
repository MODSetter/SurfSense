from datetime import datetime

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class LicenseState(Base):
    __tablename__ = "license_state"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    # The file as imported; state is re-derived from it on every read.
    certificate: Mapped[str | None]
    imported_at: Mapped[datetime | None]
    # Highest instant ever observed; a clock behind it is not trusted.
    clock_watermark: Mapped[datetime]
