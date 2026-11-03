"""A job's firm settings: what its pack declares, as the firm chose it, and the checker model.

A run copies them when it starts, so a change made while it answers applies to the next run.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.jobs.settings.models import JobSettings
from modules.jobs.workbook_rows.config import JobConfig
from modules.llm.model_route.schemas import ModelRef
from modules.llm.models import ProviderConnection
from modules.llm.providers import llamacpp

REMOTE = "openai_compatible"


class JobSettingsRefusedError(ValueError):
    """Settings the job cannot take, said in a sentence for the user."""


@dataclass(frozen=True)
class ChosenSettings:
    values: dict[str, bool]  # every setting the job declares
    checker: ModelRef | None  # None checks on the answering model


def job_settings(session: Session, job: str, config: JobConfig) -> ChosenSettings:
    """The firm's settings for `job`, each one the pack no longer declares left out."""
    row = session.get(JobSettings, job)
    stored = dict(row.settings or {}) if row is not None else {}
    declared = {s.key for s in config.settings}
    try:
        values = config.setting_values(
            {k: v for k, v in stored.items() if k in declared}
        )
    except ValueError:
        values = config.setting_values({})
    checker = (
        ModelRef.model_validate(row.checker)
        if row is not None and row.checker
        else None
    )
    return ChosenSettings(values, checker)


def save_job_settings(
    session: Session,
    job: str,
    config: JobConfig,
    settings: dict[str, object],
    checker: ModelRef | None,
) -> ChosenSettings:
    try:
        values = config.setting_values(settings)
    except ValueError as refused:
        raise JobSettingsRefusedError(str(refused)) from refused
    if checker is not None:
        _check_model(session, checker)
    row = session.get(JobSettings, job)
    if row is None:
        row = JobSettings(job=job)
        session.add(row)
    row.settings = values
    row.checker = checker.model_dump() if checker is not None else None
    session.flush()
    return ChosenSettings(values, checker)


def _check_model(session: Session, model: ModelRef) -> None:
    """A text model the app can reach: the local runtime, or a remote connection that exists.
    Whether it is installed or allowed out is the model route's to say when a run asks it."""
    if model.provider == llamacpp.PROVIDER:
        if model.connection_id is not None:
            raise JobSettingsRefusedError("A local model has no connection.")
    elif model.provider == REMOTE:
        if model.connection_id is None or (
            session.get(ProviderConnection, model.connection_id) is None
        ):
            raise JobSettingsRefusedError(
                f"There is no connection {model.connection_id} for the checker."
            )
    else:
        raise JobSettingsRefusedError(
            f"The checker is a local model or one on a connection, not {model.provider}."
        )
    if not model.name.strip():
        raise JobSettingsRefusedError("Name the checker model.")
