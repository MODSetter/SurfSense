# -*- mode: python ; coding: utf-8 -*-
"""Freeze the API sidecar: FastAPI on uvicorn over the shared database.

Chat retrieval embeds the query, so the encoder (onnxruntime, tokenizers) ships;
Docling and torch do not — only the worker parses files — so they are excluded
to keep this binary from carrying a second, unused copy of torch.
"""

import sys

from PyInstaller.utils.hooks import (
    collect_all,
    collect_dynamic_libs,
    collect_submodules,
)

sys.path.insert(0, SPECPATH)
from common import BACKEND, database_inputs

datas, binaries, hiddenimports = database_inputs()

# uvicorn loads its loop, protocol, and lifespan implementations by string.
hiddenimports += collect_submodules("uvicorn")

# The query encoder. onnxruntime's native libs load from C, not an import.
onnx_datas, onnx_binaries, onnx_hidden = collect_all("onnxruntime")
datas += onnx_datas
binaries += onnx_binaries + collect_dynamic_libs("tokenizers")
hiddenimports += onnx_hidden

a = Analysis(
    [str(BACKEND / "main.py")],
    pathex=[str(BACKEND)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["docling", "torch", "torchvision"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="api", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="api")
