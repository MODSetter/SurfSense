"""What a job run keeps in its revised copy's metadata: which pack and job, which sources, and
once the worker has run it, the answers' report.

A run is a revised copy whose operations the worker works out first, so Studio shows,
versions and downloads it like any other.
"""

from typing import Any

JOB_RUN_KEY = "job_run"


def job_run_of(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    run = (metadata or {}).get(JOB_RUN_KEY)
    return run if isinstance(run, dict) else None


def pending_job_run(
    *, pack_id: str, pack_version: str, job: str, source_document_ids: list[int]
) -> dict[str, Any]:
    return {
        "pack_id": pack_id,
        "pack_version": pack_version,
        "job": job,
        "source_document_ids": source_document_ids,
        "report": None,
    }
