"""Add access_token column to image_generations

Revision ID: 94
Revises: 93

Adds an indexed access_token column to the image_generations table.
This token is stored per-record so that image serving URLs survive
SECRET_KEY rotation.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "94"
down_revision: str | None = "93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add access_token column (nullable so existing rows are unaffected)
    op.add_column(
        "image_generations",
        sa.Column("access_token", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_image_generations_access_token",
        "image_generations",
        ["access_token"],
    )


def downgrade() -> None:
    op.drop_index("ix_image_generations_access_token", table_name="image_generations")
    op.drop_column("image_generations", "access_token")
