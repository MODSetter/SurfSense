"""Every native extension in the frozen bundle still loads.

The release strips symbols from the bundle's libraries on Linux and macOS, and
a library that loses one it links against fails only when it is imported. A
script in the frozen worker imports each extension; an import may fail for an
ordinary reason (an optional dependency left out), so only loader errors count.
"""

import json
import sys
from pathlib import Path

import pytest

from tests.packaging.frozen_backend import frozen_backend
from worker.document_script.run import run_document_script

pytestmark = pytest.mark.packaging

IMPORT_EVERY_EXTENSION = r"""
import importlib, json, os, re, sys
from pathlib import Path

root = Path(sys._MEIPASS)
suffix = re.compile(r"(\.(cp\d+|cpython)[^.]*|\.abi3)?\.(pyd|so)$")
loader = re.compile(r"symbol|shared object|DLL load failed|image not found|Library not loaded", re.I)
tried, broken = 0, {}
for path in sorted(root.rglob("*")):
    if not path.is_file() or not suffix.search(path.name):
        continue
    module = suffix.sub("", path.relative_to(root).as_posix()).replace("/", ".")
    tried += 1
    try:
        importlib.import_module(module)
    except Exception as error:
        if loader.search(str(error)):
            broken[module] = str(error)
Path(os.environ["OUTPUT_PATH"]).write_text(json.dumps({"tried": tried, "broken": broken}))
"""


@pytest.fixture(scope="module")
def frozen(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The backend frozen once for this module."""
    return frozen_backend(tmp_path_factory.mktemp("frozen-backend"))


def test_every_native_extension_loads(
    frozen: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Imported in the frozen worker as a script would import it."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(frozen))

    result = run_document_script(
        IMPORT_EVERY_EXTENSION,
        output_name="extensions.json",
        images={},
        timeout_seconds=600,
    )

    assert result.ok, result.traceback_tail
    report = json.loads(result.output or b"{}")
    assert report["tried"] > 100
    assert report["broken"] == {}
