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
                # Forward slashes on every platform, as the specs' targets are.
                found.append(Path(*parts).as_posix())
    return found


@pytest.mark.parametrize("spec", SPECS, ids=lambda p: p.name)
def test_every_bundled_data_path_exists(spec: Path) -> None:
    """A path here that is not on disk ships a binary missing that file."""
    missing = [rel for rel in literal_data_paths(spec) if not (BACKEND / rel).exists()]

    assert missing == [], f"{spec.name} bundles paths that do not exist: {missing}"


@pytest.mark.parametrize("name", ["api.spec", "worker.spec"])
def test_every_binary_that_reads_the_curated_manifest_ships_it(name: str) -> None:
    """Without it the catalog falls back to an empty list: the API shows no
    curated models, and the Studio worker calls an installed, chosen image or
    audio model "not installed"."""
    bundled = literal_data_paths(BACKEND / "bundling" / name)

    assert "modules/llm/catalog/local/manifest/models.json" in bundled


@pytest.mark.parametrize("name", ["api.spec", "worker.spec"])
def test_every_binary_that_reads_the_capability_list_ships_it(name: str) -> None:
    """Without it the API gives no model the agent and Studio ignores what was measured."""
    bundled = literal_data_paths(BACKEND / "bundling" / name)

    assert "modules/llm/capability/measured/capabilities.json" in bundled


def test_the_api_ships_its_release_version() -> None:
    """The registry compares it with each entry's minimum app version."""
    assert (
        'copy_metadata("surfsense-local-backend")'
        in (BACKEND / "bundling" / "api.spec").read_text()
    )


@pytest.mark.parametrize("name", ["api.spec", "worker.spec"])
def test_every_binary_that_reads_the_first_party_plugin_list_ships_it(
    name: str,
) -> None:
    """The API lists SurfSense's plugins; the plugins worker finds the one a link's pull
    calls. The list refuses an entry whose icon is not beside it, so both ship."""
    bundled = literal_data_paths(BACKEND / "bundling" / name)

    assert "modules/plugins/lists/first_party/plugins.json" in bundled
    assert "modules/plugins/lists/first_party/icons" in bundled


def test_the_worker_names_every_module_that_registers_a_task() -> None:
    """Huey runs a job by its task's name, so a frozen worker without the module
    leaves that queue's jobs unrun: links added from the web stayed pending."""
    queue = ast.parse((BACKEND / "shared" / "queue.py").read_text())
    import_tasks = next(
        node
        for node in ast.walk(queue)
        if isinstance(node, ast.FunctionDef) and node.name == "import_tasks"
    )
    registering = {
        alias.name
        for node in ast.walk(import_tasks)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    spec = ast.parse((BACKEND / "bundling" / "worker.spec").read_text())
    named = {
        node.value
        for node in ast.walk(spec)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert registering - named == set()
