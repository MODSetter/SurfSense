"""Record when each plugin's server was last checked and why that failed, and why a
tool was switched off on its own, so Settings can say so.

Columns are added by plain ALTER TABLE: op.add_column drops a column-level CHECK on
SQLite, and a batch rebuild of `installed_plugins` would cascade through `plugin_tools`.

Revision ID: 0029
Revises: 0028
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0029"
down_revision: str | Sequence[str] | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE installed_plugins ADD COLUMN checked_at DATETIME"))
    op.execute(
        sa.text(
            "ALTER TABLE installed_plugins ADD COLUMN check_failure VARCHAR(11) "
            "CONSTRAINT ck_installed_plugins_checkfailure "
            "CHECK (check_failure IN ('unreachable', 'sign_in'))"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE plugin_tools ADD COLUMN change VARCHAR(7) "
            "CONSTRAINT ck_plugin_tools_toolchange "
            "CHECK (change IN ('added', 'changed'))"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE plugin_tools DROP COLUMN change"))
    op.execute(sa.text("ALTER TABLE installed_plugins DROP COLUMN check_failure"))
    op.execute(sa.text("ALTER TABLE installed_plugins DROP COLUMN checked_at"))
