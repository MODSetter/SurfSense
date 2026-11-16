"""The settings a job's config declares: true or false choices the firm makes once for every run,
read the same way whichever runner the job has."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class JobSetting:
    """A choice the firm makes once for every run of the job, off unless it says otherwise."""

    key: str
    label: str
    description: str = ""
    default: bool = False


class DeclaresSettings(Protocol):
    """A runner's config, as the settings, the routes and a run's start read it."""

    settings: tuple[JobSetting, ...]

    @property
    def checks(self) -> bool:
        """Whether the job checks its answers a second time, on the firm's checker model."""
        ...

    def setting_values(
        self, chosen: Mapping[str, object] | None
    ) -> dict[str, bool]: ...


def setting_values(
    settings: tuple[JobSetting, ...], chosen: Mapping[str, object] | None
) -> dict[str, bool]:
    """Every setting the job declares, as the firm chose it or at its default."""
    chosen = dict(chosen or {})
    unknown = sorted(set(chosen) - {s.key for s in settings})
    if unknown:
        raise ValueError(f"The job has no setting {', '.join(unknown)}.")
    values = {}
    for setting in settings:
        value = chosen.get(setting.key, setting.default)
        if not isinstance(value, bool):
            raise ValueError(f"{setting.key} is true or false.")
        values[setting.key] = value
    return values


def declared_settings(raw: Iterable[dict]) -> tuple[JobSetting, ...]:
    """A config's `settings` list; a default that is not true or false is a ValueError."""
    return tuple(
        JobSetting(
            key=str(item["key"]),
            label=str(item["label"]),
            description=str(item.get("description", "")),
            default=_flag(item.get("default", False)),
        )
        for item in raw
    )


def _flag(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError("A setting's default is true or false.")
    return value
