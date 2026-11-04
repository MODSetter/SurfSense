"""From a model's draft to the answer the workbook gets: no quoted answer stands unless its
quotes are in a source, and none is written that the cell's dropdown does not offer."""

from __future__ import annotations

from dataclasses import dataclass, field
from string import Template

from modules.jobs.evidence.passages import Passage, SourceText
from modules.jobs.provenance.quote_check import find_quote, nearest_sentence, words
from modules.jobs.workbook_rows.ask import AnswerModel, Asked, Draft, ask_row
from modules.jobs.workbook_rows.cell_answers import cell_value
from modules.jobs.workbook_rows.config import JobConfig
from modules.jobs.workbook_rows.layout import QuestionRow
from modules.jobs.workbook_rows.verify import Verdict, verify_answer

# How much of a source the second check is shown for a quote whose parts "..." joins.
JOINED_CHARS = 1500

# Why a row needs a person, in the words the exceptions sheet uses.
EXCEPTIONS = {
    "NEEDS_REVIEW": "The documents do not settle this question.",
    "QUOTE_NOT_FOUND": "The model answered {said}, but no quote it gave is in a source, so the answer was not given.",
    "NOT_SUPPORTED": "The model answered {said}, but a second check found its quotes do not settle the question: {missing}",
    "NOT_ON_DROPDOWN": "The cell's dropdown has no value for {answer}, so the cell was left blank.",
    "LOW_CONFIDENCE": "The model was not confident: check the source.",
    "ANSWER_SWITCHED": "The model answered {said}, a second check refused its quotes, and it then gave another answer, so no answer was given.",
    "UNREADABLE_REPLY": "The model's reply could not be read.",
    "NO_STATEMENT": "The model answered {said}. {missing}",
    "SUGGESTED": "The checks support {said}, but it rests on a provider or a scope, so a person confirms it. {missing}",
    "CALL_FAILED": "The model could not be asked about this question ({missing}), so it was left to a person.",
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
    # For a quote whose parts "..." joins, the source's lines from its first part to its last,
    # so the second check reads what the quote leaves out.
    joined: str = ""


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
    # What the second check found the quotes leave out, or, for a suggestion, its evidence.
    missing: str = ""
    looked_again: bool = False  # it fell back at first and was asked to look once more
    # Each answer and check on the way, quotes found or not; the answers sheet keeps the last.
    trace: list[dict] = field(default_factory=list)
    # The passages the question was shown, by number from 1, pinned ones first.
    shown: list[int] = field(default_factory=list)
    # An answer the checks support that the job leaves to a person to confirm, such as N/A
    # for a control a provider runs for the firm; its quotes are `cited`.
    suggested: str | None = None

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


@dataclass(frozen=True)
class Gated:
    """Why the statement gate holds an answer: its quote names a provider that runs the thing
    for the firm, or speaks of a scope, or its comment says the documents are silent."""

    kind: str  # "provider", "scope" or "silence"
    reason: str


def answer_row(
    model: AnswerModel,
    config: JobConfig,
    row: QuestionRow,
    block: str,
    passages: list[Passage],
    sources: list[SourceText],
    *,
    checker: AnswerModel | None = None,
    settings: dict[str, bool] | None = None,
) -> RowResult:
    """`checker` makes the second checks, `model` when None; `settings` are the firm's, by key."""
    checker = checker or model
    gate = config.statement_gate
    provider_on = bool(
        gate.provider_setting and (settings or {}).get(gate.provider_setting)
    )
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
        elif (
            config.second_look_answers
            and asked.draft.answer != config.fallback.answer
            and asked.draft.answer not in config.second_look_answers
        ):
            # Asked to look again for evidence, a model also turns caution into a No or an
            # N/A: all 12 that the v0.2.0 dev sweeps wrote that way were wrong.
            asked.draft = cautious
    checks: list[Verdict] = []
    gated = _gated(asked.draft, config, passages, sources)
    if gated is not None:
        # No check can turn a scope, a provider or silence into a statement that the firm
        # does not do the thing: a person decides. An answer the pack lets the job suggest is
        # still checked, so the person is offered only one its quotes support.
        trace.append(
            {"step": "statement gate", "kind": gated.kind, "missing": gated.reason}
        )
        verdict = None
        if gated.kind != "silence" and asked.draft.answer in gate.suggest:
            verdict = _verdict(
                checker,
                config,
                row,
                asked,
                passages,
                sources,
                trace,
                checks,
                prompt=gate.check_prompt,
            )
        result = _decided(
            asked,
            config,
            row,
            passages,
            sources,
            verdict,
            checks=checks,
            gated=gated,
            provider_on=provider_on,
        )
        result.looked_again = looked_again
        result.trace = trace
        return result
    verdict = _verdict(checker, config, row, asked, passages, sources, trace, checks)
    switched = None
    if verdict is not None and not verdict.supported:
        # Right answer, wrong evidence is common: say what the check found, ask once more.
        refused = asked.draft
        _, unfound = _cited(refused, config, passages, sources)
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
            switched = refused.answer
        unfounded = (
            again is not None
            and again.answer == refused.answer
            and _needs_quote(again, config)
            and not _cited(again, config, passages, sources)[0]
        )
        # Asked for evidence for a refused No or N/A, a model reaches for a scope sentence
        # or for silence: the gate holds on this turn too.
        regated = _gated(again, config, passages, sources)
        if regated is not None:
            trace.append(
                {
                    "step": "statement gate, after the check",
                    "kind": regated.kind,
                    "missing": regated.reason,
                }
            )
        if (
            again is None
            or switched
            or unfounded
            or regated is not None
            or again.answer == config.fallback.answer
        ):
            # The refusal stands, and the row keeps what was refused and why: for a person,
            # the refused quotes are the best place to start. A claim kept on quotes that are
            # nowhere in the sources, or on a scope or silence, brings no new evidence, so it
            # is refused the same way.
            asked.draft = refused
        else:
            # Checked again even on the same quotes: the check refuses right answers often
            # enough that a second look rescued 14 of them in the v0.2.0 runs, and every wrong
            # answer that passed on a second look came with new quotes.
            verdict = _verdict(
                checker, config, row, asked, passages, sources, trace, checks
            )
    result = _decided(asked, config, row, passages, sources, verdict, switched, checks)
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
            if asked.draft is None:
                asked.draft = draft  # unreadable: the row says what the model claimed
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
    checks: list[Verdict],
    prompt: str = "",
) -> Verdict | None:
    """The second check, for a quoted answer the job checks; None when there is nothing to
    check. Every check made is kept in `checks`, which the row's cost counts. `prompt` is the
    statement gate's own check, for an answer it may suggest."""
    draft = asked.draft
    if draft is None or not (
        prompt or (config.verify_prompt and draft.answer in config.verify_answers)
    ):
        return None
    cited, _ = _cited(draft, config, passages, sources)
    if not cited:
        return None
    verdict = verify_answer(
        model,
        config,
        row,
        draft.answer,
        [(c.source, c.quote, c.joined) for c in cited],
        prompt=prompt or config.verify_prompt,
    )
    checks.append(verdict)
    trace.append(
        {"step": "check", "supported": verdict.supported, "missing": verdict.missing}
    )
    return verdict


def _gated(
    draft: Draft | None,
    config: JobConfig,
    passages: list[Passage],
    sources: list[SourceText],
) -> Gated | None:
    """Why an answer the gate covers rests on no statement, or None when it may go on to the
    check. In the v0.2.0 dev sweeps this held for all 5 wrong No and N/A writes and none of
    the 23 right ones; on Qwen3.8-27B's dev runs it cut wrong answers from 3.7 to 1.7 a pass."""
    gate = config.statement_gate
    if draft is None or draft.answer not in gate.answers:
        return None
    cited, _ = _cited(draft, config, passages, sources)
    # A quote is read as the quote check reads it, by its words, so "out-of-scope" or a
    # line break inside a phrase is caught as surely as the phrase itself.
    read = [" ".join(words(c.quote)) for c in cited]
    if (
        gate.provider is not None
        and draft.answer in gate.suggest
        and any(gate.provider.search(quote) for quote in read)
    ):
        return Gated(
            "provider",
            f"The evidence for {draft.answer} is that a provider runs this for the firm.",
        )
    if gate.quote is not None and any(gate.quote.search(quote) for quote in read):
        return Gated(
            "scope",
            f"The only evidence for {draft.answer} speaks of a scope or a provider, which "
            "does not say the firm does not do it.",
        )
    if gate.comment is not None and gate.comment.search(
        " ".join(draft.comment.split())
    ):
        return Gated(
            "silence",
            f"The only evidence for {draft.answer} is what the documents leave unsaid, which "
            "does not say the firm does not do it.",
        )
    return None


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
            _lines(sources[found.source].text, found.line, found.end_line),
        )
        if quote not in cited:
            cited.append(quote)
    return cited, unfound


def _lines(text: str, first: int, last: int) -> str:
    """A source's lines `first` to `last`, at most JOINED_CHARS; "" for a quote with one part."""
    if not last:
        return ""
    held = "\n".join(text.splitlines()[first - 1 : last]).strip()
    return held if len(held) <= JOINED_CHARS else held[:JOINED_CHARS].rstrip() + " ..."


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
    checks: list[Verdict] | None = None,
    gated: Gated | None = None,
    provider_on: bool = False,
) -> RowResult:
    fallback = config.fallback
    checks = checks or []
    result = RowResult(
        row=row,
        answer=fallback.answer,
        said=None,
        written=None,
        comment="",
        confidence="low",
        calls=asked.calls + len(checks),
        input_tokens=asked.input_tokens + sum(c.input_tokens for c in checks),
        output_tokens=asked.output_tokens + sum(c.output_tokens for c in checks),
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
            result.missing = verdict.missing if verdict else ""
            result.codes.append("ANSWER_SWITCHED")
        elif choice.needs_quote and not result.cited:
            result.said = choice.answer
            result.codes.append("QUOTE_NOT_FOUND")
        elif gated is not None:
            supported = verdict is not None and verdict.supported
            if supported and gated.kind == "provider" and provider_on:
                result.answer = choice.answer  # the firm's setting writes it
            elif supported:
                result.said = result.suggested = choice.answer
                result.missing = _suggestion(choice.answer, result.cited)
                result.codes.append("SUGGESTED")
            elif verdict is not None:
                result.said = choice.answer
                result.missing = verdict.missing
                result.codes.append("NOT_SUPPORTED")
            else:
                result.said = choice.answer
                result.missing = gated.reason
                result.codes.append("NO_STATEMENT")
        elif verdict is not None and not verdict.supported:
            result.said = choice.answer
            result.missing = verdict.missing
            result.codes.append("NOT_SUPPORTED")
        else:
            result.answer = choice.answer
    chosen = config.choice(result.answer) or fallback
    result.written = written_value(result, config)
    if chosen.fallback:
        result.codes.append("NEEDS_REVIEW")
    elif result.written is None:
        result.codes.append("NOT_ON_DROPDOWN")
    if result.confidence == "low" and not chosen.fallback:
        result.codes.append("LOW_CONFIDENCE")
    return result


def written_value(result: RowResult, config: JobConfig) -> str | None:
    """What the answer cell gets for `result.answer`: the requester's dropdown spelling, the
    answer in words in a free-text cell, or None to leave the cell blank."""
    chosen = config.choice(result.answer) or config.fallback
    if result.row.allowed is None and not chosen.fallback:
        # A free-text cell takes the answer in words, as a person filling it in would.
        return " ".join(
            Template(config.templates.free_text)
            .safe_substitute(template_fields(result))
            .split()
        )
    return cell_value(chosen, result.row.allowed)


def failed_row(config: JobConfig, row: QuestionRow, error: Exception) -> RowResult:
    """A row whose call failed outright, left to a person with the reason."""
    fallback = config.fallback
    reason = " ".join(str(error).split())[:200] or type(error).__name__
    return RowResult(
        row=row,
        answer=fallback.answer,
        said=None,
        written=cell_value(fallback, row.allowed),
        comment=EXCEPTIONS["CALL_FAILED"].format(missing=reason),
        confidence="low",
        codes=["CALL_FAILED"],
        missing=reason,
    )


def template_fields(result: RowResult) -> dict[str, str]:
    """What a pack's templates may say of an answer. $quote, $source, $section and $where name
    the main quote, $citations and $sources all of them. $comment is the model's own words only
    when they stand: where the checks set its answer aside, it is the reason instead, so a
    claim nothing checked never reaches the requester's cells."""
    wheres = [_where(c) for c in result.cited]
    comment = result.comment
    if result.said is not None:
        code = next((c for c in result.codes if c != "NEEDS_REVIEW"), "NEEDS_REVIEW")
        comment = result.missing or EXCEPTIONS[code].format(
            said=result.said, answer=result.answer, missing=result.missing
        )
    return {
        "answer": result.answer,
        "comment": comment,
        "quote": result.quote,
        "source": result.source,
        "section": result.section,
        "where": wheres[0] if wheres else "",
        "citations": "; ".join(
            f'{where}: "{c.quote}"'
            for where, c in zip(wheres, result.cited, strict=True)
        ),
        "sources": "; ".join(dict.fromkeys(wheres)),
    }


def _where(cited: Cited) -> str:
    return cited.source + (f", {cited.section}" if cited.section else "")


def _suggestion(answer: str, cited: list[Cited]) -> str:
    """What a person confirms in one step: the answer, and where its checked quotes are."""
    evidence = "; ".join(f'{_where(c)}: "{c.quote}"' for c in cited)
    return f"Suggested: {answer}. Evidence: {evidence}"


def _section(passages: list[Passage], source: int, line: int) -> str:
    holding = [
        p
        for p in passages
        if p.source == source and p.first_line <= line <= p.last_line
    ]
    return holding[0].section if holding else ""
