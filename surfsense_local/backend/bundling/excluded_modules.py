"""Modules that reach the bundle through imports no shipped code path runs."""

from pathlib import Path

from PyInstaller.utils.hooks import get_package_paths
from worker_inputs import TRANSFORMERS_MODELS_USED

EXCLUDED = [
    # Dev tooling the freezing environment carries.
    "pytest",
    "_pytest",
    "py",
    "iniconfig",
    # pywin32's MFC GUI (mfc140u.dll), pulled in by win32com.client.makepy.
    # win32com, pythoncom and win32api stay: torch, mcp and mpire use them.
    "win32ui",
    "pywin",
    # huggingface_hub's Xet transfer: the app runs with HF_HUB_OFFLINE=1 and
    # downloads nothing through the Hub.
    "hf_xet",
    # Docling's DocumentExtractor fills a Pydantic template with them; the app
    # never builds one. Do not exclude pluggy: Docling's model factories use it.
    "faker",
    "polyfactory",
    # onnxruntime's model-conversion tooling; everything here only builds an
    # InferenceSession, which lives in onnxruntime.capi.
    "onnxruntime.transformers",
    "onnxruntime.quantization",
    "onnxruntime.tools",
]


def without_excluded(hiddenimports: list[str], excluded: list[str]) -> list[str]:
    """collect_all names every submodule, the excluded ones too; PyInstaller
    then logs each as a missing hidden import."""
    return [
        name
        for name in hiddenimports
        if not any(name == gone or name.startswith(gone + ".") for gone in excluded)
    ]


def unused_transformers_models() -> list[str]:
    """Every transformers model family but the ones Docling's layout engine loads.

    Listed from the installed package, so a transformers upgrade that adds a
    family does not quietly ship it.
    """
    _, package = get_package_paths("transformers")
    models = Path(package) / "models"
    return [
        f"transformers.models.{family.name}"
        for family in sorted(models.iterdir())
        if (family / "__init__.py").is_file()
        and family.name not in TRANSFORMERS_MODELS_USED
    ]
