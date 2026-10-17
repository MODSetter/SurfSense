"""An older release runs these scripts, inside code that may lack anything they import."""

import ast
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

VERSIONS = Path(__file__).parents[3] / "alembic" / "versions"
ALLOWED = set(sys.stdlib_module_names) | {"alembic", "sqlalchemy"}


def _imported_roots(script: Path) -> set[str]:
    roots = set()
    for node in ast.walk(ast.parse(script.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize(
    "script", sorted(VERSIONS.glob("*.py")), ids=lambda path: path.stem
)
def test_a_migration_imports_no_app_code(script: Path) -> None:
    """Only the standard library, sqlalchemy and alembic are in every release."""
    assert _imported_roots(script) - ALLOWED == set()
