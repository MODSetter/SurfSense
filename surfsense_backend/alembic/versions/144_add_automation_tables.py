"""Add automation tables (automations, automation_triggers, automation_runs)

Revision ID: 144
Revises: 143
Create Date: 2026-05-26

Adds the three tables that back the v1 automation engine, plus the
three PostgreSQL ENUM types they reference. Matches the SQLAlchemy
models under ``app.automations.persistence.models`` and the v1 data
model in ``automation-design-plan.md`` §9.

v1 ships these three tables only. ``domain_events`` is deferred to
Phase 3 with the event trigger; ``mcp_connections`` / ``mcp_tools``
are deferred to Phase 4 with the MCP integration.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "144"
down_revision: str | None = "143"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Guard every object so the migration is safe to re-run after a partial
    # apply (the types/tables outlive a failed run that never advanced
    # alembic_version). Types must precede the tables that reference them.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'automation_status'
            ) THEN
                CREATE TYPE automation_status AS ENUM (
                    'active', 'paused', 'archived'
                );
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'automation_trigger_type'
            ) THEN
                CREATE TYPE automation_trigger_type AS ENUM (
                    'schedule', 'manual'
                );
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'automation_run_status'
            ) THEN
                CREATE TYPE automation_run_status AS ENUM (
                    'pending', 'running', 'succeeded', 'failed',
                    'cancelled', 'timed_out'
                );
            END IF;
        END
        $$;
        """
    )

    # automations — the editable, versioned automation definition
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS automations (
            id SERIAL PRIMARY KEY,
            search_space_id INTEGER NOT NULL
                REFERENCES searchspaces(id) ON DELETE CASCADE,
            created_by_user_id UUID
                REFERENCES "user"(id) ON DELETE SET NULL,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            status automation_status NOT NULL DEFAULT 'active',
            definition JSONB NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_automations_search_space_id ON automations(search_space_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_automations_created_by_user_id ON automations(created_by_user_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_automations_status ON automations(status);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_automations_created_at ON automations(created_at);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_automations_updated_at ON automations(updated_at);"
    )

    # automation_triggers — one row per (automation, trigger-instance) pair
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS automation_triggers (
            id SERIAL PRIMARY KEY,
            automation_id INTEGER NOT NULL
                REFERENCES automations(id) ON DELETE CASCADE,
            type automation_trigger_type NOT NULL,
            params JSONB NOT NULL,
            static_inputs JSONB NOT NULL DEFAULT '{}'::jsonb,
            enabled BOOLEAN NOT NULL DEFAULT true,
            last_fired_at TIMESTAMP WITH TIME ZONE,
            next_fire_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_automation_triggers_automation_id ON automation_triggers(automation_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_automation_triggers_type ON automation_triggers(type);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_automation_triggers_enabled ON automation_triggers(enabled);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_automation_triggers_created_at ON automation_triggers(created_at);"
    )
    # Partial index for the schedule tick: only enabled schedule triggers
    # with a scheduled next fire are ever scanned for due rows.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_automation_triggers_due
            ON automation_triggers (next_fire_at)
            WHERE enabled = true
              AND type = 'schedule'
              AND next_fire_at IS NOT NULL;
        """
    )

    # automation_runs — the immutable per-fire execution record
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS automation_runs (
            id SERIAL PRIMARY KEY,
            automation_id INTEGER NOT NULL
                REFERENCES automations(id) ON DELETE CASCADE,
            trigger_id INTEGER
                REFERENCES automation_triggers(id) ON DELETE SET NULL,
            status automation_run_status NOT NULL DEFAULT 'pending',
            definition_snapshot JSONB NOT NULL,
            inputs JSONB NOT NULL DEFAULT '{}'::jsonb,
            step_results JSONB NOT NULL DEFAULT '[]'::jsonb,
            output JSONB,
            artifacts JSONB NOT NULL DEFAULT '[]'::jsonb,
            error JSONB,
            started_at TIMESTAMP WITH TIME ZONE,
            finished_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_automation_runs_automation_id ON automation_runs(automation_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_automation_runs_trigger_id ON automation_runs(trigger_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_automation_runs_status ON automation_runs(status);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_automation_runs_created_at ON automation_runs(created_at);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_automation_runs_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_automation_runs_status;")
    op.execute("DROP INDEX IF EXISTS ix_automation_runs_trigger_id;")
    op.execute("DROP INDEX IF EXISTS ix_automation_runs_automation_id;")
    op.execute("DROP TABLE IF EXISTS automation_runs;")

    op.execute("DROP INDEX IF EXISTS ix_automation_triggers_due;")
    op.execute("DROP INDEX IF EXISTS ix_automation_triggers_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_automation_triggers_enabled;")
    op.execute("DROP INDEX IF EXISTS ix_automation_triggers_type;")
    op.execute("DROP INDEX IF EXISTS ix_automation_triggers_automation_id;")
    op.execute("DROP TABLE IF EXISTS automation_triggers;")

    op.execute("DROP INDEX IF EXISTS ix_automations_updated_at;")
    op.execute("DROP INDEX IF EXISTS ix_automations_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_automations_status;")
    op.execute("DROP INDEX IF EXISTS ix_automations_created_by_user_id;")
    op.execute("DROP INDEX IF EXISTS ix_automations_search_space_id;")
    op.execute("DROP TABLE IF EXISTS automations;")

    op.execute("DROP TYPE IF EXISTS automation_run_status;")
    op.execute("DROP TYPE IF EXISTS automation_trigger_type;")
    op.execute("DROP TYPE IF EXISTS automation_status;")
