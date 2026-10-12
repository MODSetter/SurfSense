"""python -m host, from plugins/remote/: serves the plugins on PORT (default 8000).

PLUGINS, a comma-separated list of ids, limits the container to those plugins.
REDIS_URL passes a Stop to the other copies of the host.
"""

import os

import uvicorn

from host.app import host_app
from host.cancel_broadcast import RedisBroadcast

only = os.environ.get("PLUGINS")
redis_url = os.environ.get("REDIS_URL")
app = host_app(
    plugins={plugin.strip() for plugin in only.split(",")} if only else None,
    broadcast=RedisBroadcast(redis_url) if redis_url else None,
)
uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
