"""add security events table

Revision ID: 42
Revises: 41
Create Date: 2025-11-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "42"
down_revision: Union[str, None] = "41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type for security event types
    op.execute("""
        CREATE TYPE securityeventtype AS ENUM (
            'TWO_FA_ENABLED',
            'TWO_FA_DISABLED',
            'TWO_FA_SETUP_INITIATED',
            'TWO_FA_VERIFICATION_SUCCESS',
            'TWO_FA_VERIFICATION_FAILED',
            'TWO_FA_LOGIN_SUCCESS',
            'TWO_FA_LOGIN_FAILED',
            'BACKUP_CODE_USED',
            'BACKUP_CODES_REGENERATED',
            'PASSWORD_LOGIN_SUCCESS',
            'PASSWORD_LOGIN_FAILED'
        )
    """)

    # Create security_events table
    op.create_table(
        "security_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.Enum(
            'TWO_FA_ENABLED',
            'TWO_FA_DISABLED',
            'TWO_FA_SETUP_INITIATED',
            'TWO_FA_VERIFICATION_SUCCESS',
            'TWO_FA_VERIFICATION_FAILED',
            'TWO_FA_LOGIN_SUCCESS',
            'TWO_FA_LOGIN_FAILED',
            'BACKUP_CODE_USED',
            'BACKUP_CODES_REGENERATED',
            'PASSWORD_LOGIN_SUCCESS',
            'PASSWORD_LOGIN_FAILED',
            name='securityeventtype'
        ), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("details", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )

    # Create indexes
    op.create_index("ix_security_events_event_type", "security_events", ["event_type"])
    op.create_index("ix_security_events_user_id", "security_events", ["user_id"])
    op.create_index("ix_security_events_created_at", "security_events", ["created_at"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_security_events_created_at", table_name="security_events")
    op.drop_index("ix_security_events_user_id", table_name="security_events")
    op.drop_index("ix_security_events_event_type", table_name="security_events")

    # Drop table
    op.drop_table("security_events")

    # Drop enum type
    op.execute("DROP TYPE securityeventtype")
