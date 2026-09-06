"""start the first allowance period for existing free accounts

Migration 192 added the plan columns but left them inert: every row had a zero
allowance and a null ``allowance_period_end``, so ``wallet_credit.drain``
behaved exactly as it had before. This is the switch that makes the free plan
real for accounts that already exist. New accounts get theirs at registration,
from ``wallet_credit.start_first_allowance_period``.

Only rows that have never been on a period are touched (``allowance_period_end
IS NULL``), which makes this idempotent and stops it from resetting a period
already under way or clobbering a subscriber mid-month. Restricted to
``plan = 'free'`` as well, so a paid allowance is only ever granted by the
``invoice.paid`` webhook that proves the card charged.

The amount is written literally rather than read from ``config``. A migration
records what happened at a point in time, so it must not shift later when
``PLAN_ALLOWANCE_MICROS_FREE`` is retuned — the going-forward value belongs to
the config, and every subsequent period is granted by
``roll_allowance_if_due`` reading it.

Downgrade returns those rows to the inert state rather than dropping columns,
which is migration 192's job.

Revision ID: 193
Revises: 192
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "193"
down_revision: str | None = "192"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# $1.00 in micro-USD, matching PLAN_ALLOWANCE_MICROS_FREE at the time of writing.
_FREE_ALLOWANCE_MICROS = 1_000_000


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            """
            UPDATE "user"
               SET credit_micros_allowance = :allowance,
                   allowance_period_end = now() + interval '30 days'
             WHERE plan = 'free'
               AND allowance_period_end IS NULL
            """
        ),
        {"allowance": _FREE_ALLOWANCE_MICROS},
    )


def downgrade() -> None:
    # Cannot tell a backfilled period from one a user has since rolled into, so
    # this clears every free period. The next premium turn re-grants through
    # ``roll_allowance_if_due``, so the effect is a reset rather than a loss.
    op.get_bind().execute(
        sa.text(
            """
            UPDATE "user"
               SET credit_micros_allowance = 0,
                   allowance_period_end = NULL
             WHERE plan = 'free'
            """
        )
    )
