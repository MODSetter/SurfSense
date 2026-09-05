# -*- mode: python ; coding: utf-8 -*-
"""Freeze the worker sidecar: the Huey consumer and the full ingest stack.

Ingest embeds chunks (onnxruntime) and parses files (Docling, which pulls torch
and RapidOCR). torch is picked up by PyInstaller's own hook; the packages below
are collected here because their data or native libs are reached by path or by
string, which the analyser cannot follow.
"""

import sys

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
):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

binaries += collect_dynamic_libs("tokenizers")

# Huey resolves a task by its name, so the module that registers it must be in.
hiddenimports += ["modules.documents.tasks"]

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
