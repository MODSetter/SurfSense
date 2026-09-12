"""add license purchases and trial claim ledger

Revision ID: 195
Revises: 194
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "195"
down_revision: str | None = "194"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "license_purchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stripe_checkout_session_id", sa.String(255), nullable=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False),
        sa.Column("max_users", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("keygen_license_id", sa.String(255), nullable=False),
        sa.Column("certificate", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("keygen_license_id"),
    )
    op.create_index(
        "ix_license_purchases_stripe_checkout_session_id",
        "license_purchases",
        ["stripe_checkout_session_id"],
        unique=True,
    )
    op.create_index(
        "ix_license_purchases_email",
        "license_purchases",
        ["email"],
        unique=False,
    )
    op.create_index(
        "ix_license_purchases_created_at",
        "license_purchases",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "license_trial_claims",
        sa.Column("identity_kind", sa.String(), nullable=False),
        sa.Column("identity_fingerprint", sa.String(64), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "identity_kind",
            "identity_fingerprint",
            name="uq_license_trial_claims_identity",
        ),
    )
    op.create_index(
        "ix_license_trial_claims_id",
        "license_trial_claims",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_license_trial_claims_created_at",
        "license_trial_claims",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("license_trial_claims")
    op.drop_table("license_purchases")
