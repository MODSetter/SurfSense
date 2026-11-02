"""From a model's draft to the answer the workbook gets: no quoted answer stands unless its
quotes are in a source, and none is written that the cell's dropdown does not offer."""

from __future__ import annotations

from dataclasses import dataclass, field
from string import Template

from modules.jobs.evidence.passages import Passage, SourceText
from modules.jobs.provenance.quote_check import find_quote, nearest_sentence
from modules.jobs.workbook_rows.ask import AnswerModel, Asked, Draft, ask_row
from modules.jobs.workbook_rows.cell_answers import cell_value
from modules.jobs.workbook_rows.config import JobConfig
from modules.jobs.workbook_rows.layout import QuestionRow
from modules.jobs.workbook_rows.verify import Verdict, verify_answer

# Why a row needs a person, in the words the exceptions sheet uses.
EXCEPTIONS = {
    "NEEDS_REVIEW": "The documents do not settle this question.",
    "QUOTE_NOT_FOUND": "The model answered {said}, but no quote it gave is in a source, so the answer was not given.",
    "NOT_SUPPORTED": "The model answered {said}, but a second check found its quotes do not settle the question: {missing}",
    "NOT_ON_DROPDOWN": "The cell's dropdown has no value for {answer}, so the cell was left blank.",
    "LOW_CONFIDENCE": "The model was not confident: check the source.",
    "ANSWER_SWITCHED": "The model answered {said}, a second check refused its quotes, and it then gave another answer, so no answer was given.",
    "UNREADABLE_REPLY": "The model's reply could not be read.",
    "ROW_HIDDEN": "The row is hidden, so it was left as it was.",
    "ANSWER_LOCKED": "The answer cell is locked, so it was left as it was.",
    "ALREADY_ANSWERED": "The question already had an answer, so it was left as it was.",
}


@dataclass(frozen=True)
class Cited:
    """A quote found in a source, and where."""

    quote: str
    source: str  # the source's title
    section: str
    line: int


@dataclass
class RowResult:
    row: QuestionRow
    answer: str  # the job's own answer, after the checks
    said: str | None  # what the model answered, when the checks changed it
    written: str | None  # what the answer cell gets; None leaves it blank
    comment: str
    confidence: str
    # The draft's quotes found in a source, the main one first; a refused answer keeps its own.
    cited: list[Cited] = field(default_factory=list)
    codes: list[str] = field(default_factory=list)
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    missing: str = ""  # what the second check found the quotes leave out
    looked_again: bool = False  # it fell back at first and was asked to look once more
    # Each answer and check on the way, quotes found or not; the answers sheet keeps the last.
    trace: list[dict] = field(default_factory=list)

    @property
    def quote(self) -> str:
        return self.cited[0].quote if self.cited else ""

    @property
    def source(self) -> str:
        return self.cited[0].source if self.cited else ""

    @property
    def section(self) -> str:
        return self.cited[0].section if self.cited else ""

    @property
    def line(self) -> int | None:
        return self.cited[0].line if self.cited else None


def answer_row(
    model: AnswerModel,
    config: JobConfig,
    row: QuestionRow,
    block: str,
    passages: list[Passage],
    sources: list[SourceText],
) -> RowResult:
    trace: list[dict] = []

    def quoted(step: str, ask: str | None, earlier: Asked | None) -> Asked:
        return _quoted(
            model, config, row, block, passages, sources, trace, step, ask, earlier
        )

    asked = quoted("answer", None, None)
    looked_again = False
    if config.second_look_prompt and _doubtful(asked.draft, config):
        # Caution is the common miss: the quotes are often there, part by part.
        looked_again, cautious = True, asked.draft
        asked = quoted(
            "second look",
            Template(config.second_look_prompt).safe_substitute(
                fallback=config.fallback.answer
            ),
            asked,
        )
        if asked.draft is None:
            asked.draft = cautious  # an unreadable second look leaves the first answer
    verdict = _verdict(model, config, row, asked, passages, sources, trace)
    switched = None
    if verdict is not None and not verdict.supported:
        # Right answer, wrong evidence is common: say what the check found, ask once more.
        refused = asked.draft
        _, unfound = _cited(refused, config, passages, sources)
        asked.calls += 1
        asked.input_tokens += verdict.input_tokens
        asked.output_tokens += verdict.output_tokens
        asked = ask_row(
            model,
            config,
            row,
            block,
            repair=(
                f"A check found your {_quotes_are(refused)} not evidence for {refused.answer}: "
                f"{verdict.missing}{_unfound_note(unfound)} Quote, word for word, the "
                f"passages that are evidence for {refused.answer}, or answer "
                f"{config.fallback.answer} if no passage is."
            ),
            earlier=asked,
        )
        _note(trace, "after the check", asked.draft, config, passages, sources)
        again = asked.draft
        if again is not None and again.answer not in (
            refused.answer,
            config.fallback.answer,
        ):
            # Refused, an answer may find better evidence or give way, never turn into
            # another, which nothing checked: all 11 of Qwen's last-turn No were refused.
            switched, verdict = refused.answer, None
        else:
            verdict = _verdict(model, config, row, asked, passages, sources, trace)
    result = _decided(asked, config, row, passages, sources, verdict, switched)
    result.looked_again = looked_again
    result.trace = trace
    return result


def _doubtful(draft: Draft | None, config: JobConfig) -> bool:
    """A fallback answer worth a second look: it quotes something, or is unsure, or says
    nothing of what is open. Sonnet's fallbacks with a quote were the gold's Yes 62% of the
    time, against 13% without, and its low-confidence ones 77%."""
    return (
        draft is not None
        and draft.answer == config.fallback.answer
        and (bool(draft.quotes) or draft.confidence == "low" or not draft.comment)
    )


def _quoted(
    model: AnswerModel,
    config: JobConfig,
    row: QuestionRow,
    block: str,
    passages: list[Passage],
    sources: list[SourceText],
    trace: list[dict],
    step: str,
    ask: str | None,
    earlier: Asked | None,
) -> Asked:
    """Asked (the first time, or with `ask`), and once more if no quote of a quoted answer is found."""
    asked = ask_row(model, config, row, block, repair=ask, earlier=earlier)
    _note(trace, step, asked.draft, config, passages, sources)
    draft = asked.draft
    if draft is not None and _needs_quote(draft, config):
        cited, _ = _cited(draft, config, passages, sources)
        if not cited:
            asked = ask_row(
                model,
                config,
                row,
                block,
                repair=_not_found(draft, config, sources),
                earlier=asked,
            )
            _note(trace, "quote again", asked.draft, config, passages, sources)
    return asked


def _note(
    trace: list[dict],
    step: str,
    draft: Draft | None,
    config: JobConfig,
    passages: list[Passage],
    sources: list[SourceText],
) -> None:
    """One step of a row's way to its answer, for a person or an eval checking how it got there."""
    if draft is None:
        trace.append({"step": step, "answer": None})
        return
    _, unfound = _cited(draft, config, passages, sources)
    trace.append(
        {
            "step": step,
            "answer": draft.answer,
            "confidence": draft.confidence,
            "quotes": [
                {
                    "passage": q.passage,
                    "quote": q.quote,
                    "found": n not in unfound,
                }
                for n, q in enumerate(draft.quotes, start=1)
            ],
            "comment": draft.comment,
        }
    )


def _verdict(
    model: AnswerModel,
    config: JobConfig,
    row: QuestionRow,
    asked: Asked,
    passages: list[Passage],
    sources: list[SourceText],
    trace: list[dict],
) -> Verdict | None:
    """The second check, for a quoted answer the job checks; None when there is nothing to check."""
    draft = asked.draft
    if (
        draft is None
        or not config.verify_prompt
        or draft.answer not in config.verify_answers
    ):
        return None
    cited, _ = _cited(draft, config, passages, sources)
    if not cited:
        return None
    verdict = verify_answer(
        model, config, row, draft.answer, [(c.source, c.quote) for c in cited]
    )
    trace.append(
        {"step": "check", "supported": verdict.supported, "missing": verdict.missing}
    )
    return verdict


def _needs_quote(draft: Draft, config: JobConfig) -> bool:
    choice = config.choice(draft.answer)
    return choice is not None and choice.needs_quote


def _cited(
    draft: Draft, config: JobConfig, passages: list[Passage], sources: list[SourceText]
) -> tuple[list[Cited], list[int]]:
    """The draft's quotes found in a source, and the numbers (from 1) of those too short or not there."""
    texts = [s.text for s in sources]
    cited: list[Cited] = []
    unfound: list[int] = []
    for number, quoted in enumerate(draft.quotes, start=1):
        found = None
        if len(quoted.quote) >= config.min_quote_chars:
            prefer = (
                passages[quoted.passage - 1].source
                if 0 < quoted.passage <= len(passages)
                else None
            )
            found = find_quote(quoted.quote, texts, prefer=prefer)
        if found is None:
            unfound.append(number)
            continue
        quote = Cited(
            quoted.quote,
            sources[found.source].title,
            _section(passages, found.source, found.line),
            found.line,
        )
        if quote not in cited:
            cited.append(quote)
    return cited, unfound


def _not_found(draft: Draft, config: JobConfig, sources: list[SourceText]) -> str:
    if not draft.quotes:
        problem = f"Your answer {draft.answer} needs a quote, and you gave none."
    elif len(draft.quotes) == 1:
        problem = (
            f"Your quote is not, word for word, in passage {draft.quotes[0].passage} "
            "or any other passage."
        )
    else:
        problem = "None of your quotes is, word for word, in its passage or any other passage."
    texts = [s.text for s in sources]
    for number, quoted in enumerate(draft.quotes, start=1):
        nearest = nearest_sentence(quoted.quote, texts)
        if nearest:
            which = "your quote" if len(draft.quotes) == 1 else f"quote {number}"
            problem += (
                f' The closest words to {which} in the documents are: "{nearest}" '
                "If they are what you meant, copy them exactly."
            )
    return (
        f"{problem} Copy each quote's words exactly from one passage, or answer "
        f"{config.fallback.answer} if no passage settles the question."
    )


def _quotes_are(draft: Draft) -> str:
    return "quote is" if len(draft.quotes) == 1 else "quotes are"


def _unfound_note(unfound: list[int]) -> str:
    if not unfound:
        return ""
    if len(unfound) == 1:
        return f" Quote {unfound[0]} is not, word for word, in any passage."
    numbers = ", ".join(str(n) for n in unfound[:-1]) + f" and {unfound[-1]}"
    return f" Quotes {numbers} are not, word for word, in any passage."


def _decided(
    asked: Asked,
    config: JobConfig,
    row: QuestionRow,
    passages: list[Passage],
    sources: list[SourceText],
    verdict: Verdict | None = None,
    switched: str | None = None,
) -> RowResult:
    fallback = config.fallback
    result = RowResult(
        row=row,
        answer=fallback.answer,
        said=None,
        written=None,
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
        result.cited, _ = _cited(draft, config, passages, sources)
        if switched is not None:
            result.said = switched
            result.codes.append("ANSWER_SWITCHED")
        elif choice.needs_quote and not result.cited:
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
