"""Which pack a license and an app get for one job (contract 6, producer rule 5)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from license.job_packs.manifest import version_key
from license.job_packs.verify import PublishedPack

Refusal = Literal["unpublished", "not_covered", "needs_newer_app"]


@dataclass(frozen=True)
class Choice:
    pack: PublishedPack | None
    refusal: Refusal | None = None


def choose(
    packs: Iterable[PublishedPack],
    entitlement: str,
    runners: Iterable[str],
    held_jobs: Iterable[str],
) -> Choice:
    """The newest pack with a job for `entitlement` whose every job the license holds
    and whose every runner the app has, else why there is none.

    Coverage comes before runners: an app installs every job of a pack it accepts,
    so a pack holding a job the license lacks is never sent, to any app.
    """
    having = [pack for pack in packs if entitlement in pack.entitlements]
    if not having:
        return Choice(None, "unpublished")
    held = frozenset(held_jobs)
    covered = [pack for pack in having if pack.entitlements <= held]
    if not covered:
        return Choice(None, "not_covered")
    shipped = frozenset(runners)
    runnable = [pack for pack in covered if pack.runners <= shipped]
    if not runnable:
        return Choice(None, "needs_newer_app")
    return Choice(max(runnable, key=lambda pack: (pack.version_key, pack.id)))


def is_current(installed_version: str | None, pack: PublishedPack) -> bool:
    """The app already has this version, or a newer one."""
    return (
        installed_version is not None
        and version_key(installed_version) >= pack.version_key
    )
