"""Add notifications table and Electric SQL replication

Revision ID: 62
Revises: 61

Creates notifications table and sets up Electric SQL replication
(user, publication, REPLICA IDENTITY FULL) for notifications,
search_source_connectors, and documents tables.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "62"
down_revision: str | None = "61"
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

    # Create indexes
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_read", "notifications", ["read"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "read"])

    # =====================================================
    # Electric SQL Setup - User and Publication
    # =====================================================
    
    # Create Electric SQL replication user if not exists
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'electric') THEN
                CREATE USER electric WITH REPLICATION PASSWORD 'electric_password';
            END IF;
        END
        $$;
        """
    )
    
    # Grant necessary permissions to electric user
    op.execute(
        """
        DO $$
        DECLARE
            db_name TEXT := current_database();
        BEGIN
            EXECUTE format('GRANT CONNECT ON DATABASE %I TO electric', db_name);
        END
        $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO electric;")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO electric;")
    op.execute("GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO electric;")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO electric;")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO electric;")
    
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
