"""
Add GOOGLE_CALENDAR_CONNECTOR to SearchSourceConnectorType and DocumentType enums
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '13_add_google_calendar_connector_enum'
down_revision = '12_add_logs_table'
branch_labels = None
depends_on = None

CONNECTOR_NEW_VALUE = "GOOGLE_CALENDAR_CONNECTOR"
DOCUMENT_NEW_VALUE = "GOOGLE_CALENDAR_CONNECTOR"

def upgrade():
    # Add GOOGLE_CALENDAR_CONNECTOR to searchsourceconnectortype
    op.execute(f"ALTER TYPE searchsourceconnectortype ADD VALUE IF NOT EXISTS '{CONNECTOR_NEW_VALUE}'")
    # Add GOOGLE_CALENDAR_CONNECTOR to documenttype
    op.execute(f"ALTER TYPE documenttype ADD VALUE IF NOT EXISTS '{DOCUMENT_NEW_VALUE}'")

def downgrade():
    # Downgrade logic: cannot remove enum values in PostgreSQL, so this is a no-op
    pass 