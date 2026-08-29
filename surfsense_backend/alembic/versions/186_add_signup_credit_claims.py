"""Add the signup credit claim ledger and stop funding accounts by column default.

Revision ID: 186
Revises: 185
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.config import config
from app.signup_credit.identity.fingerprint import fingerprint
from app.signup_credit.identity.sources import GOOGLE_SUBJECT

revision: str = "186"
down_revision: str | None = "185"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BACKFILL_BATCH = 1000


def _oauth_account_table_exists() -> bool:
    """Only ``AUTH_TYPE=GOOGLE`` deployments have this table."""
    return bool(
        op.get_bind()
        .execute(
            sa.text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = current_schema()
                      AND table_name = 'oauth_account'
                )
                """
            )
        )
        .scalar()
    )


def _claim_existing_google_identities() -> None:
    """Record every current Google account as having taken the signup credit.

    Without this the ledger starts empty and existing users could delete and
    re-register for a second one.
    """
    if not _oauth_account_table_exists():
        return

    bind = op.get_bind()

    # `people/<sub>` and a bare `<sub>` are the same person; migration 169
    # normalised most rows but deliberately left duplicates behind.
    subjects = (
        bind.execute(
            sa.text(
                """
                SELECT DISTINCT regexp_replace(account_id, '^people/', '') AS subject
                FROM oauth_account
                WHERE oauth_name = 'google'
                  AND regexp_replace(account_id, '^people/', '') <> ''
                """
            )
        )
        .scalars()
        .all()
    )

    # Claim dates are this migration's own timestamp: "user" has no created_at
    # to copy. NOW() is explicit: a create_all-built table has no DB default.
    for start in range(0, len(subjects), _BACKFILL_BATCH):
        bind.execute(
            sa.text(
                """
                INSERT INTO signup_credit_claims
                    (identity_kind, identity_fingerprint, created_at)
                VALUES (:identity_kind, :identity_fingerprint, NOW())
                ON CONFLICT (identity_kind, identity_fingerprint) DO NOTHING
                """
            ),
            [
                {
                    "identity_kind": GOOGLE_SUBJECT,
                    "identity_fingerprint": fingerprint(subject),
                }
                for subject in subjects[start : start + _BACKFILL_BATCH]
            ],
        )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS signup_credit_claims (
            id SERIAL PRIMARY KEY,
            identity_kind VARCHAR NOT NULL,
            identity_fingerprint VARCHAR(64) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_signup_credit_claims_identity
                UNIQUE (identity_kind, identity_fingerprint)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_signup_credit_claims_created_at "
        "ON signup_credit_claims(created_at)"
    )

    _claim_existing_google_identities()

    # Left as a column default the credit is minted per row, which is what made
    # delete-and-re-register profitable. It is an explicit grant now.
    op.execute('ALTER TABLE "user" ALTER COLUMN credit_micros_balance SET DEFAULT 0')


def downgrade() -> None:
    op.execute(
        'ALTER TABLE "user" ALTER COLUMN credit_micros_balance '
        f"SET DEFAULT {int(config.DEFAULT_CREDIT_MICROS_BALANCE)}"
    )
    op.execute("DROP TABLE IF EXISTS signup_credit_claims")
