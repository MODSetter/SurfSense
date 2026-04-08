"""Clean up Electric SQL artifacts (user, publication, replication slots)

Revision ID: 108
Revises: 107

Removes leftover Electric SQL infrastructure that is no longer needed after
the migration to Rocicorp Zero. Fully idempotent — safe on databases that
never had Electric SQL set up (fresh installs).

Cleaned up:
- Replication slots containing 'electric' (prevents unbounded WAL growth)
- The 'electric_publication_default' publication
- Default privileges, grants, and the 'electric' database user
"""

from collections.abc import Sequence

from alembic import op

revision: str = "108"
down_revision: str | None = "107"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            slot RECORD;
        BEGIN
            -- 1. Drop inactive Electric replication slots (prevents WAL growth)
            FOR slot IN
                SELECT slot_name FROM pg_replication_slots
                WHERE slot_name LIKE '%electric%' AND active = false
            LOOP
                BEGIN
                    PERFORM pg_drop_replication_slot(slot.slot_name);
                EXCEPTION WHEN OTHERS THEN
                    RAISE WARNING 'Could not drop replication slot %: %', slot.slot_name, SQLERRM;
                END;
            END LOOP;

            -- Warn about active Electric slots that cannot be safely dropped
            FOR slot IN
                SELECT slot_name FROM pg_replication_slots
                WHERE slot_name LIKE '%electric%' AND active = true
            LOOP
                RAISE WARNING 'Active Electric replication slot "%" was not dropped — drop it manually to stop WAL growth', slot.slot_name;
            END LOOP;

            -- 2. Drop the Electric publication
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'electric_publication_default') THEN
                    DROP PUBLICATION electric_publication_default;
                END IF;
            EXCEPTION WHEN OTHERS THEN
                RAISE WARNING 'Could not drop publication electric_publication_default: %', SQLERRM;
            END;

            -- 3. Revoke privileges and drop the Electric user
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'electric') THEN
                BEGIN
                    ALTER DEFAULT PRIVILEGES IN SCHEMA public
                        REVOKE SELECT ON TABLES FROM electric;
                    ALTER DEFAULT PRIVILEGES IN SCHEMA public
                        REVOKE SELECT ON SEQUENCES FROM electric;
                EXCEPTION WHEN OTHERS THEN
                    RAISE WARNING 'Could not revoke default privileges from electric: %', SQLERRM;
                END;

                BEGIN
                    REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM electric;
                    REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM electric;
                    REVOKE USAGE ON SCHEMA public FROM electric;
                EXCEPTION WHEN OTHERS THEN
                    RAISE WARNING 'Could not revoke schema privileges from electric: %', SQLERRM;
                END;

                BEGIN
                    EXECUTE format(
                        'REVOKE CONNECT ON DATABASE %I FROM electric',
                        current_database()
                    );
                EXCEPTION WHEN OTHERS THEN
                    RAISE WARNING 'Could not revoke CONNECT from electric: %', SQLERRM;
                END;

                BEGIN
                    REASSIGN OWNED BY electric TO CURRENT_USER;
                    DROP ROLE electric;
                EXCEPTION WHEN OTHERS THEN
                    RAISE WARNING 'Could not drop role electric: %', SQLERRM;
                END;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    pass
