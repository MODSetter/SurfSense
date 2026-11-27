"""The committed OpenRouter screen, read, written and folded at the JSON level.

The screen carries provenance extras a Pydantic round-trip drops — each
entry's `runs`, `served_by` and prices, the file's `generated`, `listing`
and `spent` — so it is handled as raw JSON, never through `SweepResults`.
"""

import json
from pathlib import Path
from typing import Any

from capability_list.sweep_input import DONE
from capability_list.sweep_rows import COMMITTED_SCREEN

Screen = dict[str, Any]


def read_screen(path: Path = COMMITTED_SCREEN) -> Screen:
    return json.loads(path.read_text(encoding="utf-8"))


def write_screen(screen: Screen, path: Path = COMMITTED_SCREEN) -> None:
    path.write_text(
        json.dumps(screen, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _finished(entry: Screen) -> bool:
    """Whether its counts are a measurement, as `SweptModel.finished` reads them."""
    status = entry.get("status")
    if status is not None and (status != DONE or entry.get("level") is None):
        return False
    return all(entry.get(field) is not None for field in ("passed", "counted", "run"))


def folded_screen(base: Screen, rerun: Screen) -> Screen:
    """The screen with a re-run folded in, by `rerun.folded`'s rules.

    Entries move whole, extras and all; what the two runs spent adds up,
    and the folded screen is dated by the re-run.
    """
    models = {entry["key"]: entry for entry in base.get("models") or []}
    assumed = {entry["key"]: entry for entry in base.get("assumed") or []}
    for entry in [*(rerun.get("models") or []), *(rerun.get("unfinished") or [])]:
        if _finished(entry):
            models[entry["key"]] = entry
            # A measured verdict replaces the assumption: no stale row
            # beside the measured result.
            assumed.pop(entry["key"], None)
        else:
            # No verdict: the model drops out, and a stale assumption
            # goes with it, as a measured verdict clears one.
            models.pop(entry["key"], None)
            assumed.pop(entry["key"], None)
    # The sweep writes a capped model to `assumed`: its key is the
    # re-run's verdict — out of models, into assumed.
    for entry in rerun.get("assumed") or []:
        models.pop(entry["key"], None)
        assumed[entry["key"]] = entry
    assumed_keys = {entry["key"] for entry in rerun.get("assumed") or []}
    finished = {key for key, entry in models.items() if _finished(entry)}
    unfinished: dict[str, Screen] = {}
    for entry in [*(base.get("unfinished") or []), *(rerun.get("unfinished") or [])]:
        if entry["key"] not in finished and entry["key"] not in assumed_keys:
            unfinished.setdefault(entry["key"], entry)
    folded = dict(base)
    folded["models"] = list(models.values())
    folded["assumed"] = list(assumed.values())
    folded["unfinished"] = list(unfinished.values())
    if rerun.get("date"):
        folded["date"] = rerun["date"]
    spent = [run["spent"] for run in (base, rerun) if run.get("spent") is not None]
    if spent:
        folded["spent"] = sum(spent)
    return folded
