"""Add automations permissions to existing Editor/Viewer roles

Revision ID: 145
Revises: 144
Create Date: 2026-05-27

Owners already have ``*`` and need no backfill. Custom (non-system) roles
are left untouched on purpose: workspace admins manage those explicitly.
"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "145"
down_revision: str | None = "144"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_EDITOR_PERMISSIONS = (
    "automations:create",
    "automations:read",
    "automations:update",
    "automations:execute",
)
_VIEWER_PERMISSIONS = ("automations:read",)


def upgrade():
    connection = op.get_bind()

    for permission in _EDITOR_PERMISSIONS:
        connection.execute(
            text(
                """
                UPDATE search_space_roles
                SET permissions = array_append(permissions, :permission)
                WHERE name = 'Editor'
                AND NOT (:permission = ANY(permissions))
                """
            ),
            {"permission": permission},
        )

    for permission in _VIEWER_PERMISSIONS:
        connection.execute(
            text(
                """
                UPDATE search_space_roles
                SET permissions = array_append(permissions, :permission)
                WHERE name = 'Viewer'
                AND NOT (:permission = ANY(permissions))
                """
            ),
            {"permission": permission},
        )


def downgrade():
    connection = op.get_bind()

    for permission in _EDITOR_PERMISSIONS:
        connection.execute(
            text(
                """
                UPDATE search_space_roles
                SET permissions = array_remove(permissions, :permission)
                WHERE name = 'Editor'
                """
            ),
            {"permission": permission},
        )

    for permission in _VIEWER_PERMISSIONS:
        connection.execute(
            text(
                """
                UPDATE search_space_roles
                SET permissions = array_remove(permissions, :permission)
                WHERE name = 'Viewer'
                """
            ),
            {"permission": permission},
        )
