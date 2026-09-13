"""In-memory stand-in for the Keygen account.

Keygen is the system of record for licenses -- there is no table -- so nearly
every license test needs to model it rather than a database. This keeps the
metadata-filter semantics the real API has, including that a filter key which
matches nothing returns an empty list.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from itertools import count
from typing import Any


class FakeKeygen:
    """Enough of the Keygen licenses API for the license flows."""

    def __init__(self) -> None:
        self.licenses: dict[str, dict[str, Any]] = {}
        self.suspended: list[str] = []
        self.checkouts: list[str] = []
        self._ids = count(1)

    # -- the four functions app.services.keygen exposes --------------------

    async def create_license(
        self,
        plan: str,
        email: str,
        max_users: int | None = None,
        *,
        expiry: datetime | None = None,
        extra_metadata: Mapping[str, str] | None = None,
        client: Any = None,
    ) -> str:
        license_id = f"lic_{next(self._ids)}"
        metadata: dict[str, str] = {"plan": plan, "email": email}
        if extra_metadata:
            metadata.update({k: str(v) for k, v in extra_metadata.items() if v})
        self.licenses[license_id] = {
            "id": license_id,
            "attributes": {
                "key": f"key-{license_id}",
                "status": "ACTIVE",
                "maxUsers": max_users,
                "expiry": expiry.isoformat() if expiry else None,
                "metadata": metadata,
            },
            "policy": {
                "trial": "policy-trial",
                "individual": "policy-individual",
                "team": "policy-team",
            }[plan],
        }
        return license_id

    async def checkout_license(self, license_id: str, *, client: Any = None) -> str:
        if license_id not in self.licenses:
            raise KeyError(license_id)
        self.checkouts.append(license_id)
        # A fresh checkout each time, as the real one produces: same key, new
        # meta.issued. The counter stands in for that difference.
        return (
            "-----BEGIN LICENSE FILE-----\n"
            f"{license_id}:{self.checkouts.count(license_id)}\n"
            "-----END LICENSE FILE-----\n"
        )

    async def list_licenses(
        self,
        *,
        metadata: Mapping[str, str] | None = None,
        policy: str | None = None,
        limit: int = 100,
        client: Any = None,
    ) -> list[dict[str, Any]]:
        results = []
        for record in self.licenses.values():
            stored = record["attributes"]["metadata"]
            if any(stored.get(k) != v for k, v in (metadata or {}).items()):
                continue
            if policy is not None and record["policy"] != policy:
                continue
            results.append(record)
        return results[:limit]

    async def update_license_metadata(
        self,
        license_id: str,
        metadata: Mapping[str, str],
        *,
        client: Any = None,
    ) -> dict[str, Any]:
        # Keygen replaces metadata wholesale rather than merging; the fake must
        # too, or a test would pass while production silently kept stale keys.
        record = self.licenses[license_id]
        record["attributes"]["metadata"] = dict(metadata)
        return dict(record["attributes"])

    async def suspend_license(self, license_id: str, *, client: Any = None) -> None:
        self.suspended.append(license_id)
        # Real Keygen flips the status, and resend filters on it.
        self.licenses[license_id]["attributes"]["status"] = "SUSPENDED"

    # -- wiring ------------------------------------------------------------

    def install(self, monkeypatch, module) -> FakeKeygen:
        """Point a module's ``keygen`` calls at this fake."""
        for name in (
            "create_license",
            "checkout_license",
            "list_licenses",
            "update_license_metadata",
            "suspend_license",
        ):
            monkeypatch.setattr(module, name, getattr(self, name))
        return self
