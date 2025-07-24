"""Change podcast_content to podcast_transcript with JSON type

Revision ID: 6
Revises: 5

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6"
down_revision: str | None = "5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the old column and create a new one with the new name and type
    # We need to do this because PostgreSQL doesn't support direct column renames with type changes
    op.add_column(
        "podcasts",
        sa.Column("podcast_transcript", JSON, nullable=False, server_default="{}"),
    )

    # Copy data from old column to new column
    # Convert text to JSON by storing it as a JSON string value
    op.execute(
        "UPDATE podcasts SET podcast_transcript = jsonb_build_object('text', podcast_content) WHERE podcast_content != ''"
    )

    # Drop the old column
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
