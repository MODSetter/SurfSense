"""Add refresh_tokens table for user session management

Revision ID: 92
Revises: 91

Changes:
1. Create refresh_tokens table with columns:
   - id (primary key)
   - user_id (foreign key to user)
   - token_hash (unique, indexed)
   - expires_at (indexed)
   - is_revoked
   - family_id (indexed, for token rotation tracking)
   - created_at, updated_at (timestamps)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "92"
down_revision: str | None = "91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create refresh_tokens table (idempotent)."""
    # Check if table already exists
    connection = op.get_bind()
    result = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'refresh_tokens')"
        )
    )
    table_exists = result.scalar()

    if not table_exists:
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", UUID(as_uuid=True), nullable=False),
            sa.Column("token_hash", sa.String(256), nullable=False),
            sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("is_revoked", sa.Boolean(), nullable=False, default=False),
            sa.Column("family_id", UUID(as_uuid=True), nullable=False),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["user.id"],
                ondelete="CASCADE",
            ),
        )

    # Create indexes if they don't exist
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens (user_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_refresh_tokens_token_hash ON refresh_tokens (token_hash)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_refresh_tokens_expires_at ON refresh_tokens (expires_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_refresh_tokens_family_id ON refresh_tokens (family_id)"
    )


def downgrade() -> None:
    """Drop refresh_tokens table (idempotent)."""
    op.execute("DROP INDEX IF EXISTS ix_refresh_tokens_family_id")
    op.execute("DROP INDEX IF EXISTS ix_refresh_tokens_expires_at")
    op.execute("DROP INDEX IF EXISTS ix_refresh_tokens_token_hash")
    op.execute("DROP INDEX IF EXISTS ix_refresh_tokens_user_id")
    op.execute("DROP TABLE IF EXISTS refresh_tokens")
