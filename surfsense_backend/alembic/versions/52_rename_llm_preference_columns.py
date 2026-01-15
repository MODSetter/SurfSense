"""Rename LLM preference columns in searchspaces table

Revision ID: 52
Revises: 51
Create Date: 2024-12-22

This migration renames the LLM preference columns:
- fast_llm_id -> agent_llm_id
- long_context_llm_id -> document_summary_llm_id
- strategic_llm_id is removed (data migrated to document_summary_llm_id)
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "52"
down_revision = "51"
branch_labels = None
depends_on = None


def upgrade():
    # First, migrate any strategic_llm_id values to document_summary_llm_id
    # (only if document_summary_llm_id/long_context_llm_id is NULL)
    # Use IF EXISTS check to handle case where column might not exist
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'searchspaces' AND column_name = 'strategic_llm_id'
            ) THEN
                UPDATE searchspaces 
                SET long_context_llm_id = strategic_llm_id 
                WHERE long_context_llm_id IS NULL AND strategic_llm_id IS NOT NULL;
            END IF;
        END$$;
        """
    )

    # Rename columns (only if source exists and target doesn't already exist)
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'searchspaces' AND column_name = 'fast_llm_id'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'searchspaces' AND column_name = 'agent_llm_id'
            ) THEN
                ALTER TABLE searchspaces RENAME COLUMN fast_llm_id TO agent_llm_id;
            END IF;
        END$$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'searchspaces' AND column_name = 'long_context_llm_id'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'searchspaces' AND column_name = 'document_summary_llm_id'
            ) THEN
                ALTER TABLE searchspaces RENAME COLUMN long_context_llm_id TO document_summary_llm_id;
            END IF;
        END$$;
        """
    )

    # Drop the strategic_llm_id column if it exists
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'searchspaces' AND column_name = 'strategic_llm_id'
            ) THEN
                ALTER TABLE searchspaces DROP COLUMN strategic_llm_id;
            END IF;
        END$$;
        """
    )


def downgrade():
    # Add back the strategic_llm_id column
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'searchspaces' AND column_name = 'strategic_llm_id'
            ) THEN
                ALTER TABLE searchspaces ADD COLUMN strategic_llm_id INTEGER;
            END IF;
        END$$;
        """
    )

    # Rename columns back (only if source exists and target doesn't already exist)
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'searchspaces' AND column_name = 'agent_llm_id'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'searchspaces' AND column_name = 'fast_llm_id'
            ) THEN
                ALTER TABLE searchspaces RENAME COLUMN agent_llm_id TO fast_llm_id;
            END IF;
        END$$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'searchspaces' AND column_name = 'document_summary_llm_id'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'searchspaces' AND column_name = 'long_context_llm_id'
            ) THEN
                ALTER TABLE searchspaces RENAME COLUMN document_summary_llm_id TO long_context_llm_id;
            END IF;
        END$$;
        """
    )
