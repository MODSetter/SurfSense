"""Add content_hash column to documents table

Revision ID: 8
Revises: 7
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8'
down_revision: Union[str, None] = '7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add content_hash column as nullable first to handle existing data
    op.add_column('documents', sa.Column('content_hash', sa.String(), nullable=True))
    
    # Update existing documents to generate content hashes
    # Using SHA-256 hash of the content column with proper UTF-8 encoding
    op.execute("""
        UPDATE documents 
        SET content_hash = encode(sha256(convert_to(content, 'UTF8')), 'hex')
        WHERE content_hash IS NULL
    """)
    
    # Handle duplicate content hashes by keeping only the oldest document for each hash
    # Delete newer documents with duplicate content hashes
    op.execute("""
        DELETE FROM documents 
        WHERE id NOT IN (
            SELECT MIN(id) 
            FROM documents 
            GROUP BY content_hash
        )
    """)
    
    # Now alter the column to match the model: nullable=False, index=True, unique=True
    op.alter_column('documents', 'content_hash', 
                    existing_type=sa.String(),
                    nullable=False)
    op.create_index(op.f('ix_documents_content_hash'), 'documents', ['content_hash'], unique=False)
    op.create_unique_constraint(op.f('uq_documents_content_hash'), 'documents', ['content_hash'])


def downgrade() -> None:
    # Remove constraints and index first
    op.drop_constraint(op.f('uq_documents_content_hash'), 'documents', type_='unique')
    op.drop_index(op.f('ix_documents_content_hash'), table_name='documents')
    
    # Remove content_hash column from documents table
    op.drop_column('documents', 'content_hash') 