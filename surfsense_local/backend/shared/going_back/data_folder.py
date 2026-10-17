from pathlib import Path


def migrations_dir(data_dir: Path) -> Path:
    return data_dir / "migrations"


def backups_dir(data_dir: Path) -> Path:
    return data_dir / "backups"


def set_aside_dir(data_dir: Path) -> Path:
    # Beneath backups/, not in it: pruning there keeps only two copies.
    return backups_dir(data_dir) / "set-aside"
