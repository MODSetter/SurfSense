"""What a pack must be, besides signed, to take the installed one's place (contract 6, consumer
rule 5): a download must be the job asked for, hold no job the licence lacks and be newer; an
import may be the same version, the same signed pack again. Neither replaces a pack while a run
of it is under way."""

from __future__ import annotations

from collections.abc import Callable

from modules.jobs.packs.install import Accept
from modules.jobs.packs.manifest import PackManifest, PackRefusedError, version_key

# Whether a run of the pack with this id is pending or processing.
InUse = Callable[[str], bool]


def accept_delivered(
    entitlement: str, held_jobs: frozenset[str], in_use: InUse
) -> Accept:
    def accept(new: PackManifest, installed: list[PackManifest]) -> None:
        if not any(job.entitlement == entitlement for job in new.jobs):
            raise PackRefusedError(
                "PACK_WRONG_JOB",
                f"{new.name} {new.version} has no job for {entitlement}.",
            )
        if any(
            job.entitlement is None or job.entitlement not in held_jobs
            for job in new.jobs
        ):
            raise PackRefusedError(
                "PACK_NOT_INCLUDED",
                f"{new.name} {new.version} holds a job this license does not include.",
            )
        # Any id: one id per job is the publisher's rule, so another id is never newer.
        current = [
            pack
            for pack in installed
            if any(job.entitlement == entitlement for job in pack.jobs)
        ]
        newest = max(current, key=lambda pack: version_key(pack.version), default=None)
        if newest is not None and version_key(newest.version) >= version_key(
            new.version
        ):
            raise PackRefusedError(
                "PACK_NOT_NEWER",
                f"{new.name} {new.version} is not newer than the installed "
                f"{newest.name} {newest.version}.",
            )
        _refuse_in_use(new, in_use)

    return accept


def accept_imported(in_use: InUse) -> Accept:
    def accept(new: PackManifest, installed: list[PackManifest]) -> None:
        same = next((pack for pack in installed if pack.id == new.id), None)
        if same is not None and version_key(same.version) > version_key(new.version):
            raise PackRefusedError(
                "PACK_OLDER",
                f"This is {new.name} {new.version}, older than the installed "
                f"{same.version}.",
            )
        _refuse_in_use(new, in_use)

    return accept


def _refuse_in_use(new: PackManifest, in_use: InUse) -> None:
    if in_use(new.id):
        raise PackRefusedError(
            "PACK_IN_USE",
            f"A run of {new.name} is under way, so it is not replaced until the run ends.",
        )
