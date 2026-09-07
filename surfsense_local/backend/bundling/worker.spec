# -*- mode: python ; coding: utf-8 -*-
"""Freeze the worker sidecar: the Huey consumer and the full ingest stack.

Ingest embeds chunks (onnxruntime) and parses files (Docling, which pulls torch
and RapidOCR). torch is picked up by PyInstaller's own hook; the packages below
are collected here because their data or native libs are reached by path or by
string, which the analyser cannot follow.
"""

import sys

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
)

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
    # Studio document formats: the model writes python-docx/pptx/xlsxwriter/
    # reportlab code (worker/studio/office/) that the worker runs, so none are
    # imported statically anymore — the analyser cannot see them, and each also
    # reaches package data by path (Office templates, reportlab core fonts).
    "docx",
    "pptx",
    "xlsxwriter",
    "reportlab",
    # Studio podcast: kokoro-onnx loads its ONNX model by path and phonemises
    # through espeak data shipped as package files, neither visible to the
    # analyser. espeakng_loader carries the espeak-ng-data; phonemizer is its g2p.
    "kokoro_onnx",
    "espeakng_loader",
    "phonemizer",
):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

binaries += collect_dynamic_libs("tokenizers")

# The per-format SKILL.md files (worker/studio/office/*/) are read at import via
# importlib.resources, so the analyser does not see them as source.
datas += collect_data_files("worker.studio.office", includes=["**/*.md"])

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
