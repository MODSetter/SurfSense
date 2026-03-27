"""add quick_ask_actions table

Revision ID: 109
Revises: 108
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "109"
down_revision: str | None = "108"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE quick_ask_action_mode AS ENUM ('transform', 'explore');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = 'quick_ask_actions'")
    )
    if not result.fetchone():
        op.create_table(
            "quick_ask_actions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("search_space_id", sa.Integer(), nullable=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column(
                "mode",
                sa.Enum("transform", "explore", name="quick_ask_action_mode", create_type=False),
                nullable=False,
            ),
            sa.Column("icon", sa.String(50), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["search_space_id"], ["searchspaces.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_quick_ask_actions_user_id", "quick_ask_actions", ["user_id"])
        op.create_index("ix_quick_ask_actions_search_space_id", "quick_ask_actions", ["search_space_id"])


def downgrade() -> None:
    op.drop_table("quick_ask_actions")
    op.execute("DROP TYPE IF EXISTS quick_ask_action_mode")
