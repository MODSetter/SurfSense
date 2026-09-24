"""Name a local image selection by its build, as the manifest does.

Revision ID: 0015
Revises: 0014
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen here: a migration must not read the manifest, which will change.
OLD_TO_NEW = {
    "stable-diffusion-1.5": "v1-5-pruned_Q4_0",
    "sdxl-base-1.0": "sd_xl_base_1.0_0_Q4_0",
    "sdxl-turbo": "stable-diffusion-xl-1.0-turbo-Q4_0",
}

_RENAME = sa.text(
    "UPDATE selected_models SET name = :to "
    "WHERE provider = 'sdcpp' AND model_type = 'image_gen' AND name = :from_"
)


def upgrade() -> None:
    for old, new in OLD_TO_NEW.items():
        op.execute(_RENAME.bindparams(from_=old, to=new))


def downgrade() -> None:
    for old, new in OLD_TO_NEW.items():
        op.execute(_RENAME.bindparams(from_=new, to=old))
