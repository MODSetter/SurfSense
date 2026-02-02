"""Add public_sharing permissions to existing roles

Revision ID: 86
Revises: 85
Create Date: 2026-02-02

"""

from sqlalchemy import text

from alembic import op

revision = "86"
down_revision = "85"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()

    connection.execute(
        text(
            """
            UPDATE search_space_roles
            SET permissions = array_append(permissions, 'public_sharing:view')
            WHERE name IN ('Editor', 'Viewer')
            AND NOT ('public_sharing:view' = ANY(permissions))
            """
        )
    )

    connection.execute(
        text(
            """
            UPDATE search_space_roles
            SET permissions = array_append(permissions, 'public_sharing:create')
            WHERE name = 'Editor'
            AND NOT ('public_sharing:create' = ANY(permissions))
            """
        )
    )


def downgrade():
    connection = op.get_bind()

    connection.execute(
        text(
            """
            UPDATE search_space_roles
            SET permissions = array_remove(permissions, 'public_sharing:view')
            WHERE name IN ('Editor', 'Viewer')
            """
        )
    )

    connection.execute(
        text(
            """
            UPDATE search_space_roles
            SET permissions = array_remove(permissions, 'public_sharing:create')
            WHERE name = 'Editor'
            """
        )
    )
