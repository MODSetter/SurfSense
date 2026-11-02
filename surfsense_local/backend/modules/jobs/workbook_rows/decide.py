"""From a model's draft to the answer the workbook gets: no quoted answer stands unless its
quote is in a source, and none is written that the cell's dropdown does not offer."""

from __future__ import annotations

from dataclasses import dataclass, field
from string import Template

from modules.jobs.evidence.passages import Passage, SourceText
from modules.jobs.provenance.quote_check import find_quote
from modules.jobs.workbook_rows.ask import AnswerModel, Asked, ask_row
from modules.jobs.workbook_rows.cell_answers import cell_value
from modules.jobs.workbook_rows.config import JobConfig
from modules.jobs.workbook_rows.layout import QuestionRow
from modules.jobs.workbook_rows.verify import Verdict, verify_answer

# Why a row needs a person, in the words the exceptions sheet uses.
EXCEPTIONS = {
    "NEEDS_REVIEW": "The documents do not settle this question.",
    "QUOTE_NOT_FOUND": "The model answered {said}, but its quote is not in any source, so the answer was not given.",
    "NOT_SUPPORTED": "The model answered {said}, but a second check found its quote does not settle the question: {missing}",
    "NOT_ON_DROPDOWN": "The cell's dropdown has no value for {answer}, so the cell was left blank.",
    "LOW_CONFIDENCE": "The model was not confident: check the source.",
    "UNREADABLE_REPLY": "The model's reply could not be read.",
    "ROW_HIDDEN": "The row is hidden, so it was left as it was.",
    "ANSWER_LOCKED": "The answer cell is locked, so it was left as it was.",
    "ALREADY_ANSWERED": "The question already had an answer, so it was left as it was.",
}


@dataclass
class RowResult:
    row: QuestionRow
    answer: str  # the job's own answer, after the checks
    said: str | None  # what the model answered, when the checks changed it
    written: str | None  # what the answer cell gets; None leaves it blank
    quote: str  # a quote found in a source, or ""
    source: str
    section: str
    line: int | None
    comment: str
    confidence: str
    codes: list[str] = field(default_factory=list)
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    missing: str = ""  # what the second check found the quote leaves out


def answer_row(
    model: AnswerModel,
    config: JobConfig,
    row: QuestionRow,
    block: str,
    passages: list[Passage],
    sources: list[SourceText],
) -> RowResult:
    asked = ask_row(model, config, row, block)
    if asked.draft is not None:
        located = _located(asked, config, passages, sources)
        if located is None and _needs_quote(asked, config):
            shown = asked.draft.passage
            asked = ask_row(
                model,
                config,
                row,
                block,
                repair=(
                    f"Your quote is not, word for word, in passage {shown} or any other passage. "
                    "Copy the words exactly from one passage, or answer "
                    f"{config.fallback.answer} if no passage settles the question."
                ),
                earlier=asked,
            )
    return _decided(
        asked,
        config,
        row,
        passages,
        sources,
        _verdict(model, config, row, asked, passages, sources),
    )


def _verdict(
    model: AnswerModel,
    config: JobConfig,
    row: QuestionRow,
    asked: Asked,
    passages: list[Passage],
    sources: list[SourceText],
) -> Verdict | None:
    """The second check, for a quoted answer the job checks; None when there is nothing to check."""
    draft = asked.draft
    if (
        draft is None
        or not config.verify_prompt
        or draft.answer not in config.verify_answers
    ):
        return None
    located = _located(asked, config, passages, sources)
    if located is None:
        return None
    return verify_answer(
        model, config, row, draft.answer, draft.quote, sources[located[0]].title
    )


def _needs_quote(asked: Asked, config: JobConfig) -> bool:
    choice = config.choice(asked.draft.answer) if asked.draft else None
    return choice is not None and choice.needs_quote


def _located(
    asked: Asked, config: JobConfig, passages: list[Passage], sources: list[SourceText]
) -> tuple[int, int] | None:
    """The source and line of the draft's quote, or None when it is too short or not there."""
    draft = asked.draft
    if draft is None or len(draft.quote) < config.min_quote_chars:
        return None
    prefer = (
        passages[draft.passage - 1].source
        if 0 < draft.passage <= len(passages)
        else None
    )
    found = find_quote(draft.quote, [s.text for s in sources], prefer=prefer)
    return (found.source, found.line) if found else None


def _decided(
    asked: Asked,
    config: JobConfig,
    row: QuestionRow,
    passages: list[Passage],
    sources: list[SourceText],
    verdict: Verdict | None = None,
) -> RowResult:
    fallback = config.fallback
    result = RowResult(
        row=row,
        answer=fallback.answer,
        said=None,
        written=None,
        quote="",
        source="",
        section="",
        line=None,
        comment="",
        confidence="low",
        calls=asked.calls + (verdict is not None),
        input_tokens=asked.input_tokens + (verdict.input_tokens if verdict else 0),
        output_tokens=asked.output_tokens + (verdict.output_tokens if verdict else 0),
    )
    draft = asked.draft
    if draft is None:
        result.codes.append("UNREADABLE_REPLY")
    else:
        result.comment, result.confidence = draft.comment, draft.confidence
        choice = config.choice(draft.answer) or fallback
        located = _located(asked, config, passages, sources)
        if located is not None:
            source, line = located
            result.quote = draft.quote
            result.source = sources[source].title
            result.section = _section(passages, source, line)
            result.line = line
        if choice.needs_quote and located is None:
            result.said = choice.answer
            result.codes.append("QUOTE_NOT_FOUND")
        elif verdict is not None and not verdict.supported:
            result.said = choice.answer
            result.missing = verdict.missing
            result.codes.append("NOT_SUPPORTED")
        else:
            result.answer = choice.answer
    chosen = config.choice(result.answer) or fallback
    result.written = cell_value(chosen, row.allowed)
    if row.allowed is None and not chosen.fallback:
        # A free-text cell takes the answer in words, as a person filling it in would.
        result.written = " ".join(
            Template(config.templates.free_text)
            .safe_substitute(
                answer=result.answer, comment=result.comment, quote=result.quote
            )
            .split()
        )
    if chosen.fallback:
        result.codes.append("NEEDS_REVIEW")
    elif result.written is None:
        result.codes.append("NOT_ON_DROPDOWN")
    if result.confidence == "low" and not chosen.fallback:
        result.codes.append("LOW_CONFIDENCE")
    return result


def _section(passages: list[Passage], source: int, line: int) -> str:
    holding = [
        p
        for p in passages
        if p.source == source and p.first_line <= line <= p.last_line
    ]
    return holding[0].section if holding else ""
