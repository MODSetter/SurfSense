"""Add LLMConfig table and user LLM preferences

Revision ID: 11
Revises: 10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON


# revision identifiers, used by Alembic.
revision: str = "11"
down_revision: Union[str, None] = "10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add LiteLLMProvider enum, LLMConfig table and user LLM preferences."""
    
    # Check if enum type exists and create if it doesn't
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'litellmprovider') THEN
                CREATE TYPE litellmprovider AS ENUM ('OPENAI', 'ANTHROPIC', 'GROQ', 'COHERE', 'HUGGINGFACE', 'AZURE_OPENAI', 'GOOGLE', 'AWS_BEDROCK', 'OLLAMA', 'MISTRAL', 'TOGETHER_AI', 'REPLICATE', 'PALM', 'VERTEX_AI', 'ANYSCALE', 'PERPLEXITY', 'DEEPINFRA', 'AI21', 'NLPCLOUD', 'ALEPH_ALPHA', 'PETALS', 'CUSTOM');
            END IF;
        END$$;
    """)
    
    # Create llm_configs table using raw SQL to avoid enum creation conflicts
    op.execute("""
        CREATE TABLE llm_configs (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            name VARCHAR(100) NOT NULL,
            provider litellmprovider NOT NULL,
            custom_provider VARCHAR(100),
            model_name VARCHAR(100) NOT NULL,
            api_key TEXT NOT NULL,
            api_base VARCHAR(500),
            litellm_params JSONB,
            user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE
        )
    """)
    
    # Create indexes
    op.create_index(op.f('ix_llm_configs_id'), 'llm_configs', ['id'], unique=False)
    op.create_index(op.f('ix_llm_configs_created_at'), 'llm_configs', ['created_at'], unique=False)
    op.create_index(op.f('ix_llm_configs_name'), 'llm_configs', ['name'], unique=False)
    
    # Add LLM preference columns to user table
    op.add_column('user', sa.Column('long_context_llm_id', sa.Integer(), nullable=True))
    op.add_column('user', sa.Column('fast_llm_id', sa.Integer(), nullable=True))
    op.add_column('user', sa.Column('strategic_llm_id', sa.Integer(), nullable=True))
    
    # Create foreign key constraints for LLM preferences
    op.create_foreign_key(op.f('fk_user_long_context_llm_id_llm_configs'), 'user', 'llm_configs', ['long_context_llm_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(op.f('fk_user_fast_llm_id_llm_configs'), 'user', 'llm_configs', ['fast_llm_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(op.f('fk_user_strategic_llm_id_llm_configs'), 'user', 'llm_configs', ['strategic_llm_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema - remove LLMConfig table and user LLM preferences."""
    
    # Drop foreign key constraints
    op.drop_constraint(op.f('fk_user_strategic_llm_id_llm_configs'), 'user', type_='foreignkey')
    op.drop_constraint(op.f('fk_user_fast_llm_id_llm_configs'), 'user', type_='foreignkey')
    op.drop_constraint(op.f('fk_user_long_context_llm_id_llm_configs'), 'user', type_='foreignkey')
    
    # Drop LLM preference columns from user table
    op.drop_column('user', 'strategic_llm_id')
    op.drop_column('user', 'fast_llm_id')
    op.drop_column('user', 'long_context_llm_id')
    
    # Drop indexes and table
    op.drop_index(op.f('ix_llm_configs_name'), table_name='llm_configs')
    op.drop_index(op.f('ix_llm_configs_created_at'), table_name='llm_configs')
    op.drop_index(op.f('ix_llm_configs_id'), table_name='llm_configs')
    op.drop_table('llm_configs')
    
    # Drop LiteLLMProvider enum
    op.execute("DROP TYPE IF EXISTS litellmprovider") 