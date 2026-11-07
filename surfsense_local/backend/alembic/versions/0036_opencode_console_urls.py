"""Move saved OpenCode connections to the Console's documented URLs.

Only an exact old default moves: a proxy or a hand-typed address is the user's.

Revision ID: 0036
Revises: 0035
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0036"
down_revision: str | Sequence[str] | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# provider, old default, documented URL
_MOVES = (
    (
        "opencode",
        "https://opencode.ai/zen/v1",
        "https://opencode.ai/inference/openai/v1",
    ),
    (
        "opencode-go",
        "https://opencode.ai/zen/go/v1",
        "https://opencode.ai/inference/go/openai/v1",
    ),
)


def _move(provider: str, from_url: str, to_url: str) -> None:
    op.execute(
        sa.text(
            "UPDATE provider_connections SET base_url = :to_url "
            "WHERE catalog_provider = :provider AND base_url = :from_url"
        ).bindparams(provider=provider, from_url=from_url, to_url=to_url)
    )


def upgrade() -> None:
    for provider, old, new in _MOVES:
        _move(provider, old, new)


def downgrade() -> None:
    for provider, old, new in _MOVES:
        _move(provider, new, old)
