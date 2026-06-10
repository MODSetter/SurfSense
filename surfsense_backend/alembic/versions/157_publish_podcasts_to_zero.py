"""publish podcasts to zero_publication

Reconciles ``zero_publication`` after migration 156 added the lifecycle columns,
so the frontend observes podcast status and the reviewable brief by push.

Revision ID: 157
Revises: 156
"""

from collections.abc import Sequence

from alembic import op

from app.zero_publication import apply_publication

revision: str = "157"
down_revision: str | None = "156"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_publication(op.get_bind())


def downgrade() -> None:
    """No-op. Historical publication shapes are immutable."""
