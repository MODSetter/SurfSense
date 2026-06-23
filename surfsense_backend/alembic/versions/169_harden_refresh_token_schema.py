"""harden refresh token schema

Revision ID: 169
Revises: 168
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "169"
down_revision: str | None = "168"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "refresh_tokens",
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "refresh_tokens",
        sa.Column("absolute_expiry", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE refresh_tokens
        SET revoked_at = NOW()
        WHERE is_revoked = TRUE
        """
    )
    op.alter_column(
        "refresh_tokens",
        "token_hash",
        existing_type=sa.String(length=256),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.drop_column("refresh_tokens", "is_revoked")


def downgrade() -> None:
    op.add_column(
        "refresh_tokens",
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.execute(
        """
        UPDATE refresh_tokens
        SET is_revoked = TRUE
        WHERE revoked_at IS NOT NULL
        """
    )
    op.alter_column("refresh_tokens", "is_revoked", server_default=None)
    op.alter_column(
        "refresh_tokens",
        "token_hash",
        existing_type=sa.String(length=64),
        type_=sa.String(length=256),
        existing_nullable=False,
    )
    op.drop_column("refresh_tokens", "absolute_expiry")
    op.drop_column("refresh_tokens", "revoked_at")
