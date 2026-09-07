# -*- mode: python ; coding: utf-8 -*-
"""Freeze the worker sidecar: the Huey consumer and the full ingest stack.

Ingest embeds chunks (onnxruntime) and parses files (Docling, which pulls torch
and RapidOCR). torch is picked up by PyInstaller's own hook; the packages below
are collected here because their data or native libs are reached by path or by
string, which the analyser cannot follow.
"""

import sys
from importlib.util import find_spec

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

sys.path.insert(0, SPECPATH)
from common import BACKEND, database_inputs

datas, binaries, hiddenimports = database_inputs()

for package in (
    "onnxruntime",
    "docling",
    "docling_core",
    "docling_ibm_models",
    "docling_parse",
    "rapidocr",
    # Transformers exposes AutoImageProcessor through lazy imports, and
    # torchvision loads native extensions dynamically. Neither edge is visible
    # by following Docling's imports, so a source install works while the frozen
    # worker fails only when its first PDF initializes the layout model.
    "transformers",
    "torchvision",
    # Studio builders: python-docx and python-pptx render from template .docx
    # and .pptx files inside their packages, reached by path and invisible to
    # the analyser, so a frozen build would fail on the first Office artifact.
    "docx",
    "pptx",
    # fpdf2 ships its core-font metrics as package data, reached by path.
    "fpdf",
):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

# Podcast is an optional build (`uv sync --extra podcast`). Its engine loads the
# Kokoro ONNX model by path and phonemises through espeak data shipped as package
# files, neither visible to the analyser. Collected only when the extra is
# installed, so a default build skips this untouched and never carries the voice.
for package in ("kokoro_onnx", "espeakng_loader", "phonemizer_fork", "phonemizer"):
    if find_spec(package) is None:
        continue
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

binaries += collect_dynamic_libs("tokenizers")

# Huey resolves a task by its name, so the module that registers it must be in.
hiddenimports += ["modules.documents.tasks", "modules.artifacts.tasks"]

a = Analysis(
    [str(BACKEND / "worker.py")],
    pathex=[str(BACKEND)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="worker", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="worker")
