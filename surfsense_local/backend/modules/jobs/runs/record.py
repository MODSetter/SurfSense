"""What a job run keeps in its revised copy's metadata: which pack and job, which sources, the
firm's settings and checker model as they were when it started, how far it has got, and once
the worker has run it, the answers' report.

A run is a revised copy whose operations the worker works out first, so Studio shows,
versions and downloads it like any other.
"""

from typing import Any

JOB_RUN_KEY = "job_run"
# {"done", "total"} once the worker has found the questions; the screens poll it.
PROGRESS_KEY = "progress"


def job_run_of(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    run = (metadata or {}).get(JOB_RUN_KEY)
    return run if isinstance(run, dict) else None


def pending_job_run(
    *,
    pack_id: str,
    pack_version: str,
    job: str,
    source_document_ids: list[int],
    settings: dict[str, bool] | None = None,
    checker: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "pack_id": pack_id,
        "pack_version": pack_version,
        "job": job,
        "source_document_ids": source_document_ids,
        "settings": settings or {},
        # A text model by provider, name and connection_id; None checks on the answering one.
        "checker": checker,
        PROGRESS_KEY: None,
        "report": None,
    }
