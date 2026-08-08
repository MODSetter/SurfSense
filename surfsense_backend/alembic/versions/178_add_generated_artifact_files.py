"""Add generated artifact files and their display role.

Revision ID: 178
Revises: 177
"""

from collections.abc import Sequence

from alembic import op

revision: str = "178"
down_revision: str | None = "177"
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
