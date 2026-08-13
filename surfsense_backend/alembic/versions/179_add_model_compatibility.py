"""Add the model compatibility blocklist.

Records one verdict per catalogue model from the compatibility sweep. Status is
a plain VARCHAR rather than a PG enum so a new verdict never needs a migration
to land alongside the sweep that produces it.

Revision ID: 179
Revises: 178
"""

from collections.abc import Sequence

from alembic import op

revision: str = "179"
down_revision: str | None = "178"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE model_compatibility (
            id SERIAL PRIMARY KEY,
            model_id VARCHAR(255) NOT NULL,
            status VARCHAR(16) NOT NULL,
            failure_stage VARCHAR(32),
            error_code VARCHAR(64),
            error_excerpt TEXT,
            latency_ms INTEGER,
            checked_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_model_compatibility_model_id UNIQUE (model_id)
        )
        """
    )
    for statement in (
        "CREATE INDEX ix_model_compatibility_model_id ON model_compatibility(model_id)",
        "CREATE INDEX ix_model_compatibility_status ON model_compatibility(status)",
        "CREATE INDEX ix_model_compatibility_checked_at "
        "ON model_compatibility(checked_at)",
    ):
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE model_compatibility")
