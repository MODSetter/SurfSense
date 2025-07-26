"""Change podcast_content to podcast_transcript with JSON type

Revision ID: 6
Revises: 5

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSON

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6"
down_revision: str | None = "5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    columns = [col["name"] for col in inspector.get_columns("podcasts")]
    if "podcast_transcript" not in columns:
        op.add_column(
            "podcasts",
            sa.Column("podcast_transcript", JSON, nullable=False, server_default="{}"),
        )

        # Copy data from old column to new column
        op.execute(
            """
            UPDATE podcasts
            SET podcast_transcript = jsonb_build_object('text', podcast_content)
            WHERE podcast_content != ''
        """
        )

    # Drop the old column only if it exists
    if "podcast_content" in columns:
        op.drop_column("podcasts", "podcast_content")


def downgrade() -> None:
    # Add back the original column
    op.add_column(
        "podcasts",
        sa.Column("podcast_content", sa.Text(), nullable=False, server_default=""),
    )

    # Copy data from JSON column back to text column
    # Extract the 'text' field if it exists, otherwise use empty string
    op.execute(
        "UPDATE podcasts SET podcast_content = COALESCE((podcast_transcript->>'text'), '')"
    )

    # Drop the new column
    op.drop_column("podcasts", "podcast_transcript")
