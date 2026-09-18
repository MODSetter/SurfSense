# -*- mode: python ; coding: utf-8 -*-
"""Freeze the API sidecar: FastAPI on uvicorn over the shared database.

Chat retrieval embeds the query, so the encoder (onnxruntime, tokenizers) ships;
Docling and torch do not — only the worker parses files — so they are excluded
to keep this binary from carrying a second, unused copy of torch.
"""

import sys

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

sys.path.insert(0, SPECPATH)
from common import BACKEND, database_inputs

datas, binaries, hiddenimports = database_inputs()
datas.append(
    (
            str(BACKEND / "modules" / "llm" / "recommendations" / "curated-models.json"),
        "modules/llm/recommendations",
    )
)
# Read by path, so the analyser cannot see it. Without this every remote model
# reports its capability as unknown in a frozen build only.
datas.append(
    (
        str(BACKEND / "modules" / "llm" / "connections" / "model-capabilities.json"),
        "modules/llm/connections",
    )
)

# Chat's three prompts are read through importlib.resources, not imported.
datas += collect_data_files("modules.chat", includes=["prompts/*.md"])

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
    # 260 MB of dependencies the analyser cannot tell are optional: chonkie
    # names transformers only under TYPE_CHECKING and imports pandas inside
    # TableChef, and those two then reach opencv and scipy. Chunking here is
    # RecursiveChunker over the Rust tokenizer, which touches none of them.
    # onnxruntime's model-conversion tooling arrives the same way via collect_all;
    # retrieval only builds an InferenceSession, which lives in onnxruntime.capi.
    excludes=[
        "docling",
        "torch",
        "torchvision",
        "cv2",
        "pandas",
        "scipy",
        "transformers",
        "onnxruntime.transformers",
        "onnxruntime.quantization",
        "onnxruntime.tools",
    ],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="api", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="api")
