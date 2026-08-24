"""Publish the safe deliverable-job lifecycle projection to Zero.

Revision ID: 187
Revises: 186
"""

from collections.abc import Sequence

from alembic import op
from app.zero_publication import apply_publication

revision: str = "187"
down_revision: str | None = "186"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_publication(op.get_bind())


def downgrade() -> None:
    """No-op. Historical publication shapes are immutable."""
