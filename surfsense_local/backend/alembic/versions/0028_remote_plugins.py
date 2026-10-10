"""Record connected plugins with their sign-in, their tools, and every call of one.

Remote plugins first; `kind` and the enums carry only what is built, since SQLite
rebuilds a table to widen a check constraint. `plugin_calls` keeps no foreign key
to the plugin: a past call stays in its thread after a disconnect.

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
        sa.Column("publisher", sa.String(), nullable=False),
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
    op.create_table(
        "plugin_calls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=True),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column(
            "caller",
            _enum("plugincaller", "agent", "chat_router", "mention"),
            nullable=False,
        ),
        sa.Column("plugin_id", sa.String(), nullable=False),
        sa.Column("tool", sa.String(), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            _enum(
                "plugincallstatus",
                "waiting_approval",
                "running",
                "succeeded",
                "failed",
                "denied",
                "cancelled",
            ),
            nullable=False,
        ),
        sa.Column("result_text", sa.String(), nullable=True),
        sa.Column("result_data", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_plugin_calls_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plugin_calls")),
    )
    op.create_index("plugin_calls_plugin", "plugin_calls", ["plugin_id"])


def downgrade() -> None:
    op.drop_index("plugin_calls_plugin", table_name="plugin_calls")
    op.drop_table("plugin_calls")
    op.drop_table("plugin_settings")
    op.drop_table("plugin_tools")
    op.drop_table("installed_plugins")
