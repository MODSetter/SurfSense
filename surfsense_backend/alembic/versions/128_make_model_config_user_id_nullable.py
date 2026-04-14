"""128_make_model_config_user_id_nullable

Revision ID: 128
Revises: 127
Create Date: 2026-04-15

Makes user_id nullable on the three model-config tables so that admin-created
(superuser-owned) configurations have user_id = NULL and are visible to all
members of the search space.

Tables affected:
  - new_llm_configs
  - image_generation_configs
  - vision_llm_configs
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "128"
down_revision: str | None = "127"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("new_llm_configs", "user_id", existing_type=sa.UUID(), nullable=True)
    op.alter_column("image_generation_configs", "user_id", existing_type=sa.UUID(), nullable=True)
    op.alter_column("vision_llm_configs", "user_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    conn = op.get_bind()

    # Null out orphaned rows before re-adding NOT NULL (safety guard)
    for table in ("new_llm_configs", "image_generation_configs", "vision_llm_configs"):
        # If any rows have user_id=NULL we cannot restore NOT NULL — delete them
        conn.execute(sa.text(f'DELETE FROM "{table}" WHERE user_id IS NULL'))

    op.alter_column("new_llm_configs", "user_id", existing_type=sa.UUID(), nullable=False)
    op.alter_column("image_generation_configs", "user_id", existing_type=sa.UUID(), nullable=False)
    op.alter_column("vision_llm_configs", "user_id", existing_type=sa.UUID(), nullable=False)
