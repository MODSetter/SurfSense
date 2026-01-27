"""Add user incentive tasks table for earning free pages

Revision ID: 80
Revises: 79

Changes:
1. Create incentive_task_type enum with GITHUB_STAR value
2. Create user_incentive_tasks table to track completed tasks
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "80"
down_revision: str | None = "79"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create incentive tasks infrastructure."""

    # Check if enum already exists (handles partial migration recovery)
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'incentivetasktype'")
    )
    enum_exists = result.fetchone() is not None

    # Create the enum type only if it doesn't exist
    if not enum_exists:
        incentive_task_type_enum = postgresql.ENUM(
            "GITHUB_STAR",
            name="incentivetasktype",
            create_type=False,
        )
        incentive_task_type_enum.create(op.get_bind(), checkfirst=True)

    # Check if table already exists (handles partial migration recovery)
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'user_incentive_tasks'"
        )
    )
    table_exists = result.fetchone() is not None

    if not table_exists:
        # Create the user_incentive_tasks table
        op.create_table(
            "user_incentive_tasks",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column(
                "user_id",
                sa.UUID(as_uuid=True),
                sa.ForeignKey("user.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "task_type",
                postgresql.ENUM(
                    "GITHUB_STAR", name="incentivetasktype", create_type=False
                ),
                nullable=False,
                index=True,
            ),
            sa.Column("pages_awarded", sa.Integer(), nullable=False),
            sa.Column(
                "completed_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
                index=True,
            ),
            sa.UniqueConstraint("user_id", "task_type", name="uq_user_incentive_task"),
        )


def downgrade() -> None:
    """Remove incentive tasks infrastructure."""

    # Drop the table
    op.drop_table("user_incentive_tasks")

    # Drop the enum type
    postgresql.ENUM(name="incentivetasktype").drop(op.get_bind(), checkfirst=True)
