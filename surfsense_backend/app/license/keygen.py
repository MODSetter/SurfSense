"""Minimal Keygen client for producing offline license files.

Keygen is the system of record for licenses: there is no license table, so
every lookup here is a filter over license ``metadata``. See
``plans/community-local/portal/01-license-routes.md``.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Literal

import httpx

from app.config import config

LicensePlan = Literal["trial", "individual", "team"]
_CLOUD_BASE_URL = "https://api.keygen.sh/v1/accounts"
_TIMEOUT_SECONDS = 30.0


def _base_url() -> str:
    return (config.KEYGEN_API_URL or _CLOUD_BASE_URL).rstrip("/")


def _required(value: str | None, name: str) -> str:
    if not value:
        raise RuntimeError(f"{name} is not configured")
    return value


def _policy_for(plan: LicensePlan) -> str:
    return _required(
        {
            "trial": config.KEYGEN_POLICY_TRIAL,
            "individual": config.KEYGEN_POLICY_INDIVIDUAL,
            "team": config.KEYGEN_POLICY_TEAM,
        }[plan],
        f"KEYGEN_POLICY_{plan.upper()}",
    )


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
        "Authorization": f"Bearer {_required(config.KEYGEN_API_TOKEN, 'KEYGEN_API_TOKEN')}",
    }
    if config.KEYGEN_HOST:
        # Self-hosted CE resolves the account from Host, and 308s plain HTTP
        # unless a proxy vouches for it. Missing either one, a call redirects
        # and reads as an empty result rather than as an error.
        headers["Host"] = config.KEYGEN_HOST
        headers["X-Forwarded-Proto"] = "https"
    return headers


def _account_url(path: str) -> str:
    account_id = _required(config.KEYGEN_ACCOUNT_ID, "KEYGEN_ACCOUNT_ID")
    return f"{_base_url()}/{account_id}/{path.lstrip('/')}"


@asynccontextmanager
async def _http(client: httpx.AsyncClient | None):
    if client is not None:
        yield client
        return
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as owned:
        yield owned


class LicenseExistsError(RuntimeError):
    """A license with this id already exists.

    Callers derive the id from the purchase, so this is not a failure but the
    answer to "did someone else already fulfil this?" -- Keygen's uniqueness on
    the id is the only constraint available to a design with no license table.
    See ``app.license.issue``.
    """


async def _raise_if_license_exists(
    response: httpx.Response,
    license_id: str | None,
    client: httpx.AsyncClient | None,
) -> None:
    """Turn Keygen's two rejections of a duplicate id into one signal.

    Keygen answers differently depending on how the duplicate arrives. An id
    that is already committed fails validation with ``422`` and an
    ``ID_CONFLICT`` code. Two creates in flight at once fail at the unique
    index instead, and that answer is a bare ``409`` with no code and a generic
    message -- which is precisely the case this design exists to handle, so
    matching only the ``422`` would miss every real race.

    Since a ``409`` says nothing about *which* conflict it was, confirm the id
    is genuinely taken before reporting it. Guessing would let an unrelated
    conflict masquerade as "your trial is already claimed".
    """
    if license_id is None:
        return

    if response.status_code == 422:
        errors = response.json().get("errors") or []
        if any(error.get("code") == "ID_CONFLICT" for error in errors):
            raise LicenseExistsError(license_id)
        return

    if response.status_code == 409 and await get_license(license_id, client=client):
        raise LicenseExistsError(license_id)


async def create_license(
    plan: LicensePlan,
    email: str,
    max_users: int | None = None,
    *,
    license_id: str | None = None,
    expiry: datetime | None = None,
    extra_metadata: Mapping[str, str] | None = None,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Create a user-less Keygen license and return its id.

    ``metadata`` is the only index we have, so everything a later lookup needs
    goes in it. ``expiry`` overrides the policy duration; the trial route needs
    that to keep the pre-plugin gap week from eating the trial.

    ``license_id`` sets the record's id rather than letting Keygen assign one,
    which is what makes a duplicate fulfilment fail with
    :class:`LicenseExistsError` instead of succeeding twice. The license *key*
    stays Keygen-generated: it is the bearer credential contract 2 sends to the
    scraper API, so it must be unguessable, whereas an id is only a handle.
    """
    metadata: dict[str, str] = {"plan": plan, "email": email}
    if extra_metadata:
        metadata.update({str(k): str(v) for k, v in extra_metadata.items() if v})

    attributes: dict[str, Any] = {"metadata": metadata}
    if plan == "team":
        if max_users is None or max_users < 1:
            raise ValueError("Team licenses require max_users >= 1")
        attributes["maxUsers"] = max_users
    if expiry is not None:
        attributes["expiry"] = expiry.isoformat()

    payload: dict[str, Any] = {
        "data": {
            "type": "licenses",
            "attributes": attributes,
            "relationships": {
                "policy": {
                    "data": {
                        "type": "policies",
                        "id": _policy_for(plan),
                    }
                }
            },
        }
    }
    if license_id:
        payload["data"]["id"] = license_id

    async with _http(client) as http:
        response = await http.post(
            _account_url("licenses"),
            headers=_headers(),
            json=payload,
        )
        await _raise_if_license_exists(response, license_id, client)
        response.raise_for_status()
        return str(response.json()["data"]["id"])


async def get_license(
    license_id: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any] | None:
    """The license with this id, or ``None`` if there is none.

    Resolves the record whatever its state: a refunded buyer's license is
    ``SUSPENDED`` and still occupies its id, and the caller that lost a race
    needs the winner either way.
    """
    async with _http(client) as http:
        response = await http.get(
            _account_url(f"licenses/{license_id}"),
            headers=_headers(),
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        record = response.json().get("data")
        return record if isinstance(record, dict) else None


async def checkout_license(
    license_id: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Check out a non-expiring license file and return its PEM unchanged.

    Certificates are never stored, so this runs once per delivery. Two files
    for one license therefore differ in ``meta.issued`` while carrying the same
    key -- contract 1 requires the app to handle that.
    """
    async with _http(client) as http:
        response = await http.post(
            _account_url(f"licenses/{license_id}/actions/check-out"),
            headers=_headers(),
            json={"meta": {"ttl": None}},
        )
        response.raise_for_status()
        return str(response.json()["data"]["attributes"]["certificate"])


async def list_licenses(
    *,
    metadata: Mapping[str, str] | None = None,
    policy: str | None = None,
    limit: int = 100,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """List licenses matching every given metadata filter.

    Keygen camelCases metadata keys in filter queries, so callers must pass
    ``checkoutSessionId``, not ``checkout_session_id``. A wrong key returns an
    empty list rather than an error, which reads as "no license exists" and
    would issue a duplicate -- which is why this is stated here and covered by
    the live contract test.
    """
    params: dict[str, str] = {"limit": str(limit)}
    for key, value in (metadata or {}).items():
        params[f"metadata[{key}]"] = value
    if policy:
        params["policy"] = policy

    async with _http(client) as http:
        response = await http.get(
            _account_url("licenses"),
            headers=_headers(),
            params=params,
        )
        response.raise_for_status()
        data = response.json().get("data") or []
        return [item for item in data if isinstance(item, dict)]


async def update_license_metadata(
    license_id: str,
    metadata: Mapping[str, str],
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Replace a license's metadata and return the updated attributes.

    Keygen replaces the metadata object wholesale rather than merging, so
    callers must pass every key they want to keep. Support uses this to correct
    a mistyped purchase email: mailing the file to the right address is not
    enough, because the stored address is what ``/license/resend`` looks up --
    leave it wrong and the customer needs support again every time.
    """
    payload = {
        "data": {
            "type": "licenses",
            "attributes": {"metadata": dict(metadata)},
        }
    }
    async with _http(client) as http:
        response = await http.patch(
            _account_url(f"licenses/{license_id}"),
            headers=_headers(),
            json=payload,
        )
        response.raise_for_status()
        return dict(response.json()["data"]["attributes"])


async def suspend_license(
    license_id: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> None:
    """Suspend a license, e.g. after a refund.

    Suspend rather than revoke: it is reversible, it keeps the record listable
    for support, and ``validate-key`` then returns ``SUSPENDED``, which maps
    onto contract 2's ``revoked`` reason. A revoked license is deleted and a
    reversed refund would have nothing to restore.
    """
    async with _http(client) as http:
        response = await http.post(
            _account_url(f"licenses/{license_id}/actions/suspend"),
            headers=_headers(),
        )
        response.raise_for_status()
