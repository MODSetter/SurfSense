"""One review point settled: the model's verdict, kept only when its playbook quote is found and its
change can be placed in the contract, and checked again when the job asks for it. Anything else
goes to a person with the reason."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from modules.jobs.asking.model import AnswerModel
from modules.jobs.evidence.passages import Passage, SourceText
from modules.jobs.provenance.quote_check import Found, find_quote, nearest_sentence
from modules.jobs.word_clauses.ask import Draft, PointPrompt, ask_point
from modules.jobs.word_clauses.check import check_change
from modules.jobs.word_clauses.config import ClauseConfig, ReviewPoint
from modules.jobs.word_clauses.contract import Contract
from modules.jobs.word_clauses.placement import locate, touches_field, typeset

# What a person reads of each reason a point came to them.
REASONS = {
    "UNREADABLE_REPLY": "The model's reply could not be read.",
    "CALL_FAILED": "The call to the model failed.",
    "NEEDS_REVIEW": "The model could not settle this point.",
    "QUOTE_NOT_FOUND": "The playbook position it quoted is not in your playbook word for word.",
    "NO_PARAGRAPH": "It named a paragraph the contract does not have.",
    "TEXT_NOT_FOUND": "The words it would change are not in the paragraph it named.",
    "IN_FIELD": "The words it would change are inside a field Word fills in.",
    "NO_CHANGE": "It found the contract departs from your playbook but proposed no change.",
    "SAME_TEXT": "Its change would leave the text as it is.",
    "NOT_SUPPORTED": "A second check found your playbook does not call for this change.",
    "ANCHOR_NOT_UNIQUE": "The words it would change occur more than once in the contract.",
}
_NEEDS_QUOTE = ("meets", "deviates", "missing")
_NEEDS_CHANGE = ("deviates", "missing")


@dataclass(frozen=True)
class Change:
    kind: str  # "replace", "insert_after" or "delete"
    clause: int  # index into the contract's clauses
    start: (
        int  # the span of the clause's text replaced or deleted; for an insert, nothing
    )
    end: int
    new_text: str  # "" for a delete


@dataclass
class PointResult:
    point: ReviewPoint
    verdict: str  # "changed", "meets", "not_covered" or "for_person"
    said: str = ""  # the model's own verdict; "" when none could be read
    paragraphs: list[str] = field(default_factory=list)
    quote: str = ""
    source: str = ""
    section: str = ""
    external: str = ""  # the reason the other side reads beside the change
    internal: str = ""  # SurfSense's reasoning, kept in Studio
    change: Change | None = None
    codes: list[str] = field(default_factory=list)
    why: str = ""
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def to_person(self, code: str, why: str = "") -> None:
        """No change is made: the point and its reason go to a person."""
        self.verdict = "for_person"
        self.change = None
        self.codes.append(code)
        self.why = why or REASONS.get(code, code)


@dataclass(frozen=True)
class _Problem:
    code: str
    ask: str  # what the model is told when asked again


def decide_point(
    model: AnswerModel,
    config: ClauseConfig,
    contract: Contract,
    point: ReviewPoint,
    prompt: PointPrompt,
    passages: list[Passage],
    sources: list[SourceText],
    checker: AnswerModel | None = None,
) -> PointResult:
    """`checker` makes the second check when the job has one, the answering model when None."""
    texts = [s.text for s in sources]
    asked = ask_point(model, config, prompt)
    problems = _problems(asked.draft, config, contract, passages, texts)
    if problems and asked.draft is not None and asked.calls < 2:
        asked = ask_point(
            model,
            config,
            prompt,
            repair="\n".join(p.ask for p in problems),
            earlier=asked,
        )
        problems = _problems(asked.draft, config, contract, passages, texts)
    result = PointResult(
        point,
        "for_person",
        calls=asked.calls,
        input_tokens=asked.input_tokens,
        output_tokens=asked.output_tokens,
    )
    draft = asked.draft
    if draft is None:
        result.to_person("UNREADABLE_REPLY")
        return result
    result.said, result.paragraphs = draft.said, list(draft.paragraphs)
    result.external, result.internal = draft.external, draft.internal
    if problems:
        result.to_person(problems[0].code)
        return result
    if draft.said in _NEEDS_QUOTE:
        found = _found(draft, config, passages, texts)
        result.quote = draft.quote
        result.source = sources[found.source].title  # type: ignore[union-attr]
        result.section = _section(passages, found)  # type: ignore[arg-type]
    if draft.said in ("meets", "not_covered"):
        result.verdict = draft.said
    elif draft.said == "unclear":
        result.to_person("NEEDS_REVIEW", draft.internal or REASONS["NEEDS_REVIEW"])
    else:
        change = _change(draft, contract)
        if config.check_prompt:
            clause = contract.clauses[change.clause].text
            checked = check_change(
                checker or model,
                config.check_prompt,
                point,
                (result.source, result.quote),
                clause,
                _described(change, clause),
            )
            result.calls += 1
            result.input_tokens += checked.input_tokens
            result.output_tokens += checked.output_tokens
            if not checked.supported:
                why = REASONS["NOT_SUPPORTED"]
                result.to_person("NOT_SUPPORTED", f"{why} {checked.missing}".strip())
                return result
        result.change, result.verdict = change, "changed"
    return result


def failed_point(point: ReviewPoint, error: Exception) -> PointResult:
    result = PointResult(point, "for_person")
    result.to_person("CALL_FAILED")
    return result


def _problems(
    draft: Draft | None,
    config: ClauseConfig,
    contract: Contract,
    passages: list[Passage],
    texts: list[str],
) -> list[_Problem]:
    if draft is None:
        return [_Problem("UNREADABLE_REPLY", "")]
    problems = []
    if draft.said in _NEEDS_QUOTE and _found(draft, config, passages, texts) is None:
        problems.append(_Problem("QUOTE_NOT_FOUND", _quote_ask(draft, passages, texts)))
    if draft.said in _NEEDS_CHANGE:
        problems += _placement(draft, contract)
    return problems


def _found(
    draft: Draft, config: ClauseConfig, passages: list[Passage], texts: list[str]
) -> Found | None:
    if len(draft.quote) < config.min_quote_chars:
        return None
    cited = _cited(draft, passages)
    return find_quote(draft.quote, texts, cited.source if cited else None)


def _cited(draft: Draft, passages: list[Passage]) -> Passage | None:
    return passages[draft.passage - 1] if 0 < draft.passage <= len(passages) else None


def _quote_ask(draft: Draft, passages: list[Passage], texts: list[str]) -> str:
    ask = (
        "Your playbook_quote is not in the playbook word for word. Copy the firm's position "
        "exactly from one passage, without changing or leaving out a word."
    )
    nearest = nearest_sentence(draft.quote, texts) if draft.quote else None
    if nearest:
        return f'{ask} The nearest sentence the playbook has is: "{nearest}"'
    cited = _cited(draft, passages)
    if cited is not None:
        return f'{ask} Passage [{draft.passage}] reads: "{cited.text}"'
    return ask


def _placement(draft: Draft, contract: Contract) -> list[_Problem]:
    edit = draft.edit
    if edit.kind == "none":
        return [
            _Problem(
                "NO_CHANGE",
                "You found the contract departs from the playbook, so give the edit that "
                "brings it in line: kind replace, insert_after or delete.",
            )
        ]
    index = contract.find(edit.paragraph)
    if index is None:
        return [
            _Problem(
                "NO_PARAGRAPH",
                f"There is no paragraph {edit.paragraph or '(none named)'}: name the one to "
                "change by its id in brackets, such as P12.",
            )
        ]
    clause = contract.clauses[index]
    if edit.kind == "insert_after":
        if not edit.new_text:
            return [_Problem("NO_CHANGE", "Give new_text: the paragraph to insert.")]
        return []
    span = locate(clause, edit.old_text) if edit.old_text else None
    if span is None:
        return [
            _Problem(
                "TEXT_NOT_FOUND",
                f'{clause.id} does not read "{edit.old_text}". It reads: "{clause.text.strip()}". '
                "Copy old_text from it exactly, without its number.",
            )
        ]
    if touches_field(clause, *span):
        return [
            _Problem(
                "IN_FIELD",
                "Those words are inside a field Word fills in; change words outside it.",
            )
        ]
    old = clause.text[span[0] : span[1]]
    if edit.kind == "replace" and _flat(edit.new_text) == _flat(old):
        return [_Problem("SAME_TEXT", "Your new_text is the same as old_text.")]
    return []


def _change(draft: Draft, contract: Contract) -> Change:
    """The edit as positions in the clause's text; `_placement` found nothing wrong with it."""
    edit = draft.edit
    index = contract.find(edit.paragraph)
    assert index is not None
    clause = contract.clauses[index]
    whole = " ".join(c.text for c in contract.clauses)
    if edit.kind == "insert_after":
        # A paragraph inserted after a heading would take the heading's style: it goes after the
        # paragraph the heading starts instead.
        while clause.heading and index + 1 < len(contract.clauses):
            index += 1
            clause = contract.clauses[index]
        lines = [
            typeset(line.strip(), "", whole) for line in edit.new_text.splitlines()
        ]
        return Change("insert_after", index, 0, 0, "\n".join(x for x in lines if x))
    start, end = locate(clause, edit.old_text)  # type: ignore[misc]
    new = _flat(edit.new_text)
    if edit.kind == "delete" or not new:
        return Change("delete", index, start, end, "")
    return Change(
        "replace", index, start, end, typeset(new, clause.text[start:end], whole)
    )


def _described(change: Change, clause: str) -> str:
    old = clause[change.start : change.end]
    if change.kind == "insert_after":
        return f'insert after the clause a new paragraph: "{change.new_text}"'
    if change.kind == "delete":
        return f'delete "{old}"'
    return f'replace "{old}" with "{change.new_text}"'


def _section(passages: list[Passage], found: Found) -> str:
    for passage in passages:
        if (
            passage.source == found.source
            and passage.first_line <= found.line <= passage.last_line
        ):
            return passage.section
    return ""


def _flat(text: str) -> str:
    """One paragraph's worth: replace_text never starts a paragraph."""
    return re.sub(r"\s+", " ", text).strip()
