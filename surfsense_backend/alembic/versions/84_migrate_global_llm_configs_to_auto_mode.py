"""Migrate global LLM configs to Auto mode

Revision ID: 84
Revises: 83

This migration updates existing search spaces that use global LLM configs
(negative IDs) to use the new Auto mode (ID 0) instead.

Auto mode uses LiteLLM Router to automatically load balance requests across
all configured global LLM providers, which helps avoid rate limits.

Changes:
1. Update agent_llm_id from negative values to 0 (Auto mode)
2. Update document_summary_llm_id from negative values to 0 (Auto mode)
3. Update NULL values to 0 (Auto mode) as the new default

Note: This migration preserves any custom user-created LLM configs (positive IDs).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "84"
down_revision: str | None = "83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Migrate global LLM config IDs (negative) and NULL to Auto mode (0)."""
    # Update agent_llm_id: convert negative values and NULL to 0 (Auto mode)
    op.execute(
        """
        UPDATE searchspaces 
        SET agent_llm_id = 0 
        WHERE agent_llm_id < 0 OR agent_llm_id IS NULL
        """
    )

    # Update document_summary_llm_id: convert negative values and NULL to 0 (Auto mode)
    op.execute(
        """
        UPDATE searchspaces 
        SET document_summary_llm_id = 0 
        WHERE document_summary_llm_id < 0 OR document_summary_llm_id IS NULL
        """
    )


def downgrade() -> None:
    """Revert Auto mode back to the first global config (ID -1).

    Note: This is a best-effort revert. We cannot know which specific
    global config each search space was using before, so we default
    to -1 (typically the first/primary global config).
    """
    # Revert agent_llm_id from Auto mode (0) back to first global config (-1)
    op.execute(
        """
        UPDATE searchspaces 
        SET agent_llm_id = -1 
        WHERE agent_llm_id = 0
        """
    )

    # Revert document_summary_llm_id from Auto mode (0) back to first global config (-1)
    op.execute(
        """
        UPDATE searchspaces 
        SET document_summary_llm_id = -1 
        WHERE document_summary_llm_id = 0
        """
    )
