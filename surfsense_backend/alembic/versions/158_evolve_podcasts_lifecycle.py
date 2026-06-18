"""evolve podcasts: expand status lifecycle and add brief/transcript/storage columns

Revision ID: 158
Revises: 157
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "158"
down_revision: str | None = "157"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PUBLICATION_NAME = "zero_publication"
TARGET_STATUS_LABELS = (
    "pending",
    "awaiting_brief",
    "drafting",
    "awaiting_review",
    "rendering",
    "ready",
    "failed",
    "cancelled",
)
LEGACY_STATUS_LABELS = ("pending", "generating", "ready", "failed")


def _drop_podcasts_from_publication() -> None:
    """Detach podcasts from zero_publication so status can be retyped.

    Postgres refuses ``ALTER COLUMN ... TYPE`` on a column a publication
    depends on. Some databases reach this migration with podcasts already
    published (an interim apply_publication ran during 156); drop it here and
    let migration 159 reconcile the publication to the canonical shape.
    """
    conn = op.get_bind()
    published = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_publication_tables "
            "WHERE pubname = :publication "
            "AND schemaname = current_schema() AND tablename = 'podcasts'"
        ),
        {"publication": PUBLICATION_NAME},
    ).fetchone()
    if published:
        op.execute(f'ALTER PUBLICATION "{PUBLICATION_NAME}" DROP TABLE "podcasts";')


def _enum_labels(type_name: str) -> list[str] | None:
    rows = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT e.enumlabel "
                "FROM pg_type t "
                "JOIN pg_namespace n ON n.oid = t.typnamespace "
                "JOIN pg_enum e ON e.enumtypid = t.oid "
                "WHERE n.nspname = current_schema() AND t.typname = :type_name "
                "ORDER BY e.enumsortorder"
            ),
            {"type_name": type_name},
        )
        .fetchall()
    )
    if not rows:
        return None
    return [str(row[0]) for row in rows]


def _column_type_name(table: str, column: str) -> str | None:
    row = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT udt_name "
                "FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND table_name = :table AND column_name = :column"
            ),
            {"table": table, "column": column},
        )
        .fetchone()
    )
    return str(row[0]) if row else None


def _ensure_status_enum(
    *,
    desired_labels: tuple[str, ...],
    temporary_type: str,
    create_sql: str,
    alter_sql: str,
    default_value: str,
) -> None:
    current_labels = _enum_labels("podcast_status")
    desired = list(desired_labels)

    if current_labels != desired:
        if current_labels is None:
            if _enum_labels(temporary_type) is None:
                raise RuntimeError("podcast_status enum is missing")
        elif _enum_labels(temporary_type) is None:
            op.execute(f"ALTER TYPE podcast_status RENAME TO {temporary_type};")
        else:
            raise RuntimeError(
                "podcast_status and its temporary replacement both exist"
            )

        if _enum_labels("podcast_status") is None:
            op.execute(create_sql)

    if _enum_labels("podcast_status") != desired:
        raise RuntimeError("podcast_status enum is not in the expected shape")

    op.execute("ALTER TABLE podcasts ALTER COLUMN status DROP DEFAULT;")
    if _column_type_name("podcasts", "status") != "podcast_status":
        op.execute(alter_sql)
    op.execute(
        f"ALTER TABLE podcasts ALTER COLUMN status SET DEFAULT '{default_value}';"
    )

    if _enum_labels(temporary_type) is not None:
        op.execute(f"DROP TYPE {temporary_type};")


def _upgrade_status_enum() -> None:
    _ensure_status_enum(
        desired_labels=TARGET_STATUS_LABELS,
        temporary_type="podcast_status_old",
        create_sql="""
        CREATE TYPE podcast_status AS ENUM (
            'pending', 'awaiting_brief', 'drafting', 'awaiting_review',
            'rendering', 'ready', 'failed', 'cancelled'
        );
        """,
        alter_sql="""
        ALTER TABLE podcasts
            ALTER COLUMN status TYPE podcast_status
            USING (
                CASE status::text
                    WHEN 'generating' THEN 'rendering'
                    ELSE status::text
                END
            )::podcast_status;
        """,
        default_value="pending",
    )


def _downgrade_status_enum() -> None:
    _ensure_status_enum(
        desired_labels=LEGACY_STATUS_LABELS,
        temporary_type="podcast_status_new",
        create_sql=(
            "CREATE TYPE podcast_status AS ENUM "
            "('pending', 'generating', 'ready', 'failed');"
        ),
        alter_sql="""
        ALTER TABLE podcasts
            ALTER COLUMN status TYPE podcast_status
            USING (
                CASE status::text
                    WHEN 'awaiting_brief' THEN 'pending'
                    WHEN 'drafting' THEN 'generating'
                    WHEN 'awaiting_review' THEN 'generating'
                    WHEN 'rendering' THEN 'generating'
                    WHEN 'cancelled' THEN 'failed'
                    ELSE status::text
                END
            )::podcast_status;
        """,
        default_value="ready",
    )


def upgrade() -> None:
    _drop_podcasts_from_publication()

    # Retype the status enum by swapping in a fresh type and casting existing
    # rows. The legacy transient value 'generating' maps onto 'rendering'.
    _upgrade_status_enum()

    op.execute("ALTER TABLE podcasts ADD COLUMN IF NOT EXISTS source_content TEXT;")
    op.execute("ALTER TABLE podcasts ADD COLUMN IF NOT EXISTS spec JSONB;")
    op.execute(
        "ALTER TABLE podcasts ADD COLUMN IF NOT EXISTS spec_version "
        "INTEGER NOT NULL DEFAULT 1;"
    )
    op.execute(
        "ALTER TABLE podcasts ADD COLUMN IF NOT EXISTS storage_backend VARCHAR(32);"
    )
    op.execute("ALTER TABLE podcasts ADD COLUMN IF NOT EXISTS storage_key TEXT;")
    op.execute(
        "ALTER TABLE podcasts ADD COLUMN IF NOT EXISTS duration_seconds INTEGER;"
    )
    op.execute("ALTER TABLE podcasts ADD COLUMN IF NOT EXISTS error TEXT;")


def downgrade() -> None:
    _drop_podcasts_from_publication()

    op.execute("ALTER TABLE podcasts DROP COLUMN IF EXISTS error;")
    op.execute("ALTER TABLE podcasts DROP COLUMN IF EXISTS duration_seconds;")
    op.execute("ALTER TABLE podcasts DROP COLUMN IF EXISTS storage_key;")
    op.execute("ALTER TABLE podcasts DROP COLUMN IF EXISTS storage_backend;")
    op.execute("ALTER TABLE podcasts DROP COLUMN IF EXISTS spec_version;")
    op.execute("ALTER TABLE podcasts DROP COLUMN IF EXISTS spec;")
    op.execute("ALTER TABLE podcasts DROP COLUMN IF EXISTS source_content;")

    # Collapse the expanded lifecycle back onto the original four values.
    _downgrade_status_enum()
