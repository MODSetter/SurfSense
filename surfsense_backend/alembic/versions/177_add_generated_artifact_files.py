"""Add generated artifact files and their display role.

Revision ID: 177
Revises: 176
"""

from collections.abc import Sequence

from alembic import op

revision: str = "177"
down_revision: str | None = "176"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE document_file_kind ADD VALUE IF NOT EXISTS 'GENERATED'")
    op.execute(
        "ALTER TABLE document_files "
        "ADD COLUMN IF NOT EXISTS role VARCHAR(16) NOT NULL DEFAULT 'primary'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE document_files DROP COLUMN IF EXISTS role")
