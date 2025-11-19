"""add 2fa columns to user

Revision ID: 40
Revises: 39
Create Date: 2025-11-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "40"
down_revision: Union[str, None] = "39"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 2FA columns to user table
    op.add_column("user", sa.Column("two_fa_enabled", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("user", sa.Column("totp_secret", sa.String(), nullable=True))
    op.add_column("user", sa.Column("backup_codes", postgresql.JSON(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "backup_codes")
    op.drop_column("user", "totp_secret")
    op.drop_column("user", "two_fa_enabled")
