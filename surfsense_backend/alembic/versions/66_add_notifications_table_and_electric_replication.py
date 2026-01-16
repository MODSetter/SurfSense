"""Add notifications table and Electric SQL replication

Revision ID: 66
Revises: 65

Creates notifications table and sets up Electric SQL replication
(user, publication, REPLICA IDENTITY FULL) for notifications,
search_source_connectors, and documents tables.

NOTE: Electric SQL user creation is idempotent (uses IF NOT EXISTS).
- Docker deployments: user is pre-created by scripts/docker/init-electric-user.sh
- Local PostgreSQL: user is created here during migration
Both approaches are safe to run together without conflicts as this migraiton is idempotent
"""

from collections.abc import Sequence

from alembic import context, op

# Get Electric SQL user credentials from env.py configuration
_config = context.config
ELECTRIC_DB_USER = _config.get_main_option("electric_db_user", "electric")
ELECTRIC_DB_PASSWORD = _config.get_main_option(
    "electric_db_password", "electric_password"
)

# revision identifiers, used by Alembic.
revision: str = "66"
down_revision: str | None = "65"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - add notifications table and Electric SQL replication."""
    # Create notifications table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            search_space_id INTEGER REFERENCES searchspaces(id) ON DELETE CASCADE,
            type VARCHAR(50) NOT NULL,
            title VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            read BOOLEAN NOT NULL DEFAULT FALSE,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ
        );
        """
    )

    # Create indexes (using IF NOT EXISTS for idempotency)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications (user_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_notifications_read ON notifications (read);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications (created_at);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_notifications_user_read ON notifications (user_id, read);"
    )

    # =====================================================
    # Electric SQL Setup - User and Publication
    # =====================================================

    # Create Electric SQL replication user if not exists
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '{ELECTRIC_DB_USER}') THEN
                CREATE USER {ELECTRIC_DB_USER} WITH REPLICATION PASSWORD '{ELECTRIC_DB_PASSWORD}';
            END IF;
        END
        $$;
        """
    )

    # Grant necessary permissions to electric user
    op.execute(
        f"""
        DO $$
        DECLARE
            db_name TEXT := current_database();
        BEGIN
            EXECUTE format('GRANT CONNECT ON DATABASE %I TO {ELECTRIC_DB_USER}', db_name);
        END
        $$;
        """
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {ELECTRIC_DB_USER};")
    op.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {ELECTRIC_DB_USER};")
    op.execute(f"GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO {ELECTRIC_DB_USER};")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {ELECTRIC_DB_USER};"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO {ELECTRIC_DB_USER};"
    )

    # Create the publication if not exists
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_publication WHERE pubname = 'electric_publication_default') THEN
                CREATE PUBLICATION electric_publication_default;
            END IF;
        END
        $$;
        """
    )

    # =====================================================
    # Electric SQL Setup - Table Configuration
    # =====================================================

    # Set REPLICA IDENTITY FULL (required by Electric SQL for replication)
    op.execute("ALTER TABLE notifications REPLICA IDENTITY FULL;")
    op.execute("ALTER TABLE search_source_connectors REPLICA IDENTITY FULL;")
    op.execute("ALTER TABLE documents REPLICA IDENTITY FULL;")

    # Add tables to Electric SQL publication for replication
    op.execute(
        """
        DO $$
        BEGIN
            -- Add notifications if not already added
            IF NOT EXISTS (
                SELECT 1 FROM pg_publication_tables 
                WHERE pubname = 'electric_publication_default' 
                AND tablename = 'notifications'
            ) THEN
                ALTER PUBLICATION electric_publication_default ADD TABLE notifications;
            END IF;
            
            -- Add search_source_connectors if not already added
            IF NOT EXISTS (
                SELECT 1 FROM pg_publication_tables 
                WHERE pubname = 'electric_publication_default' 
                AND tablename = 'search_source_connectors'
            ) THEN
                ALTER PUBLICATION electric_publication_default ADD TABLE search_source_connectors;
            END IF;
            
            -- Add documents if not already added
            IF NOT EXISTS (
                SELECT 1 FROM pg_publication_tables 
                WHERE pubname = 'electric_publication_default' 
                AND tablename = 'documents'
            ) THEN
                ALTER PUBLICATION electric_publication_default ADD TABLE documents;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Downgrade schema - remove notifications table."""
    op.drop_index("ix_notifications_user_read", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_read", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
