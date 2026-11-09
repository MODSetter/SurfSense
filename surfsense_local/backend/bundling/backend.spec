# -*- mode: python ; coding: utf-8 -*-
"""Freeze the backend: one binary that runs as the API or as a worker.

Two binaries shared 1,500 identical files that the installer packs one by one,
so each shipped twice. Electron starts this one with a role (frozen_entry.py).
The API role still imports only what an API-only freeze would have carried:
a second, API-only analysis lists the rest, and the API role hides it.
"""

import sys
from pathlib import Path

sys.path.insert(0, SPECPATH)
from api_absent_modules import write_api_absent_modules
from api_inputs import API_ONLY_EXCLUDES, api_inputs
from common import BACKEND
from excluded_modules import EXCLUDED, unused_transformers_models, without_excluded
from torch_bytecode_only import collection_modes
from unused_payload import without_unused_payload
from worker_inputs import worker_inputs

sys.path.insert(0, str(BACKEND))
from frozen_entry import API_ABSENT_MODULES

api_datas, api_binaries, api_hidden = api_inputs()
worker_datas, worker_binaries, worker_hidden = worker_inputs()
api_excluded = EXCLUDED + API_ONLY_EXCLUDES
bundle_excluded = EXCLUDED + unused_transformers_models()

# Only read for its module list; nothing from it ships.
api_only = Analysis(
    [str(BACKEND / "main.py")],
    pathex=[str(BACKEND)],
    binaries=api_binaries,
    datas=api_datas,
    hiddenimports=without_excluded(api_hidden, api_excluded),
    excludes=api_excluded,
)

a = Analysis(
    [str(BACKEND / "frozen_entry.py")],
    pathex=[str(BACKEND)],
    binaries=api_binaries + worker_binaries,
    datas=api_datas + worker_datas,
    hiddenimports=without_excluded(api_hidden + worker_hidden, bundle_excluded),
    excludes=bundle_excluded,
    # Scripts run with MPLBACKEND=Agg; the default would also freeze Tk's GUI.
    hooksconfig={"matplotlib": {"backends": "Agg"}},
    module_collection_mode=collection_modes(),
)
a.binaries = without_unused_payload(a.binaries)
a.datas = without_unused_payload(a.datas)
a.datas.append(
    (
        API_ABSENT_MODULES,
        str(write_api_absent_modules(api_only, a, Path(workpath) / API_ABSENT_MODULES)),
        "DATA",
    )
)

pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="surfsense-backend", console=True)
# Symbols are stripped in build_binaries.py, not here: COLLECT's strip would
# also strip libraries auditwheel rewrote, which then fail to load on Linux.
coll = COLLECT(exe, a.binaries, a.datas, name="backend")
