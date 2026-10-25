"""python -m server, from backend/ with backend/plugins/ on PYTHONPATH: serves on PORT (default 8000).

PLUGINS, a comma-separated list of ids, limits the container to those plugins.
REDIS_URL passes a Stop to the other copies of the backend.
PLUGIN_LIFESPANS=off (or 0, false, no) holds no plugin's lifespan: no warm-ups.
USAGE_DB_PATH, USAGE_ADMIN_TOKEN, POSTHOG_API_KEY and POSTHOG_HOST set the usage meter.
KEYGEN_API_TOKEN serves the license portal at /api/v1; server/.env.example lists its settings.
Logs are redacted before a plugin loads, so no credential reaches them.
"""

import os

import uvicorn

from host.app import served_plugins
from host.cancel_broadcast import RedisBroadcast
from host.redacted_logs import redact_every_record
from host.usage_meter.meter_settings import MeterSettings
from host.usage_meter.usage_meter import UsageMeter
from license.portal import license_portal
from server.app import backend_app

redact_every_record()
only = os.environ.get("PLUGINS")
redis_url = os.environ.get("REDIS_URL")
usage = MeterSettings.from_env()
plugins = served_plugins(
    plugins={plugin.strip() for plugin in only.split(",")} if only else None,
    broadcast=RedisBroadcast(redis_url) if redis_url else None,
    lifespans=os.environ.get("PLUGIN_LIFESPANS", "on").strip().lower()
    not in {"off", "0", "false", "no"},
    meter=UsageMeter.from_settings(usage),
    usage_admin_token=usage.admin_token,
)
uvicorn.run(
    backend_app(plugins, license_portal()),
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8000")),
)
