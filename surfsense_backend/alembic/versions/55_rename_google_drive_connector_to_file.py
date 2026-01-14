"""Rename GOOGLE_DRIVE_CONNECTOR document type to GOOGLE_DRIVE_FILE

Revision ID: 55
Revises: 54
Create Date: 2025-12-29 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "55"
down_revision: str | None = "54"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from sqlalchemy import text

    connection = op.get_bind()

    connection.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_type t
                    JOIN pg_enum e ON t.oid = e.enumtypid
                    WHERE t.typname = 'documenttype' AND e.enumlabel = 'GOOGLE_DRIVE_FILE'
                ) THEN
                    ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'GOOGLE_DRIVE_FILE';
                END IF;
            END
            $$;
            """
        )
    )

    connection.commit()

    connection.execute(
        text(
            """
            UPDATE documents
            SET document_type = 'GOOGLE_DRIVE_FILE'
            WHERE document_type = 'GOOGLE_DRIVE_CONNECTOR';
            """
        )
    )

    connection.commit()


def downgrade() -> None:
    from sqlalchemy import text

    connection = op.get_bind()

    # Only update if the target enum value exists (it won't on fresh databases)
    result = connection.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_enum e ON t.oid = e.enumtypid
                WHERE t.typname = 'documenttype' AND e.enumlabel = 'GOOGLE_DRIVE_CONNECTOR'
            );
            """
        )
    )
    enum_exists = result.scalar()

    if enum_exists:
        connection.execute(
            text(
                """
                UPDATE documents
                SET document_type = 'GOOGLE_DRIVE_CONNECTOR'
                WHERE document_type = 'GOOGLE_DRIVE_FILE';
                """
            )
        )
        connection.commit()
