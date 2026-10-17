import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic.config import Config

from shared.going_back.saved_scripts import saved_migration_files
from shared.going_back.this_release import ALEMBIC, this_release_config

SHIPPED = ALEMBIC / "versions"


def save_migrations(migrations_dir: Path) -> None:
    """Leave this release's migrations where an older release can run their undo steps.

    An older release was built before these revisions existed. Nothing is
    removed: scripts a later release saved are still needed to go back past it.
    """
    migrations_dir.mkdir(parents=True, exist_ok=True)
    for script in SHIPPED.glob("*.py"):
        shutil.copy2(script, migrations_dir / script.name)


@contextmanager
def with_saved_migrations(migrations_dir: Path) -> Iterator[Config]:
    """This release's migrations, plus the saved ones it was built before.

    Only the ones it lacks: alembic refuses a revision found twice.
    """
    with tempfile.TemporaryDirectory(prefix="surfsense-saved-migrations-") as extra:
        shipped = {script.name for script in SHIPPED.glob("*.py")}
        for script in saved_migration_files(migrations_dir):
            if script.name not in shipped:
                shutil.copy2(script, Path(extra) / script.name)
        config = this_release_config()
        # os.pathsep, not alembic's default of spaces: a Windows profile may hold one.
        config.set_main_option("path_separator", "os")
        config.set_main_option(
            "version_locations", os.pathsep.join([str(SHIPPED), extra])
        )
        yield config
