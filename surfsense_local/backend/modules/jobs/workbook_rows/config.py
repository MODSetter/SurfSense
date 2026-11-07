"""What a workbook-rows job brings in its pack: its answers, how to find its questions, and its prompts.

The runner is the app's; everything here is the job's own content, read from the pack.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from modules.artifacts.revised_copies.engines.excel_new_sheet import name_problem
from modules.jobs.packs.manifest import PackRefusedError, safe_path
from modules.jobs.settings.declared import (
    JobSetting,
    declared_settings,
    setting_values,
)


@dataclass(frozen=True)
class AnswerChoice:
    answer: str  # the job's own word, such as "Yes" or "Needs review"
    needs_quote: bool  # given only with a passage that is really in a source
    cell_values: tuple[
        str, ...
    ]  # how a requester's dropdown may spell it, first preferred
    fallback: bool = False  # what an answer becomes when its quote is not found


@dataclass(frozen=True)
class LayoutWords:
    """Header words, lower case, that name a table's columns."""

    question: tuple[str, ...]
    answer: tuple[str, ...]
    comment: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    context: tuple[str, ...] = ()  # columns worth telling the model: id, section, topic
    header_rows: int = 40
    # Text a requester leaves in an empty cell, such as "Insert your answer here."
    placeholders: tuple[str, ...] = ()
    # Sheets that are the requester's own to fill, such as an evaluator's tab.
    skip_sheets: tuple[str, ...] = ()


@dataclass(frozen=True)
class Templates:
    """How an answer reads in the requester's comment and evidence cells; $-placeholders."""

    comment: dict[str, str]  # answer -> template; "*" for the rest
    evidence: str
    # What a free-text answer cell gets, where no dropdown limits it to a word.
    free_text: str = "$answer. $comment"


@dataclass(frozen=True)
class StatementGate:
    """A No or N/A must rest on a statement that rules the thing out: one whose found quote
    speaks of a scope or a provider (`quote`), or whose comment says the documents do not
    state it (`comment`), goes to a person. Patterns are the pack's, since they are words in
    its language.

    An answer in `suggest` is not dropped there: it goes on to a check, and an answer the
    check supports is offered to the person, who confirms it in one step. One whose quote names
    a provider that runs the thing for the firm (`provider`) is written instead when the firm
    turns on `provider_setting`. `check_prompt` is that check's own prompt, so the job's main
    check keeps its wording, which every other answer rests on; without one, the main check
    makes it."""

    answers: tuple[str, ...] = ()
    quote: re.Pattern[str] | None = None
    comment: re.Pattern[str] | None = None
    suggest: tuple[str, ...] = ()
    provider: re.Pattern[str] | None = None
    provider_setting: str = ""
    check_prompt: str = ""


@dataclass(frozen=True)
class JobConfig:
    answers: tuple[AnswerChoice, ...]
    layout: LayoutWords
    system_prompt: str
    question_prompt: str
    repair_prompt: str
    templates: Templates
    answers_sheet: str
    exceptions_sheet: str
    min_quote_chars: int = 15
    # Quotes an answer may rest on, each checked: a question's parts may sit in different documents.
    max_quotes: int = 1
    passages_per_question: int = 8
    # Queries whose best passages every question is shown, when the sources do not fit whole.
    standing_queries: tuple[str, ...] = ()
    standing_per_query: int = 1
    # What the model is told of those passages, and of the question's own after them.
    standing_labels: tuple[str, str] = ("", "")
    # The share of the model's window whole sources may fill before retrieval takes over.
    whole_sources_share: float = 0.5
    # And a ceiling whatever the window: every question re-reads what the prompt holds.
    max_whole_chars: int = 120_000
    # Column titles of the added sheets.
    labels: dict[str, str] = field(default_factory=dict)
    # A second call checks that the quote settles the question, for these answers.
    verify_prompt: str = ""
    verify_answers: tuple[str, ...] = ()
    # Asked of an answer that fell back, once, before it goes to a person.
    second_look_prompt: str = ""
    # What that second look may answer besides the fallback; empty for any answer.
    second_look_answers: tuple[str, ...] = ()
    # Answers such as No and N/A that need a statement, not a scope, a provider or silence.
    statement_gate: StatementGate = field(default_factory=lambda: StatementGate())
    settings: tuple[JobSetting, ...] = ()

    @property
    def fallback(self) -> AnswerChoice:
        return next(choice for choice in self.answers if choice.fallback)

    def choice(self, answer: str) -> AnswerChoice | None:
        return next((c for c in self.answers if c.answer == answer), None)

    @property
    def checks(self) -> bool:
        return bool(self.verify_answers)

    def setting_values(self, chosen: Mapping[str, object] | None) -> dict[str, bool]:
        """Every setting the job declares, as the firm chose it or at its default."""
        return setting_values(self.settings, chosen)


def load_config(config_file: Path) -> JobConfig:
    folder = config_file.parent
    try:
        raw = json.loads(config_file.read_text(encoding="utf-8"))
        answers = tuple(
            AnswerChoice(
                answer=item["answer"],
                needs_quote=bool(item.get("needs_quote", True)),
                cell_values=tuple(item.get("cell_values") or (item["answer"],)),
                fallback=bool(item.get("fallback", False)),
            )
            for item in raw["answers"]
        )
        layout = raw["layout"]
        prompts = raw["prompts"]
        config = JobConfig(
            answers=answers,
            layout=LayoutWords(
                question=_lowered(layout["question"]),
                answer=_lowered(layout["answer"]),
                comment=_lowered(layout.get("comment", ())),
                evidence=_lowered(layout.get("evidence", ())),
                context=_lowered(layout.get("context", ())),
                header_rows=int(layout.get("header_rows", 40)),
                placeholders=_lowered(layout.get("placeholders", ())),
                skip_sheets=_lowered(layout.get("skip_sheets", ())),
            ),
            system_prompt=_prompt(folder, prompts["system"]),
            question_prompt=_prompt(folder, prompts["question"]),
            repair_prompt=_prompt(folder, prompts["repair"]),
            templates=Templates(
                comment=dict(raw["templates"]["comment"]),
                evidence=raw["templates"]["evidence"],
                free_text=raw["templates"].get("free_text", "$answer. $comment"),
            ),
            answers_sheet=raw["sheets"]["answers"],
            exceptions_sheet=raw["sheets"]["exceptions"],
            min_quote_chars=int(raw.get("min_quote_chars", 15)),
            max_quotes=max(int(raw.get("max_quotes", 1)), 1),
            passages_per_question=int(raw.get("passages_per_question", 8)),
            standing_queries=tuple(
                str(q) for q in raw.get("standing", {}).get("queries", ())
            ),
            standing_per_query=int(raw.get("standing", {}).get("per_query", 1)),
            standing_labels=(
                str(raw.get("standing", {}).get("label", "")),
                str(raw.get("standing", {}).get("then", "")),
            ),
            whole_sources_share=float(raw.get("whole_sources_share", 0.5)),
            max_whole_chars=int(raw.get("max_whole_chars", 120_000)),
            labels=dict(raw.get("labels", {})),
            verify_prompt=_prompt(folder, raw["verify"]["prompt"])
            if "verify" in raw
            else "",
            verify_answers=tuple(raw["verify"]["answers"]) if "verify" in raw else (),
            second_look_prompt=_prompt(folder, raw["second_look"]["prompt"])
            if "second_look" in raw
            else "",
            second_look_answers=tuple(
                str(a) for a in raw.get("second_look", {}).get("answers", ())
            ),
            statement_gate=_gate(folder, raw.get("statement_gate", {})),
            settings=declared_settings(raw.get("settings", ())),
        )
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        re.error,
    ) as broken:
        raise PackRefusedError(
            "BAD_JOB_CONFIG", f"{config_file.name} is not a job config: {broken}"
        ) from broken
    if sum(1 for choice in answers if choice.fallback) != 1:
        raise PackRefusedError("BAD_JOB_CONFIG", "Exactly one answer is the fallback.")
    keys = [s.key for s in config.settings]
    if len(set(keys)) != len(keys):
        raise PackRefusedError("BAD_JOB_CONFIG", "Two settings share a key.")
    gate = config.statement_gate
    if gate.provider_setting and gate.provider_setting not in keys:
        raise PackRefusedError(
            "BAD_JOB_CONFIG",
            f"The statement gate's provider_setting {gate.provider_setting} is not a setting.",
        )
    if any(config.choice(a) is None for a in (*gate.answers, *gate.suggest)):
        raise PackRefusedError(
            "BAD_JOB_CONFIG",
            "The statement gate names an answer the job does not give.",
        )
    # Sliced as counts: 0 would show a question none of its own passages, and a negative
    # count every passage but the last few, past the budget retrieval keeps.
    if config.passages_per_question < 1:
        raise PackRefusedError("BAD_JOB_CONFIG", "passages_per_question is at least 1.")
    if config.standing_per_query < 0:
        raise PackRefusedError("BAD_JOB_CONFIG", "standing.per_query is at least 0.")
    # Refused here, before any call: the engine would refuse the sheet, and with it the
    # whole copy, once every question was answered.
    for name in (config.answers_sheet, config.exceptions_sheet):
        if not isinstance(name, str) or name_problem(name, []) is not None:
            raise PackRefusedError(
                "BAD_JOB_CONFIG", f'Excel refuses "{name}" as a sheet name.'
            )
    return config


def _gate(folder: Path, raw: dict) -> StatementGate:
    def pattern(key: str) -> re.Pattern[str] | None:
        return re.compile(str(raw[key]), re.IGNORECASE) if raw.get(key) else None

    return StatementGate(
        answers=tuple(str(a) for a in raw.get("answers", ())),
        quote=pattern("quote"),
        comment=pattern("comment"),
        suggest=tuple(str(a) for a in raw.get("suggest", ())),
        provider=pattern("provider"),
        provider_setting=str(raw.get("provider_setting", "")),
        check_prompt=_prompt(folder, raw["check"]) if raw.get("check") else "",
    )


def _lowered(words: object) -> tuple[str, ...]:
    return tuple(str(word).strip().casefold() for word in words)  # type: ignore[union-attr]


def _prompt(folder: Path, relative: str) -> str:
    return (folder / safe_path(relative)).read_text(encoding="utf-8").strip()
