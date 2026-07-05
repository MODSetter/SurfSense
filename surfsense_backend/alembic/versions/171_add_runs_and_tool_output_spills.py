"""Add runs and tool_output_spills tables.

``runs`` backs the user-facing Scraper-API logs and the agent's tool-boundary
truncation (full scraper output stored here, model sees a capped preview + id).
``tool_output_spills`` is the internal scratch store for main-agent context
spills, kept separate so the customer log stays clean.

Revision ID: 171
Revises: 170
"""

from collections.abc import Sequence

from alembic import op

revision: str = "171"
down_revision: str | None = "170"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            user_id UUID REFERENCES "user"(id) ON DELETE CASCADE,
            thread_id VARCHAR(255),
            capability VARCHAR(100) NOT NULL,
            origin VARCHAR(16) NOT NULL,
            status VARCHAR(16) NOT NULL,
            error TEXT,
            input JSONB,
            output_text TEXT,
            item_count INTEGER NOT NULL DEFAULT 0,
            char_count INTEGER NOT NULL DEFAULT 0,
            duration_ms INTEGER,
            cost_micros BIGINT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_runs_workspace_id ON runs (workspace_id)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_runs_user_id ON runs (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_runs_capability ON runs (capability)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_runs_created_at ON runs (created_at)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_runs_workspace_created "
        "ON runs (workspace_id, created_at)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tool_output_spills (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
            thread_id VARCHAR(255),
            tool_name VARCHAR(255),
            content TEXT NOT NULL,
            char_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tool_output_spills_workspace_id "
        "ON tool_output_spills (workspace_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tool_output_spills_created_at "
        "ON tool_output_spills (created_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tool_output_spills")
    op.execute("DROP TABLE IF EXISTS runs")
