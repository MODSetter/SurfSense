"""python -m host, from plugins/remote/: serves the plugins on PORT (default 8000).

PLUGINS, a comma-separated list of ids, limits the container to those plugins.
REDIS_URL passes a Stop to the other copies of the host.
PLUGIN_LIFESPANS=off (or 0, false, no) holds no plugin's lifespan: no warm-ups.
Logs are redacted before a plugin loads, so no credential reaches them.
"""

import os

import uvicorn

from host.app import host_app
from host.cancel_broadcast import RedisBroadcast
from host.redacted_logs import redact_every_record

redact_every_record()
only = os.environ.get("PLUGINS")
redis_url = os.environ.get("REDIS_URL")
app = host_app(
    plugins={plugin.strip() for plugin in only.split(",")} if only else None,
    broadcast=RedisBroadcast(redis_url) if redis_url else None,
    lifespans=os.environ.get("PLUGIN_LIFESPANS", "on").strip().lower()
    not in {"off", "0", "false", "no"},
)
uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
