"""The module's internals stay inside the module.

Callers reach the store through :class:`KnowledgeStore` and the public
``schemas``/``paths`` surface. The transaction, the engines, and the path
submodules are internal: reaching past the facade is how a second writer or a
second path spelling creeps back in, so this pins the door shut.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_APP = Path(__file__).resolve().parents[3] / "app"
_MODULE = _APP / "knowledge_store"

#: Imports only the module itself may reach for.
_FORBIDDEN = re.compile(
    r"""^\s*(?:from|import)\s+app\.knowledge_store\.(?:
        transaction
        | engines
        | paths\.(?:store_path|naming|layout|resolve|legacy)
    )\b
    | ^\s*from\s+app\.knowledge_store\s+import\s+[^\n]*\bTransaction\b
    """,
    re.VERBOSE,
)


def _outside_module() -> list[Path]:
    return [p for p in _APP.rglob("*.py") if _MODULE not in p.parents]


def test_no_module_outside_the_store_reaches_its_internals():
    violations: list[str] = []
    for path in _outside_module():
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if _FORBIDDEN.search(line):
                violations.append(f"{path.relative_to(_APP)}:{number}: {line.strip()}")
    assert not violations, "reach past the facade:\n" + "\n".join(violations)
