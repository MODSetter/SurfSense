"""make security_events user_id nullable

Revision ID: 43_nullable_user_id
Revises: 42_add_security_events_table
Create Date: 2025-01-21

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '43_nullable_user_id'
down_revision = '42_add_security_events_table'
branch_labels = None
depends_on = None


def upgrade():
    """
    Make user_id column nullable in security_events table.

    This allows logging security events for anonymous/unauthenticated attempts
    such as failed login attempts for non-existent users.
    """
    # Make user_id nullable
    op.alter_column(
        'security_events',
        'user_id',
        existing_type=sa.UUID(),
        nullable=True
    )


def downgrade():
    """
    Make user_id column non-nullable in security_events table.

    Warning: This will fail if there are any rows with NULL user_id.
    """
    # Make user_id non-nullable
    op.alter_column(
        'security_events',
        'user_id',
        existing_type=sa.UUID(),
        nullable=False
    )
