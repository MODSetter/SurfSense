import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "40"
down_revision = "39"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    existing_cols = {col["name"] for col in inspector.get_columns("searchspaces")}

    # Add columns only if they don't already exist
    if "long_context_llm_id" not in existing_cols:
        op.add_column(
            "searchspaces",
            sa.Column("long_context_llm_id", sa.Integer(), nullable=True),
        )

    if "fast_llm_id" not in existing_cols:
        op.add_column(
            "searchspaces",
            sa.Column("fast_llm_id", sa.Integer(), nullable=True),
        )

    if "strategic_llm_id" not in existing_cols:
        op.add_column(
            "searchspaces",
            sa.Column("strategic_llm_id", sa.Integer(), nullable=True),
        )

    # Migrate existing data
    conn.execute(
        sa.text("""
            UPDATE searchspaces ss
            SET 
                long_context_llm_id = usp.long_context_llm_id,
                fast_llm_id = usp.fast_llm_id,
                strategic_llm_id = usp.strategic_llm_id
            FROM user_search_space_preferences usp
            WHERE ss.id = usp.search_space_id
            AND ss.user_id = usp.user_id
        """)
    )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_cols = {col["name"] for col in inspector.get_columns("searchspaces")}

    # Drop columns only if they exist
    if "strategic_llm_id" in existing_cols:
        op.drop_column("searchspaces", "strategic_llm_id")

    if "fast_llm_id" in existing_cols:
        op.drop_column("searchspaces", "fast_llm_id")

    if "long_context_llm_id" in existing_cols:
        op.drop_column("searchspaces", "long_context_llm_id")
