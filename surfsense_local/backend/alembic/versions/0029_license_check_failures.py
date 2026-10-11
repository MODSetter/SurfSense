"""Let a plugin's last check say why SurfSense's plugin host refused the license.

Revision ID: 0029
Revises: 0028
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0029"
down_revision: str | Sequence[str] | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BEFORE = ("unreachable", "sign_in")
AFTER = (
    *BEFORE,
    "needs_license",
    "license_expired",
    "license_revoked",
    "license_invalid",
)


def _check_failure(*values: str) -> sa.Enum:
    return sa.Enum(
        *values, name="checkfailure", native_enum=False, create_constraint=True
    )


def upgrade() -> None:
    # SQLite widens a check constraint only by rebuilding the table.
    with op.batch_alter_table("installed_plugins") as batch:
        batch.alter_column(
            "check_failure",
            existing_type=_check_failure(*BEFORE),
            type_=_check_failure(*AFTER),
            existing_nullable=True,
        )


def downgrade() -> None:
    op.execute(
        "UPDATE installed_plugins SET check_failure = 'sign_in' "
        "WHERE check_failure NOT IN ('unreachable', 'sign_in')"
    )
    with op.batch_alter_table("installed_plugins") as batch:
        batch.alter_column(
            "check_failure",
            existing_type=_check_failure(*AFTER),
            type_=_check_failure(*BEFORE),
            existing_nullable=True,
        )
