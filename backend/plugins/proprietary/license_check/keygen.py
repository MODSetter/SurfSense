"""Keygen's validate-key action, which needs no token: the key is the credential.

Settings, under the backend's own names and meanings, so a deployment gives both the
same values:

- `KEYGEN_API_URL`: the accounts endpoint, Keygen Cloud's unless set. SurfSense's
  self-hosted Keygen CE is reached inside the deployment, as `http://keygen-web:3000/v1/accounts`.
- `KEYGEN_ACCOUNT_ID`: SurfSense's Keygen account. Not a secret: it is part of every
  validation URL.
- `KEYGEN_HOST`: CE's own hostname, such as `keygen.internal`. CE finds the account
  from `Host` and redirects plain HTTP unless a proxy vouches for it, so when this is
  set it goes as `Host`, with `X-Forwarded-Proto: https`.
"""

import logging
import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx2

from proprietary.scraping.api_clients import api_client

logger = logging.getLogger(__name__)

CLOUD_ACCOUNTS_URL = "https://api.keygen.sh/v1/accounts"
TIMEOUT_SECONDS = 10.0


class KeygenUnreachableError(Exception):
    """No answer about the key: a network failure, Keygen's own 5xx, or a reply that is not one."""


@dataclass(frozen=True)
class Validation:
    """Keygen's `meta.code`, and the license's id from `data.id` when Keygen found one."""

    code: str
    license_id: str | None = None


@dataclass(frozen=True)
class Keygen:
    # Read when made, not when defined, so a test or a deployment's environment sets them.
    api_url: str = field(
        default_factory=lambda: os.environ.get("KEYGEN_API_URL") or CLOUD_ACCOUNTS_URL
    )
    account_id: str = field(
        default_factory=lambda: os.environ.get("KEYGEN_ACCOUNT_ID", "")
    )
    host: str | None = field(
        default_factory=lambda: os.environ.get("KEYGEN_HOST") or None
    )

    def __post_init__(self) -> None:
        if not self.account_id:
            raise ValueError(
                "KEYGEN_ACCOUNT_ID is not set: SurfSense's Keygen account, as the backend's"
            )

    async def validation(self, key: str) -> Validation:
        """Keygen's `meta.code`, such as VALID, EXPIRED or NOT_FOUND, and the license's id.

        Any other answer that is not Keygen's own failure, a 4xx or a redirect, is
        `HTTP_<status>`, which refuses the key as invalid rather than failing the request.
        """
        url = (
            f"{self.api_url.rstrip('/')}/{self.account_id}"
            "/licenses/actions/validate-key"
        )
        headers = {
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json",
        }
        if self.host:
            headers["Host"] = self.host
            headers["X-Forwarded-Proto"] = "https"
        # One kept client: a new one paid a TLS handshake on every check.
        origin = urlsplit(url)
        http = api_client(f"{origin.scheme}://{origin.netloc}")
        try:
            response = await http.post(
                url,
                json={"meta": {"key": key}},
                headers=headers,
                timeout=TIMEOUT_SECONDS,
            )
        except httpx2.TransportError as error:
            raise KeygenUnreachableError(str(error)) from error
        if response.status_code >= 500:
            raise KeygenUnreachableError(f"Keygen answered {response.status_code}")
        if not response.is_success:
            # A wrong account id or address answers 404 for every key, and a
            # self-hosted Keygen redirects without KEYGEN_HOST: worth an operator's look.
            logger.warning(
                "Keygen answered %s to validate-key; the key is refused as invalid",
                response.status_code,
            )
            return Validation(f"HTTP_{response.status_code}")
        try:
            reply = response.json()
            code = reply["meta"]["code"]
        except (ValueError, KeyError, TypeError) as error:
            raise KeygenUnreachableError(
                f"Keygen answered {response.status_code} without a code"
            ) from error
        return Validation(code, _license_id(reply))


def _license_id(reply: object) -> str | None:
    """`data` is null for a key Keygen does not know."""
    data = reply.get("data") if isinstance(reply, dict) else None
    license_id = data.get("id") if isinstance(data, dict) else None
    return license_id if isinstance(license_id, str) and license_id else None
