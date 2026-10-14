"""Record connected plugins with their sign-in and their last check, their tools and
why one was switched off on its own, and whether third-party plugins are allowed.

Remote plugins first; `kind` and the enums carry only what is built, since SQLite
rebuilds a table to widen a check constraint. The agent's calls are kept in
opencode's session; a table of calls comes with the chat engine, which has none.

Revision ID: 0028
Revises: 0027
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0028"
down_revision: str | Sequence[str] | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    op.create_table(
        "installed_plugins",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("kind", _enum("pluginkind", "remote"), nullable=False),
        sa.Column(
            "source",
            _enum("pluginsource", "first_party", "registry", "custom"),
            nullable=False,
        ),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("entry", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "connected_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("credential_kind", sa.String(), nullable=True),
        sa.Column("credential_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("checked_at", sa.DateTime(), nullable=True),
        sa.Column("disconnected_at", sa.DateTime(), nullable=True),
        # A license's four come from SurfSense's plugin host, as contract 2 words them.
        sa.Column(
            "check_failure",
            _enum(
                "checkfailure",
                "unreachable",
                "sign_in",
                "needs_license",
                "license_expired",
                "license_revoked",
                "license_invalid",
            ),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_installed_plugins")),
        sa.UniqueConstraint("url", name=op.f("uq_installed_plugins_url")),
    )
    op.create_table(
        "plugin_tools",
        sa.Column("plugin_id", sa.String(), nullable=False),
        sa.Column("tool", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("annotations", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("approval", _enum("toolapproval", "ask", "always"), nullable=False),
        sa.Column(
            "exposure", _enum("toolexposure", "direct", "deferred"), nullable=False
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("change", _enum("toolchange", "added", "changed"), nullable=True),
        sa.ForeignKeyConstraint(
            ["plugin_id"],
            ["installed_plugins.id"],
            name=op.f("fk_plugin_tools_plugin_id_installed_plugins"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("plugin_id", "tool", name=op.f("pk_plugin_tools")),
    )
    op.create_table(
        "plugin_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("third_party_on", sa.Boolean(), nullable=False),
        sa.CheckConstraint("id = 1", name=op.f("ck_plugin_settings_singleton")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plugin_settings")),
    )


def downgrade() -> None:
    op.drop_table("plugin_settings")
    op.drop_table("plugin_tools")
    op.drop_table("installed_plugins")
