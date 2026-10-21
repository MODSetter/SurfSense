import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Only files named like a revision are migrations; anything else is never loaded.
MIGRATION_NAME = re.compile(r"^\d{4}_\w+\.py$")
_STAND_ALONE = set(sys.stdlib_module_names) | {"alembic", "sqlalchemy"}


@dataclass(frozen=True)
class SavedScript:
    revision: str
    down_revision: str | None
    # Imports nothing beyond what every release ships, so it can run here.
    stand_alone: bool


def saved_migration_files(migrations_dir: Path) -> list[Path]:
    return sorted(
        path for path in migrations_dir.glob("*.py") if MIGRATION_NAME.match(path.name)
    )


def read_saved_scripts(migrations_dir: Path) -> dict[str, SavedScript]:
    """Each saved migration by revision, read from its source without running it."""
    scripts = {}
    for path in saved_migration_files(migrations_dir):
        script = _read(path)
        if script is not None:
            scripts[script.revision] = script
    return scripts


def _read(path: Path) -> SavedScript | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    # Deep nesting overflows the parser as RecursionError or MemoryError; older
    # Pythons call a null byte a ValueError rather than a SyntaxError.
    except (
        OSError,
        SyntaxError,
        UnicodeDecodeError,
        ValueError,
        RecursionError,
        MemoryError,
    ):
        return None
    values = _module_strings(tree)
    revision = values.get("revision")
    if not isinstance(revision, str):
        return None
    down = values.get("down_revision")
    return SavedScript(
        revision=revision,
        down_revision=down if isinstance(down, str) else None,
        stand_alone=_imported_roots(tree) <= _STAND_ALONE,
    )


def _module_strings(tree: ast.Module) -> dict[str, object]:
    values: dict[str, object] = {}
    for node in tree.body:
        target, value = None, None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        if isinstance(target, ast.Name) and isinstance(value, ast.Constant):
            values[target.id] = value.value
    return values


def _imported_roots(tree: ast.Module) -> set[str]:
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            roots.add(node.module.split(".")[0])
    return roots
