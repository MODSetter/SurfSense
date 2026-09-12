"""Minimal Keygen client for producing offline license files."""

from __future__ import annotations

from typing import Any, Literal

import httpx

from app.config import config

LicensePlan = Literal["trial", "individual", "team"]
_BASE_URL = "https://api.keygen.sh/v1/accounts"
_TIMEOUT_SECONDS = 30.0


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
    return {
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
        "Authorization": f"Bearer {_required(config.KEYGEN_API_TOKEN, 'KEYGEN_API_TOKEN')}",
    }


def _account_url(path: str) -> str:
    account_id = _required(config.KEYGEN_ACCOUNT_ID, "KEYGEN_ACCOUNT_ID")
    return f"{_BASE_URL}/{account_id}/{path.lstrip('/')}"


async def create_license(
    plan: LicensePlan,
    email: str,
    max_users: int | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Create a user-less Keygen license and return its id."""
    attributes: dict[str, Any] = {
        "metadata": {"plan": plan, "email": email},
    }
    if plan == "team":
        if max_users is None or max_users < 1:
            raise ValueError("Team licenses require max_users >= 1")
        attributes["maxUsers"] = max_users

    payload = {
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

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)
    try:
        response = await client.post(
            _account_url("licenses"),
            headers=_headers(),
            json=payload,
        )
        response.raise_for_status()
        return str(response.json()["data"]["id"])
    finally:
        if owns_client:
            await client.aclose()


async def checkout_license(
    license_id: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Check out a non-expiring license file and return its PEM unchanged."""
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)
    try:
        response = await client.post(
            _account_url(f"licenses/{license_id}/actions/check-out"),
            headers=_headers(),
            json={"meta": {"ttl": None}},
        )
        response.raise_for_status()
        return str(response.json()["data"]["attributes"]["certificate"])
    finally:
        if owns_client:
            await client.aclose()
