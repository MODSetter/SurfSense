"""Every data file the spec bundles has to exist on disk.

PyInstaller is forgiving here: a `datas` entry naming a path that is not there
produces a warning in a long build log and a binary that is missing the file,
which then fails at runtime on a user's machine and nowhere else. The catalog
manifest reached exactly that state once, when the module it lived in was
renamed and the spec was not.

A unit test cannot catch it, because nothing imports the spec. This reads it the
way PyInstaller does, as Python, with the globals it expects.
"""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.packaging

BACKEND = Path(__file__).resolve().parents[2]
SPECS = sorted((BACKEND / "bundling").glob("*.spec"))


def literal_data_paths(spec: Path) -> list[str]:
    """The source paths in `datas.append((...))` calls that are plain strings.

    Only the literal ones: an entry built by `collect_data_files` is resolved by
    PyInstaller at build time and is not ours to check.
    """
    tree = ast.parse(spec.read_text())
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "append" or not node.args:
            continue
        first = node.args[0]
        if not isinstance(first, ast.Tuple) or not first.elts:
            continue
        source = first.elts[0]
        # str(BACKEND / "a" / "b"): recover the parts of the division chain.
        if isinstance(source, ast.Call) and getattr(source.func, "id", None) == "str":
            parts = []
            current = source.args[0]
            while isinstance(current, ast.BinOp) and isinstance(current.op, ast.Div):
                if isinstance(current.right, ast.Constant):
                    parts.insert(0, str(current.right.value))
                current = current.left
            if parts and getattr(current, "id", None) == "BACKEND":
                found.append(str(Path(*parts)))
    return found


@pytest.mark.parametrize("spec", SPECS, ids=lambda p: p.name)
def test_every_bundled_data_path_exists(spec: Path) -> None:
    """A path here that is not on disk ships a binary missing that file."""
    missing = [rel for rel in literal_data_paths(spec) if not (BACKEND / rel).exists()]

    assert missing == [], f"{spec.name} bundles paths that do not exist: {missing}"


def test_the_curated_manifest_is_one_of_them() -> None:
    """The file that was missed. Without it a frozen build has no curated list,
    and the model screen is empty on the machine that most needs it."""
    bundled = {rel for spec in SPECS for rel in literal_data_paths(spec)}

    assert "modules/llm/catalog/curated-models.json" in bundled
