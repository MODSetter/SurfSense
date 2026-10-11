"""python -m host, from plugins/remote/: serves every plugin on PORT (default 8000)."""

import os

import uvicorn

from host.app import host_app

uvicorn.run(host_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
