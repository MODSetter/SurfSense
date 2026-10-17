"""A release after this one, as far as the database can tell: two revisions more."""

import shutil
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text

from alembic import command
from shared.migration_snapshot import snapshot_before_upgrade

ALEMBIC = Path(__file__).parents[3] / "alembic"


def this_head() -> str:
    """The latest revision this release ships."""
    config = Config()
    config.set_main_option("script_location", str(ALEMBIC))
    head = ScriptDirectory.from_config(config).get_current_head()
    assert head is not None
    return head


def previous_revision() -> str:
    """The revision before this release's head."""
    return _offset(-1)


def newer_head() -> str:
    """The revision the newer release leaves the database at."""
    return _offset(2)


def _offset(by: int) -> str:
    return f"{int(this_head()) + by:04d}"


def save_newer_scripts(migrations_dir: Path, *, first_undo_fails: bool = False) -> None:
    """What the newer release leaves in the data folder: every script it has.

    With `first_undo_fails`, the later revision undoes and the earlier one then
    raises, which strands the database between the two.
    """
    migrations_dir.mkdir(parents=True, exist_ok=True)
    for script in (ALEMBIC / "versions").glob("*.py"):
        shutil.copy2(script, migrations_dir / script.name)
    undo_notes = 'op.drop_table("newer_notes")'
    if first_undo_fails:
        undo_notes += '\n    raise RuntimeError("undo broke")'
    _write_revision(
        migrations_dir / f"{_offset(1)}_newer_notes.py",
        revision=_offset(1),
        down_revision=this_head(),
        upgrade='op.create_table("newer_notes", sa.Column("id", sa.Integer, primary_key=True))',
        downgrade=undo_notes,
    )
    _write_revision(
        migrations_dir / f"{_offset(2)}_newer_pins.py",
        revision=_offset(2),
        down_revision=_offset(1),
        upgrade='op.add_column("newer_notes", sa.Column("pinned", sa.Boolean))',
        downgrade='op.drop_column("newer_notes", "pinned")',
    )


def _write_revision(
    path: Path, *, revision: str, down_revision: str, upgrade: str, downgrade: str
) -> None:
    path.write_text(
        f'''import sqlalchemy as sa

from alembic import op

revision = "{revision}"
down_revision = "{down_revision}"
branch_labels = None
depends_on = None


def upgrade() -> None:
    {upgrade}


def downgrade() -> None:
    {downgrade}
''',
        encoding="utf-8",
    )


def open_with_newer_release(engine: Engine, data_dir: Path) -> None:
    """Migrate the database the way the newer release would on its first start:
    copy it to backups/, migrate it, leave its scripts, then add a row."""
    migrations_dir = data_dir / "migrations"
    save_newer_scripts(migrations_dir)
    snapshot_before_upgrade(engine, data_dir / "backups", this_head(), newer_head())
    config = Config()
    config.set_main_option("script_location", str(ALEMBIC))
    config.set_main_option("path_separator", "os")
    config.set_main_option("version_locations", str(migrations_dir))
    config.attributes["engine"] = engine
    command.upgrade(config, "head")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO newer_notes(id, pinned) VALUES (1, 1)"))
