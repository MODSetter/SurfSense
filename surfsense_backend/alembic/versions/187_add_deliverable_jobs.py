"""Add generic queued deliverable jobs.

Revision ID: 187
Revises: 186
"""

from collections.abc import Sequence

from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "187"
down_revision: str | None = "186"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Every object below may already exist: the startup bootstrap
    # (Base.metadata.create_all) builds the current model shape, so a dev DB
    # that booted the backend before migrating already has the whole table.
    postgresql.ENUM(
        "queued",
        "running",
        "cancelling",
        "cancelled",
        "ready",
        "failed",
        name="deliverable_job_status",
    ).create(op.get_bind(), checkfirst=True)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS deliverable_jobs (
            id SERIAL PRIMARY KEY,
            kind VARCHAR(64) NOT NULL,
            title VARCHAR(500) NOT NULL,
            workspace_id INTEGER NOT NULL
                REFERENCES workspaces(id) ON DELETE CASCADE,
            thread_id INTEGER
                REFERENCES new_chat_threads(id) ON DELETE SET NULL,
            created_by_id UUID
                REFERENCES "user"(id) ON DELETE SET NULL,
            tool_call_id VARCHAR(255) NOT NULL,
            request JSONB NOT NULL DEFAULT '{}'::jsonb,
            checkpoint JSONB NOT NULL DEFAULT '{}'::jsonb,
            status deliverable_job_status NOT NULL DEFAULT 'queued',
            phase VARCHAR(64),
            progress INTEGER NOT NULL DEFAULT 0,
            artifact_id INTEGER
                REFERENCES artifacts(id) ON DELETE SET NULL,
            celery_task_id VARCHAR(255),
            attempt_count INTEGER NOT NULL DEFAULT 1,
            failure_code VARCHAR(64),
            internal_error VARCHAR(2000),
            cancel_requested_at TIMESTAMP WITH TIME ZONE,
            claimed_at TIMESTAMP WITH TIME ZONE,
            heartbeat_at TIMESTAMP WITH TIME ZONE,
            finished_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_deliverable_jobs_workspace_kind_tool_call
                UNIQUE (workspace_id, kind, tool_call_id),
            CONSTRAINT ck_deliverable_jobs_progress
                CHECK (progress >= 0 AND progress <= 100),
            CONSTRAINT ck_deliverable_jobs_attempt_count
                CHECK (attempt_count >= 1)
        )
        """
    )
    for statement in (
        "CREATE INDEX IF NOT EXISTS ix_deliverable_jobs_workspace_id "
        "ON deliverable_jobs(workspace_id)",
        "CREATE INDEX IF NOT EXISTS ix_deliverable_jobs_thread_id "
        "ON deliverable_jobs(thread_id)",
        "CREATE INDEX IF NOT EXISTS ix_deliverable_jobs_workspace_status "
        "ON deliverable_jobs(workspace_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_deliverable_jobs_created_at "
        "ON deliverable_jobs(created_at)",
        "CREATE INDEX IF NOT EXISTS ix_deliverable_jobs_updated_at "
        "ON deliverable_jobs(updated_at)",
        "CREATE INDEX IF NOT EXISTS ix_deliverable_jobs_outbox "
        "ON deliverable_jobs(updated_at) WHERE status = 'queued'",
        "CREATE INDEX IF NOT EXISTS ix_deliverable_jobs_stale_running "
        "ON deliverable_jobs(heartbeat_at, id) "
        "WHERE status IN ('running', 'cancelling')",
    ):
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS deliverable_jobs")
    op.execute("DROP TYPE IF EXISTS deliverable_job_status")
