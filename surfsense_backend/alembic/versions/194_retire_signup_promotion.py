"""retire the signup promotion: expire granted credit, purge the claim ledger

The signup grant is 0 from here on (``DEFAULT_CREDIT_MICROS_BALANCE``), but
that only stops new grants. Roughly 3,500 accounts still hold the old $5 in
``credit_micros_balance``, which is the permanent bucket: nothing in it expires,
it is spent only after the monthly allowance, and it is the reason a free
account had no need of a subscription until the $5 ran out.

**What counts as purchased.** Credit someone paid for is honoured in full. The
balance is clamped to the sum of their ``COMPLETED`` rows in
``credit_purchases``, which covers both checkout and ``auto_reload`` — both are
real charges. Everything above that line was granted, so it goes.

That "everything" deliberately includes incentive-task rewards
(``user_incentive_tasks``) as well as the signup credit. Both are promotional
under the policy this implements, and the two are indistinguishable in the
balance anyway: it is a single integer with no debit ledger, so the only honest
question askable of the data is "how much of this did they pay for?"

Only rows holding more than they paid are touched, which makes this idempotent
— a second run finds nothing above the line.

**The claim ledger.** ``signup_credit_claims`` stores a one-way keyed hash per
person, retained solely to stop delete-and-re-register from re-minting the
grant. With the grant off there is nothing left to farm, so the retention basis
(GDPR Art. 6(1)(f), promotional-abuse prevention, cited in the privacy policy)
no longer holds and the rows are deleted. The table is kept: ``award_signup_credit``
still writes to it if a future promotion is switched on, and an empty table
costs nothing. Note the trade-off — with the hashes gone, anyone who took the
old $5 could claim a future promotion a second time.

Revision ID: 194
Revises: 193
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "194"
down_revision: str | None = "193"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The enum is stored by *name*, not by the lowercase StrEnum value: the column
# is ``SQLAlchemyEnum(CreditPurchaseStatus)`` with no ``values_callable``, so
# the Postgres labels are PENDING/COMPLETED/FAILED. Matching 'completed' here
# would total nothing and expire the balance of every genuine purchaser.
_PURCHASED_MICROS = """
    SELECT u.id AS user_id,
           COALESCE(SUM(cp.credit_micros_granted), 0) AS micros
      FROM "user" u
      LEFT JOIN credit_purchases cp
             ON cp.user_id = u.id
            AND cp.status = 'COMPLETED'
     GROUP BY u.id
"""


def upgrade() -> None:
    conn = op.get_bind()

    expiring = conn.execute(
        sa.text(
            f"""
            WITH purchased AS ({_PURCHASED_MICROS})
            SELECT count(*) AS accounts,
                   COALESCE(SUM(u.credit_micros_balance - purchased.micros), 0) AS micros
              FROM "user" u
              JOIN purchased ON purchased.user_id = u.id
             WHERE u.credit_micros_balance > purchased.micros
            """
        )
    ).one()
    print(
        f"Expiring {expiring.micros} micro-USD of granted credit "
        f"across {expiring.accounts} account(s)."
    )

    conn.execute(
        sa.text(
            f"""
            WITH purchased AS ({_PURCHASED_MICROS})
            UPDATE "user" u
               SET credit_micros_balance = purchased.micros
              FROM purchased
             WHERE purchased.user_id = u.id
               AND u.credit_micros_balance > purchased.micros
            """
        )
    )

    # Table kept, rows dropped: see the note above.
    conn.execute(sa.text("DELETE FROM signup_credit_claims"))


def downgrade() -> None:
    """Deliberately does nothing.

    Neither half is recoverable. The expired amounts were never recorded
    per-account, so restoring them would mean re-minting $5 for every account
    that ever held it — inventing money rather than returning it. The claim
    hashes are one-way and their inputs are not stored anywhere.
    """
