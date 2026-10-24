"""The usage meter's settings, from the environment the host runs in."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

# Under the working directory: /srv/remote/usage/ in the image, a volume in production.
DEFAULT_DB_PATH = "usage/plugin-usage.sqlite3"
DEFAULT_POSTHOG_HOST = "https://us.i.posthog.com"


@dataclass(frozen=True)
class MeterSettings:
    db_path: Path
    # Unset, the admin routes are not served.
    admin_token: str | None
    # Unset, no rollup leaves the host.
    posthog_api_key: str | None
    posthog_host: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "MeterSettings":
        return cls(
            Path(env.get("USAGE_DB_PATH") or DEFAULT_DB_PATH),
            env.get("USAGE_ADMIN_TOKEN") or None,
            env.get("POSTHOG_API_KEY") or None,
            env.get("POSTHOG_HOST") or DEFAULT_POSTHOG_HOST,
        )
