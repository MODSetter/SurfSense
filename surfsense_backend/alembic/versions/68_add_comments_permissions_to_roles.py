"""Add comments permissions to existing roles

Revision ID: 68
Revises: 67
Create Date: 2024-01-16

"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "68"
down_revision = "67"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()

    # Add comments:create to Admin, Editor, Viewer roles (if not already present)
    connection.execute(
        text(
            """
            UPDATE search_space_roles
            SET permissions = array_append(permissions, 'comments:create')
            WHERE name IN ('Admin', 'Editor', 'Viewer')
            AND NOT ('comments:create' = ANY(permissions))
            """
        )
    )

    # Add comments:read to Admin, Editor, Viewer roles (if not already present)
    connection.execute(
        text(
            """
            UPDATE search_space_roles
            SET permissions = array_append(permissions, 'comments:read')
            WHERE name IN ('Admin', 'Editor', 'Viewer')
            AND NOT ('comments:read' = ANY(permissions))
            """
        )
    )

    # Add comments:delete to Admin roles only (if not already present)
    connection.execute(
        text(
            """
            UPDATE search_space_roles
            SET permissions = array_append(permissions, 'comments:delete')
            WHERE name = 'Admin'
            AND NOT ('comments:delete' = ANY(permissions))
            """
        )
    )


def downgrade():
    connection = op.get_bind()

    # Remove comments:create from Admin, Editor, Viewer roles
    connection.execute(
        text(
            """
            UPDATE search_space_roles
            SET permissions = array_remove(permissions, 'comments:create')
            WHERE name IN ('Admin', 'Editor', 'Viewer')
            """
        )
    )

    # Remove comments:read from Admin, Editor, Viewer roles
    connection.execute(
        text(
            """
            UPDATE search_space_roles
            SET permissions = array_remove(permissions, 'comments:read')
            WHERE name IN ('Admin', 'Editor', 'Viewer')
            """
        )
    )

    # Remove comments:delete from Admin roles only
    connection.execute(
        text(
            """
            UPDATE search_space_roles
            SET permissions = array_remove(permissions, 'comments:delete')
            WHERE name = 'Admin'
            """
        )
    )
