"""Add GOOGLE_DRIVE_CONNECTOR to SearchSourceConnectorType and DocumentType enums

Revision ID: 13
Revises: 12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13'
down_revision: Union[str, None] = '12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add GOOGLE_DRIVE_CONNECTOR to both enums."""
    # Add to SearchSourceConnectorType enum
    op.execute("ALTER TYPE searchsourceconnectortype ADD VALUE 'GOOGLE_DRIVE_CONNECTOR'")
    
    # Add to DocumentType enum  
    op.execute("ALTER TYPE documenttype ADD VALUE 'GOOGLE_DRIVE_CONNECTOR'")


def downgrade() -> None:
    """Downgrade schema - remove GOOGLE_DRIVE_CONNECTOR from both enums."""
    
    # Handle SearchSourceConnectorType enum
    op.execute("ALTER TYPE searchsourceconnectortype RENAME TO searchsourceconnectortype_old")
    op.execute("""
        CREATE TYPE searchsourceconnectortype AS ENUM(
            'SERPER_API', 'TAVILY_API', 'LINKUP_API', 'SLACK_CONNECTOR', 
            'NOTION_CONNECTOR', 'GITHUB_CONNECTOR', 'LINEAR_CONNECTOR', 
            'DISCORD_CONNECTOR'
        )
    """)
    
    # Delete any rows using the removed value
    op.execute("DELETE FROM search_source_connectors WHERE connector_type::text = 'GOOGLE_DRIVE_CONNECTOR'")
    
    op.execute("""
        ALTER TABLE search_source_connectors ALTER COLUMN connector_type 
        TYPE searchsourceconnectortype USING connector_type::text::searchsourceconnectortype
    """)
    op.execute("DROP TYPE searchsourceconnectortype_old")
    
    # Handle DocumentType enum
    op.execute("ALTER TYPE documenttype RENAME TO documenttype_old")
    op.execute("""
        CREATE TYPE documenttype AS ENUM(
            'EXTENSION', 'CRAWLED_URL', 'FILE', 'SLACK_CONNECTOR', 
            'NOTION_CONNECTOR', 'YOUTUBE_VIDEO', 'GITHUB_CONNECTOR', 
            'LINEAR_CONNECTOR', 'DISCORD_CONNECTOR'
        )
    """)
    
    # Delete any rows using the removed value
    op.execute("DELETE FROM documents WHERE document_type::text = 'GOOGLE_DRIVE_CONNECTOR'")
    
    op.execute("""
        ALTER TABLE documents ALTER COLUMN document_type 
        TYPE documenttype USING document_type::text::documenttype
    """)
    op.execute("DROP TYPE documenttype_old")