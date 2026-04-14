"""129_make_model_config_search_space_id_nullable

Revision ID: 129
Revises: 128
Create Date: 2026-04-15

Makes search_space_id nullable on the three model-config tables so that
admin-created (superuser-owned) configurations have search_space_id = NULL
and are visible to ALL users across ALL search spaces.

Tables affected:
  - new_llm_configs
  - image_generation_configs
  - vision_llm_configs
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "129"
down_revision: str | None = "128"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "new_llm_configs", "search_space_id", existing_type=sa.Integer(), nullable=True
    )
    op.alter_column(
        "image_generation_configs",
        "search_space_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.alter_column(
        "vision_llm_configs",
        "search_space_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Delete global configs (search_space_id IS NULL) before restoring NOT NULL
    for table in ("new_llm_configs", "image_generation_configs", "vision_llm_configs"):
        conn.execute(sa.text(f'DELETE FROM "{table}" WHERE search_space_id IS NULL'))

    op.alter_column(
        "new_llm_configs", "search_space_id", existing_type=sa.Integer(), nullable=False
    )
    op.alter_column(
        "image_generation_configs",
        "search_space_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "vision_llm_configs",
        "search_space_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
