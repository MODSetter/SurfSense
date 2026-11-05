"""What Keygen says of a key, and the jobs its license lists, for the job pack route.

Unscoped, as the product token. Only VALID gets a pack: unlike the refresh, an
expired license gets nothing, so this never reuses `fresh_file.deliverable`.
"""

from __future__ import annotations

from dataclasses import dataclass

from license import keygen
from license.jobs import jobs_of


@dataclass(frozen=True)
class LicenseVerdict:
    code: str
    jobs: tuple[str, ...] = ()


async def license_verdict(key: str) -> LicenseVerdict:
    """Keygen's code for the key, `NOT_FOUND` with no license; Keygen's errors propagate."""
    validation = await keygen.validate_key(key)
    record = validation.record or {}
    if not record.get("id"):
        return LicenseVerdict("NOT_FOUND")
    attributes = record.get("attributes")
    metadata = attributes.get("metadata") if isinstance(attributes, dict) else None
    return LicenseVerdict(
        validation.code or "NOT_FOUND",
        jobs_of(metadata if isinstance(metadata, dict) else {}),
    )
