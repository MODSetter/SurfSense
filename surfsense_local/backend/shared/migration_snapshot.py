import contextlib
from pathlib import Path

from sqlalchemy import Engine

# Two, so a failed upgrade and the retry after it still leave the copy from
# before the first attempt.
KEEP = 2


def snapshot_before_upgrade(
    engine: Engine, backups_dir: Path, current: str, head: str
) -> Path:
    """Copy the database to `<backups_dir>/<current>-<head>.db`, or raise.

    The app never migrates a user's only database without a copy to return to.
    """
    target = backups_dir / f"{current}-{head}.db"
    partial = target.with_name(target.name + ".partial")
    try:
        backups_dir.mkdir(parents=True, exist_ok=True)
        partial.unlink(missing_ok=True)
        # Raw, outside any transaction: VACUUM cannot run inside one, and every
        # SQLAlchemy connection here opens with BEGIN IMMEDIATE.
        raw = engine.raw_connection()
        try:
            raw.driver_connection.execute("VACUUM INTO ?", (str(partial),))
        finally:
            raw.close()
        partial.replace(target)
    except Exception as error:
        # Removing the partial file can fail too, as it does beneath a file on
        # macOS and Linux; the copy's failure is the one to report.
        with contextlib.suppress(OSError):
            partial.unlink(missing_ok=True)
        raise RuntimeError(
            f"could not write a database snapshot to {target} before migrating: {error}"
        ) from error
    _prune(backups_dir)
    return target


def _prune(backups_dir: Path) -> None:
    snapshots = sorted(
        backups_dir.glob("*.db"), key=lambda path: path.stat().st_mtime, reverse=True
    )
    for stale in snapshots[KEEP:]:
        stale.unlink(missing_ok=True)
