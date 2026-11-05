"""Create the Business policies and the job entitlements in Keygen, idempotently.

    python -m license.scripts.setup_business_policies --dry-run
    python -m license.scripts.setup_business_policies
    python -m license.scripts.setup_business_policies --product-token

Run it once with the admin token in KEYGEN_API_TOKEN: entitlements and product
tokens are the two things a product token cannot create. A second run without
``--product-token`` creates only what is missing, such as a job added to
``license/jobs.py``. Each run with it makes another product token, valid until
it is revoked in Keygen, so pass it once and revoke any token it replaces.

The live trial, individual and team policies are read, never written: the
plugin host accepts only VALID, so editing one, or making it strict, would lock
out every key on it. The Business policies join their product, so one product
token reads every license.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import httpx2

from license import keygen
from license.jobs import JOBS
from license.settings import config

# Names our policies in their metadata, so a rename in Keygen does not make a
# second run create them again.
MARKER = "surfsensePolicy"


@dataclass(frozen=True, slots=True)
class PolicySpec:
    name: str
    # The fallback for a license made without an expiry; the server always sets one.
    duration: timedelta


POLICIES: dict[str, PolicySpec] = {
    "business": PolicySpec("Business", timedelta(days=365 + 30)),
    "business-trial": PolicySpec("Business trial", timedelta(days=14)),
}


class SetupError(RuntimeError):
    """Something an operator has to fix before the setup can go on."""


def _snake(key: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()


def _marker_of(policy: dict[str, Any]) -> str | None:
    metadata = (policy.get("attributes") or {}).get("metadata") or {}
    # Keygen stores keys snake-cased and answers camelCased.
    for key, value in metadata.items():
        if _snake(key) == _snake(MARKER):
            return str(value)
    return None


def _product_of(policy: dict[str, Any]) -> str | None:
    product = ((policy.get("relationships") or {}).get("product") or {}).get("data")
    return str(product.get("id")) if isinstance(product, dict) else None


async def _call(
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    response = await keygen.account_request(method, path, json=json, params=params)
    if response.status_code in {401, 403}:
        raise SetupError(
            f"Keygen refused {method} {path} ({response.status_code}): run this with "
            "the admin token in KEYGEN_API_TOKEN"
        )
    response.raise_for_status()
    return response.json() if response.content else {}


async def _every(path: str, params: dict[str, str] | None = None) -> list[dict]:
    found: list[dict] = []
    page = 1
    while True:
        body = await _call(
            "GET",
            path,
            params={**(params or {}), "page[size]": "100", "page[number]": str(page)},
        )
        data = [item for item in body.get("data") or [] if isinstance(item, dict)]
        found.extend(data)
        links = body.get("links")
        if len(data) < 100 or (isinstance(links, dict) and not links.get("next")):
            return found
        page += 1


def _policy_payload(
    plan: str, spec: PolicySpec, product: str, scheme: str | None
) -> dict[str, Any]:
    attributes: dict[str, Any] = {
        "name": spec.name,
        "duration": int(spec.duration.total_seconds()),
        # Never strict: the server creates no machines, and a strict policy
        # answers NO_MACHINE for every key, which the plugin host refuses.
        "strict": False,
        # People, not devices (ADR 0080): no node-lock for a later activation
        # scheme to inherit.
        "floating": True,
        "maxMachines": None,
        "expirationStrategy": "RESTRICT_ACCESS",
        "metadata": {MARKER: plan},
    }
    if scheme:
        # The live policies' scheme gives the file `alg` the app accepts.
        attributes["scheme"] = scheme
    return {
        "data": {
            "type": "policies",
            "attributes": attributes,
            "relationships": {"product": {"data": {"type": "products", "id": product}}},
        }
    }


async def _live_product() -> tuple[str, str | None]:
    """The one product the live policies share, and the scheme to mirror."""
    live = {
        "KEYGEN_POLICY_INDIVIDUAL": config.KEYGEN_POLICY_INDIVIDUAL,
        "KEYGEN_POLICY_TRIAL": config.KEYGEN_POLICY_TRIAL,
        "KEYGEN_POLICY_TEAM": config.KEYGEN_POLICY_TEAM,
    }
    # Every one: a live policy left unread could be on another product.
    unset = [setting for setting, policy_id in live.items() if not policy_id]
    if unset:
        raise SetupError(
            f"Set {', '.join(unset)}: the Business policies join the product all "
            "three live policies share"
        )
    policies = {
        setting: (await _call("GET", f"policies/{policy_id}"))["data"]
        for setting, policy_id in live.items()
    }
    products = {_product_of(policy) for policy in policies.values()}
    if len(products) != 1 or None in products:
        raise SetupError(
            "The live policies belong to more than one product, and a product token "
            "reads only its own product's licenses; move them under one product first"
        )
    template = next(iter(policies.values()))
    scheme = (template.get("attributes") or {}).get("scheme")
    return str(products.pop()), scheme or None


async def setup(*, dry_run: bool = False, product_token: bool = False) -> list[str]:
    """Create what is missing and return the settings lines for the backend."""
    product, scheme = await _live_product()
    print(f"product          {product}")

    ours: dict[str, dict] = {}
    for policy in await _every("policies", {"product": product}):
        marker = _marker_of(policy)
        if marker in POLICIES:
            ours[marker] = policy
    for plan, policy in ours.items():
        if (policy.get("attributes") or {}).get("strict"):
            raise SetupError(
                f"Policy {policy['id']} ({plan}) is strict, so every key on it would "
                "fail validation; make it non-strict in Keygen, then run this again"
            )

    policy_ids: dict[str, str] = {}
    for plan, spec in POLICIES.items():
        if plan in ours:
            policy_ids[plan] = str(ours[plan]["id"])
            print(f"policy {plan:<15} {policy_ids[plan]}  exists")
        elif dry_run:
            print(f"policy {plan:<15} would be created")
        else:
            created = await _call(
                "POST", "policies", json=_policy_payload(plan, spec, product, scheme)
            )
            policy_ids[plan] = str(created["data"]["id"])
            print(f"policy {plan:<15} {policy_ids[plan]}  created")

    existing = {
        str((item.get("attributes") or {}).get("code") or "").upper(): str(item["id"])
        for item in await _every("entitlements")
    }
    entitlement_ids: dict[str, str] = {}
    for code, name in JOBS.items():
        if code in existing:
            entitlement_ids[code] = existing[code]
            print(f"job {code:<18} {existing[code]}  exists")
        elif dry_run:
            print(f"job {code:<18} would be created")
        else:
            created = await _call(
                "POST",
                "entitlements",
                json={
                    "data": {
                        "type": "entitlements",
                        "attributes": {"name": name, "code": code},
                    }
                },
            )
            entitlement_ids[code] = str(created["data"]["id"])
            print(f"job {code:<18} {entitlement_ids[code]}  created")

    for plan, policy_id in policy_ids.items():
        attached = {
            str(item["id"])
            for item in await _every(f"policies/{policy_id}/entitlements")
        }
        missing = [eid for eid in entitlement_ids.values() if eid not in attached]
        if not missing:
            continue
        if dry_run:
            print(f"policy {plan:<15} would get {len(missing)} job(s)")
            continue
        await _call(
            "POST",
            f"policies/{policy_id}/entitlements",
            json={"data": [{"type": "entitlements", "id": eid} for eid in missing]},
        )
        print(f"policy {plan:<15} got {len(missing)} job(s)")

    lines = [
        f"KEYGEN_POLICY_{plan.upper().replace('-', '_')}={policy_id}"
        for plan, policy_id in policy_ids.items()
    ]
    if product_token and not dry_run:
        token = await _call(
            "POST",
            f"products/{product}/tokens",
            json={
                "data": {
                    "type": "tokens",
                    "attributes": {"name": "SurfSense license server"},
                }
            },
        )
        lines.append(f"KEYGEN_API_TOKEN={token['data']['attributes']['token']}")
    return lines


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--dry-run", action="store_true", help="Say what would be created"
    )
    parser.add_argument(
        "--product-token",
        action="store_true",
        help=(
            "Also create the license server's product token, shown once. Each run "
            "with this makes another, valid until it is revoked in Keygen: pass it "
            "once and revoke any token it replaces"
        ),
    )
    args = parser.parse_args()
    try:
        lines = await setup(dry_run=args.dry_run, product_token=args.product_token)
    except (SetupError, RuntimeError, httpx2.HTTPError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if lines:
        print("\nSet these on the backend:")
        print("\n".join(lines))
    if any(line.startswith("KEYGEN_API_TOKEN=") for line in lines):
        print(
            "\nThe token is shown once: put it in the secret store now, and keep the "
            "admin token offline."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
