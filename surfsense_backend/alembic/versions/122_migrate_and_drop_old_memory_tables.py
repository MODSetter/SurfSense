"""Migrate row-per-fact memories to markdown, then drop legacy tables

Revision ID: 122
Revises: 121

Converts user_memories rows into per-user markdown documents stored in
user.memory_md, and shared_memories rows into per-search-space markdown
stored in searchspaces.shared_memory_md.  Then drops the old tables and
the memorycategory enum.

The markdown format matches the new memory system:
  ## Heading
  - (YYYY-MM-DD) [fact|pref|instr] memory text
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

from alembic import op
from app.config import config

logger = logging.getLogger(__name__)

revision: str = "122"
down_revision: str | None = "121"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = config.embedding_model_instance.dimension

_CATEGORY_TO_MARKER = {
    "fact": "fact",
    "context": "fact",
    "preference": "pref",
    "instruction": "instr",
}

_CATEGORY_HEADING = {
    "fact": "Facts",
    "preference": "Preferences",
    "instruction": "Instructions",
    "context": "Context",
}

_HEADING_ORDER = ["fact", "preference", "instruction", "context"]


def _build_markdown(rows: list[tuple]) -> str:
    """Build a markdown document from (memory_text, category, created_at) rows."""
    by_category: dict[str, list[str]] = defaultdict(list)

    for memory_text, category, created_at in rows:
        cat = str(category)
        marker = _CATEGORY_TO_MARKER.get(cat, "fact")
        date_str = created_at.strftime("%Y-%m-%d")
        clean_text = str(memory_text).replace("\n", " ").strip()
        bullet = f"- ({date_str}) [{marker}] {clean_text}"
        by_category[cat].append(bullet)

    sections: list[str] = []
    for cat in _HEADING_ORDER:
        if cat in by_category:
            heading = _CATEGORY_HEADING[cat]
            sections.append(f"## {heading}")
            sections.extend(by_category[cat])
            sections.append("")

    return "\n".join(sections).strip() + "\n"


def _migrate_user_memories(conn: sa.engine.Connection) -> None:
    """Convert user_memories rows → user.memory_md grouped by user_id."""
    rows = conn.execute(
        sa.text(
            "SELECT user_id, memory_text, category::text, created_at "
            "FROM user_memories ORDER BY created_at"
        )
    ).fetchall()

    if not rows:
        logger.info("user_memories is empty, skipping data migration.")
        return

    by_user: dict[UUID, list[tuple]] = defaultdict(list)
    for user_id, memory_text, category, created_at in rows:
        by_user[user_id].append((memory_text, category, created_at))

    migrated = 0
    for uid, user_rows in by_user.items():
        existing = conn.execute(
            sa.text('SELECT memory_md FROM "user" WHERE id = :uid'),
            {"uid": uid},
        ).scalar()

        if existing and existing.strip():
            logger.info("User %s already has memory_md, skipping.", uid)
            continue

        markdown = _build_markdown(user_rows)
        conn.execute(
            sa.text('UPDATE "user" SET memory_md = :md WHERE id = :uid'),
            {"md": markdown, "uid": uid},
        )
        migrated += 1

    logger.info("Migrated user_memories for %d user(s).", migrated)


def _migrate_shared_memories(conn: sa.engine.Connection) -> None:
    """Convert shared_memories rows → searchspaces.shared_memory_md."""
    rows = conn.execute(
        sa.text(
            "SELECT search_space_id, memory_text, category::text, created_at "
            "FROM shared_memories ORDER BY created_at"
        )
    ).fetchall()

    if not rows:
        logger.info("shared_memories is empty, skipping data migration.")
        return

    by_space: dict[int, list[tuple]] = defaultdict(list)
    for search_space_id, memory_text, category, created_at in rows:
        by_space[search_space_id].append((memory_text, category, created_at))

    migrated = 0
    for space_id, space_rows in by_space.items():
        existing = conn.execute(
            sa.text("SELECT shared_memory_md FROM searchspaces WHERE id = :sid"),
            {"sid": space_id},
        ).scalar()

        if existing and existing.strip():
            logger.info(
                "Search space %s already has shared_memory_md, skipping.", space_id
            )
            continue

        markdown = _build_markdown(space_rows)
        conn.execute(
            sa.text("UPDATE searchspaces SET shared_memory_md = :md WHERE id = :sid"),
            {"md": markdown, "sid": space_id},
        )
        migrated += 1

    logger.info("Migrated shared_memories for %d search space(s).", migrated)


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)
    tables = inspector.get_table_names()

    if "user_memories" in tables:
        _migrate_user_memories(conn)

    if "shared_memories" in tables:
        _migrate_shared_memories(conn)

    op.execute("DROP TABLE IF EXISTS shared_memories CASCADE;")
    op.execute("DROP TABLE IF EXISTS user_memories CASCADE;")
    op.execute("DROP TYPE IF EXISTS memorycategory;")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'memorycategory') THEN
                CREATE TYPE memorycategory AS ENUM (
                    'preference',
                    'fact',
                    'instruction',
                    'context'
                );
            END IF;
        END$$;
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS user_memories (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            search_space_id INTEGER REFERENCES searchspaces(id) ON DELETE CASCADE,
            memory_text TEXT NOT NULL,
            category memorycategory NOT NULL DEFAULT 'fact',
            embedding vector({EMBEDDING_DIM}),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_memories_user_id ON user_memories(user_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_memories_search_space_id ON user_memories(search_space_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_memories_updated_at ON user_memories(updated_at);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_memories_category ON user_memories(category);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_memories_user_search_space ON user_memories(user_id, search_space_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS user_memories_vector_index ON user_memories USING hnsw (embedding public.vector_cosine_ops);"
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS shared_memories (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            search_space_id INTEGER NOT NULL REFERENCES searchspaces(id) ON DELETE CASCADE,
            created_by_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            memory_text TEXT NOT NULL,
            category memorycategory NOT NULL DEFAULT 'fact',
            embedding vector({EMBEDDING_DIM})
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_shared_memories_search_space_id ON shared_memories(search_space_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_shared_memories_updated_at ON shared_memories(updated_at);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_shared_memories_created_by_id ON shared_memories(created_by_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS shared_memories_vector_index ON shared_memories USING hnsw (embedding public.vector_cosine_ops);"
    )
