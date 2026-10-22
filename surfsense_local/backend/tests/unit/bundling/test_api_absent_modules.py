"""The API role hides exactly the modules an API-only freeze did not collect."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "bundling"))
from api_absent_modules import write_api_absent_modules  # noqa: E402


def _analysis(
    modules: list[str], extensions: list[str] = (), sources: list[str] = ()
) -> SimpleNamespace:
    return SimpleNamespace(
        pure=[(name, f"{name}.py", "PYMODULE") for name in modules],
        binaries=[(path, path, "EXTENSION") for path in extensions],
        datas=[(path, path, "DATA") for path in sources],
    )


def test_a_package_shipped_only_as_source_is_listed(tmp_path: Path) -> None:
    """cv2's hook collects it as .py files beside its extension, not as bytecode."""
    bundle = _analysis([], ["cv2/cv2.pyd"], ["cv2/__init__.py", "cv2/config.py"])

    out = write_api_absent_modules(_analysis([]), bundle, tmp_path / "absent.txt")

    assert out.read_text().split() == ["cv2"]


@pytest.mark.parametrize(
    ("extension", "module"),
    [
        ("win32/win32process.pyd", "win32process"),
        ("python3.12/lib-dynload/_testcapi.cpython-312-darwin.so", "_testcapi"),
        ("python3.12/lib-dynload/_lzma.cpython-312-x86_64-linux-gnu.so", "_lzma"),
    ],
)
def test_an_extension_on_a_sys_path_folder_is_listed_by_its_import_name(
    tmp_path: Path, extension: str, module: str
) -> None:
    """pywin32's folders and lib-dynload are on sys.path: no package above them."""
    bundle = _analysis([], [extension])

    out = write_api_absent_modules(_analysis([]), bundle, tmp_path / "absent.txt")

    assert out.read_text().split() == [module]


def test_only_the_outermost_absent_package_is_listed(tmp_path: Path) -> None:
    """Hiding a package hides its submodules, so they are not listed again."""
    api_only = _analysis(["main_helper", "onnxruntime", "onnxruntime.capi"])
    bundle = _analysis(
        [
            "cv2",
            "main",
            "main_helper",
            "onnxruntime",
            "onnxruntime.capi",
            "onnxruntime.tools",
            "onnxruntime.tools.convert",
            "torch",
            "torch.nn",
        ],
        ["torch/_C.cp312-win_amd64.pyd", "cv2/cv2.abi3.so"],
    )

    out = write_api_absent_modules(api_only, bundle, tmp_path / "absent.txt")

    # main is the API-only analysis's script, imported as a module by the bundle.
    assert out.read_text().split() == ["cv2", "onnxruntime.tools", "torch"]


def test_nothing_is_listed_when_the_api_carried_it_all(tmp_path: Path) -> None:
    """The API role then behaves exactly as the bundle allows."""
    both = _analysis(["fastapi", "fastapi.routing"])

    out = write_api_absent_modules(both, both, tmp_path / "absent.txt")

    assert out.read_text().split() == []
