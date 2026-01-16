"""Migrate old chats to new_chat_threads and remove old tables

Revision ID: 49
Revises: 48
Create Date: 2025-12-21

This migration:
1. Migrates data from old 'chats' table to 'new_chat_threads' and 'new_chat_messages'
2. Drops the 'chats' table
3. Removes the 'chattype' enum
"""

import json
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "49"
down_revision: str | None = "48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def extract_text_content(content: str | dict | list) -> str:
    """Extract plain text content from various message formats."""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        # Handle dict with 'text' key
        if "text" in content:
            return content["text"]
        return str(content)
    if isinstance(content, list):
        # Handle list of parts (e.g., [{"type": "text", "text": "..."}])
        texts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(part.get("text", ""))
            elif isinstance(part, str):
                texts.append(part)
        return "\n".join(texts) if texts else ""
    return ""


def parse_timestamp(ts, fallback):
    """Parse ISO timestamp string to datetime object."""
    if ts is None:
        return fallback
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, str):
        try:
            # Handle ISO format like '2025-11-26T22:43:34.399Z'
            ts = ts.replace("Z", "+00:00")
            return datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            return fallback
    return fallback


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :table_name)"
        ),
        {"table_name": table_name},
    )
    return result.scalar()


def upgrade() -> None:
    """Migrate old chats to new_chat_threads and remove old tables."""
    # Skip if chats table doesn't exist (fresh database)
    if not table_exists("chats"):
        print("[Migration 49] Chats table does not exist, skipping migration")
        return

    connection = op.get_bind()

    # Get all old chats
    old_chats = connection.execute(
        sa.text("""
            SELECT id, title, messages, search_space_id, created_at
            FROM chats
            ORDER BY created_at ASC
        """)
    ).fetchall()

    print(f"[Migration 49] Found {len(old_chats)} old chats to migrate")

    migrated_count = 0
    for chat_id, title, messages_json, search_space_id, created_at in old_chats:
        try:
            # Parse messages JSON
            if isinstance(messages_json, str):
                messages = json.loads(messages_json)
            else:
                messages = messages_json or []

            # Skip empty chats
            if not messages:
                print(f"[Migration 49] Skipping empty chat {chat_id}")
                continue

            # Create new thread - truncate title to 500 chars (VARCHAR(500) limit)
            thread_title = title or "Migrated Chat"
            if len(thread_title) > 500:
                thread_title = thread_title[:497] + "..."

            result = connection.execute(
                sa.text("""
                    INSERT INTO new_chat_threads 
                    (title, archived, search_space_id, created_at, updated_at)
                    VALUES (:title, FALSE, :search_space_id, :created_at, :created_at)
                    RETURNING id
                """),
                {
                    "title": thread_title,
                    "search_space_id": search_space_id,
                    "created_at": created_at,
                },
            )
            new_thread_id = result.fetchone()[0]

            # Migrate messages - only user and assistant roles, skip SOURCES/TERMINAL_INFO
            message_count = 0
            for msg in messages:
                role_lower = msg.get("role", "").lower()

                # Only migrate user and assistant messages
                if role_lower not in ("user", "assistant"):
                    continue

                # Convert to uppercase for database enum
                role = role_lower.upper()

                # Extract content - handle various formats
                content_raw = msg.get("content", "")
                content_text = extract_text_content(content_raw)

                # Skip empty messages
                if not content_text.strip():
                    continue

                # Parse message timestamp
                msg_created_at = parse_timestamp(msg.get("createdAt"), created_at)

                # Store content as JSONB array format for assistant-ui compatibility
                content_list = [{"type": "text", "text": content_text}]

                # Use direct SQL with string interpolation for the enum since CAST doesn't work
                # The enum value comes from trusted source (our own code), not user input
                connection.execute(
                    sa.text(f"""
                        INSERT INTO new_chat_messages 
                        (thread_id, role, content, created_at)
                        VALUES (:thread_id, '{role}', CAST(:content AS jsonb), :created_at)
                    """),
                    {
                        "thread_id": new_thread_id,
                        "content": json.dumps(content_list),
                        "created_at": msg_created_at,
                    },
                )
                message_count += 1

            print(
                f"[Migration 49] Migrated chat {chat_id} -> thread {new_thread_id} ({message_count} messages)"
            )
            migrated_count += 1

        except Exception as e:
            print(f"[Migration 49] Error migrating chat {chat_id}: {e}")
            # Re-raise to abort migration - we don't want partial data
            raise

    print(f"[Migration 49] Successfully migrated {migrated_count} chats")

    # Drop chats table (podcasts table was already updated to remove chat_id FK)
    print("[Migration 49] Dropping chats table...")
    op.drop_table("chats")

    # Drop chattype enum
    print("[Migration 49] Dropping chattype enum...")
    op.execute(sa.text("DROP TYPE IF EXISTS chattype"))

    print("[Migration 49] Migration complete!")


def enum_exists(enum_name: str) -> bool:
    """Check if an enum type exists in the database."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = :enum_name)"),
        {"enum_name": enum_name},
    )
    return result.scalar()


def downgrade() -> None:
    """Recreate old chats table (data cannot be restored)."""
    # Skip if chats table already exists
    if table_exists("chats"):
        print("[Migration 49 Downgrade] Chats table already exists, skipping")
        return

    # Recreate chattype enum if it doesn't exist
    if not enum_exists("chattype"):
        op.execute(
            sa.text("""
                CREATE TYPE chattype AS ENUM ('QNA')
            """)
        )

    # Recreate chats table using raw SQL to avoid SQLAlchemy trying to create the enum
    op.execute(
        sa.text("""
            CREATE TABLE chats (
                id SERIAL PRIMARY KEY,
                type chattype NOT NULL,
                title VARCHAR NOT NULL,
                initial_connectors VARCHAR[],
                messages JSON NOT NULL,
                state_version BIGINT NOT NULL DEFAULT 1,
                search_space_id INTEGER NOT NULL REFERENCES searchspaces(id) ON DELETE CASCADE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        """)
    )
    op.execute(sa.text("CREATE INDEX ix_chats_id ON chats (id)"))
    op.execute(sa.text("CREATE INDEX ix_chats_title ON chats (title)"))

    print("[Migration 49 Downgrade] Chats table recreated (data not restored)")
