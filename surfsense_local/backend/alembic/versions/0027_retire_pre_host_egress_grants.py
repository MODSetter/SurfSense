"""Retire the egress grants stored under the earlier destination names.

`host:huggingface.co` covers search as well as downloads, so, as in 0012, only
a user who allowed both is carried across. An answer already given for the
host is kept. Downgrading changes nothing: 0026 reads only host names.

Revision ID: 0027
Revises: 0026
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from modules.egress.service import HUGGINGFACE

revision: str = "0027"
down_revision: str | Sequence[str] | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEARCH = "model_search"
DOWNLOADS = ("model_download", "image_model_pull")


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("egress_destinations"):
        return
    rows = dict(
        bind.execute(
            sa.text(
                "SELECT destination, enabled FROM egress_destinations "
                "WHERE destination IN :names"
            ).bindparams(sa.bindparam("names", expanding=True)),
            {"names": [HUGGINGFACE, SEARCH, *DOWNLOADS]},
        ).all()
    )
    allowed_both = rows.get(SEARCH) and any(rows.get(name) for name in DOWNLOADS)
    if allowed_both and HUGGINGFACE not in rows:
        bind.execute(
            sa.text(
                "INSERT INTO egress_destinations(destination, enabled) "
                "VALUES (:destination, 1)"
            ),
            {"destination": HUGGINGFACE},
        )
    bind.execute(
        sa.text(
            "DELETE FROM egress_destinations WHERE destination IN :names"
        ).bindparams(sa.bindparam("names", expanding=True)),
        {"names": [SEARCH, *DOWNLOADS]},
    )


def downgrade() -> None:
    pass
