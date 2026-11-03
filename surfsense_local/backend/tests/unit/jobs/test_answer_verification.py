"""A quoted answer is checked once more: a quote that is real but does not settle the question
leaves the answer to a person, so a related control never passes for the one asked about."""

import json
from pathlib import Path

import openpyxl
import pytest
from openpyxl.worksheet.datavalidation import DataValidation

from modules.artifacts.revised_copies.engines import excel
from modules.jobs.evidence.passages import SourceText
from modules.jobs.workbook_rows.ask import ModelReply
from modules.jobs.workbook_rows.config import load_config
from modules.jobs.workbook_rows.fill import fill_workbook
from modules.jobs.workbook_rows.operations import comment_text

pytestmark = pytest.mark.unit

PLAN = SourceText(
    3,
    "contingency-plan",
    "## Plan\n\nThe procedures shall be documented in a formal contingency plan.",
)
QUOTE = "The procedures shall be documented in a formal contingency plan."
ISMS = SourceText(
    4,
    "isms",
    "## Review\n\nEvery policy is reviewed and approved by management each year.",
)
REVIEWED = "Every policy is reviewed and approved by management each year."


@pytest.fixture
def config(tmp_path: Path):
    """The runner's settings with the second check turned on for Yes."""
    folder = tmp_path / "job"
    (folder / "prompts").mkdir(parents=True)
    prompts = {
        "system": "system: $answers",
        "question": "$passages\n\nQuestion: $question",
        "repair": "$problem",
        "verify": "verify: $answer",
    }
    for name, text in prompts.items():
        (folder / "prompts" / f"{name}.md").write_text(text, encoding="utf-8")
    (folder / "job.json").write_text(
        json.dumps(
            {
                "answers": [
                    {"answer": "Yes", "needs_quote": True},
                    {"answer": "No", "needs_quote": True},
                    {"answer": "Needs review", "needs_quote": False, "fallback": True},
                ],
                "layout": {"question": ["question"], "answer": ["answer"]},
                "prompts": {
                    "system": "prompts/system.md",
                    "question": "prompts/question.md",
                    "repair": "prompts/repair.md",
                },
                "verify": {"prompt": "prompts/verify.md", "answers": ["Yes"]},
                "max_quotes": 2,
                "templates": {"comment": {"*": "$comment"}, "evidence": "$where"},
                "sheets": {"answers": "Answers", "exceptions": "Exceptions"},
            }
        ),
        encoding="utf-8",
    )
    return load_config(folder / "job.json")


@pytest.fixture
def workbook(tmp_path: Path) -> Path:
    """Two questions with a Yes/No dropdown."""
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["Question", "Answer"])
    sheet.append(["Are virtualization security policies established?", None])
    sheet.append(["Is a contingency plan documented?", None])
    rule = DataValidation(type="list", formula1='"Yes,No"', allow_blank=True)
    rule.add("B2:B3")
    sheet.add_data_validation(rule)
    path = tmp_path / "Q.xlsx"
    book.save(path)
    return path


class Model:
    """Answers Yes with the plan's one sentence; the second check holds only for the contingency plan."""

    name = "scripted"
    window = 32_768
    concurrency = 1

    def __init__(self) -> None:
        self.checks: list[str] = []

    def ask(self, system, turns, schema, shared):
        question = turns[0][1].split("Question:")[-1]
        if system.startswith("verify"):
            self.checks.append(question)
            settled = "contingency plan documented" in question
            return ModelReply(
                json.dumps(
                    {
                        "supported": settled,
                        "missing": "" if settled else "Says nothing of virtualization.",
                    }
                )
            )
        return ModelReply(
            json.dumps(
                {
                    "quotes": [{"passage": 1, "quote": QUOTE}],
                    "answer": "Yes",
                    "comment": "Planned.",
                    "confidence": "high",
                }
            )
        )


def test_a_real_quote_that_does_not_settle_the_question_is_left_for_review(
    workbook, config
):
    """The verified Yes stands; the Yes resting on an unrelated sentence is asked again, checked
    again, and refused again: it becomes Needs review with what is missing, and the requester's
    comment cell gets that reason, not the model's claim."""
    model = Model()

    filled = fill_workbook(workbook, [PLAN], config, model)

    virtualization, contingency = filled.results
    assert (contingency.answer, contingency.written) == ("Yes", "Yes")
    assert (virtualization.answer, virtualization.said, virtualization.written) == (
        "Needs review",
        "Yes",
        None,
    )
    assert virtualization.codes == ["NOT_SUPPORTED", "NEEDS_REVIEW"]
    assert "virtualization" in filled.exceptions[0][4]
    # Asked once more with the reason, and checked again.
    assert len(model.checks) == 3
    assert [s["step"] for s in virtualization.trace] == [
        "answer",
        "check",
        "after the check",
        "check",
    ]
    assert virtualization.calls == 4
    assert comment_text(virtualization, config) == "Says nothing of virtualization."


def test_a_check_that_cannot_be_read_does_not_let_the_answer_through(workbook, config):
    """An unreadable second check counts as unsupported: the answer goes to a person."""
    model = Model()
    model.ask = lambda system, turns, schema, shared: ModelReply(
        "not json"
        if system.startswith("verify")
        else json.dumps(
            {
                "quotes": [{"passage": 1, "quote": QUOTE}],
                "answer": "Yes",
                "comment": "",
                "confidence": "high",
            }
        )
    )

    filled = fill_workbook(workbook, [PLAN], config, model)

    assert [r.answer for r in filled.results] == ["Needs review", "Needs review"]


def _reply(*quotes: str) -> ModelReply:
    return ModelReply(
        json.dumps(
            {
                "quotes": [{"passage": 1, "quote": q} for q in quotes],
                "answer": "Yes",
                "comment": "Planned and reviewed.",
                "confidence": "high",
            }
        )
    )


def test_an_answer_may_rest_on_quotes_from_two_documents(workbook, config, tmp_path):
    """Each quote is found in its own source, the second check reads them together, quotes past
    the job's limit are dropped, and the answers sheet gives each quote a line."""
    checks: list[str] = []

    def ask(system, turns, schema, shared):
        if system.startswith("verify"):
            checks.append(turns[0][1])
            return ModelReply(json.dumps({"supported": True, "missing": ""}))
        return _reply(QUOTE, REVIEWED, "Every policy is reviewed and approved")

    model = Model()
    model.ask = ask

    filled = fill_workbook(workbook, [PLAN, ISMS], config, model)

    contingency = filled.results[1]
    assert contingency.answer == "Yes"
    assert [(c.source, c.section) for c in contingency.cited] == [
        ("contingency-plan", "Plan"),
        ("isms", "Review"),
    ]
    assert '1. From contingency-plan: "The procedures' in checks[1]
    assert '2. From isms: "Every policy' in checks[1]
    assert "3. From" not in checks[1]
    out = tmp_path / "filled.xlsx"
    assert excel.apply(workbook, filled.operations, out).saved
    lines = [
        (row[1], row[6])
        for row in openpyxl.load_workbook(out)["Answers"].iter_rows(
            min_row=2, values_only=True
        )
    ]
    assert lines == [
        ("B2", "contingency-plan"),
        ("B2", "isms"),
        ("B3", "contingency-plan"),
        ("B3", "isms"),
    ]


def test_a_quote_that_is_not_in_any_source_is_named_when_the_answer_is_asked_again(
    workbook, config
):
    """The answer is checked on the quotes that were found; asked again, the model hears which was not."""
    turns_seen: list[list[tuple[str, str]]] = []
    verdicts = iter([False, True, False, True])

    def ask(system, turns, schema, shared):
        if system.startswith("verify"):
            supported = next(verdicts)
            return ModelReply(
                json.dumps(
                    {
                        "supported": supported,
                        "missing": "" if supported else "Says nothing of review.",
                    }
                )
            )
        turns_seen.append(turns)
        if len(turns) == 1:
            return _reply(QUOTE, "Words that no policy of the firm holds anywhere.")
        return _reply(QUOTE, REVIEWED)

    model = Model()
    model.ask = ask

    filled = fill_workbook(workbook, [PLAN, ISMS], config, model)

    assert [r.answer for r in filled.results] == ["Yes", "Yes"]
    repair = turns_seen[1][-1][1]
    assert "Says nothing of review." in repair
    assert "Quote 2 is not, word for word, in any passage." in repair
    assert [c.source for c in filled.results[0].cited] == ["contingency-plan", "isms"]


@pytest.fixture
def looking_config(tmp_path: Path, config):
    """The same job, asking an answer that fell back to look once more."""
    folder = tmp_path / "job"
    (folder / "prompts" / "second_look.md").write_text(
        "Look again, part by part, or answer $fallback.", encoding="utf-8"
    )
    raw = json.loads((folder / "job.json").read_text(encoding="utf-8"))
    raw["second_look"] = {"prompt": "prompts/second_look.md"}
    (folder / "job.json").write_text(json.dumps(raw), encoding="utf-8")
    return load_config(folder / "job.json")


def test_an_answer_that_fell_back_is_asked_to_look_once_more(workbook, looking_config):
    """A second look may find the quote, which is then checked like any other; one that
    still falls back stays with a person."""
    asked: list[list[tuple[str, str]]] = []

    def ask(system, turns, schema, shared):
        if system.startswith("verify"):
            return ModelReply(json.dumps({"supported": True, "missing": ""}))
        asked.append(turns)
        looking = "Look again, part by part" in turns[-1][1]
        if looking and "contingency plan documented" in turns[0][1]:
            return _reply(QUOTE)
        return ModelReply(
            json.dumps(
                {
                    "quotes": [],
                    "answer": "Needs review",
                    "comment": "Not settled.",
                    "confidence": "low",
                }
            )
        )

    model = Model()
    model.ask = ask

    filled = fill_workbook(workbook, [PLAN], looking_config, model)

    virtualization, contingency = filled.results
    assert (contingency.answer, contingency.looked_again) == ("Yes", True)
    assert (virtualization.answer, virtualization.looked_again) == (
        "Needs review",
        True,
    )
    assert "Needs review." in asked[1][-1][1]
    assert len(asked) == 4


def test_a_pack_s_labels_set_the_standing_passages_apart():
    """The passages every question is shown come first, under the pack's label for them."""
    from modules.jobs.evidence.passages import passages_of
    from modules.jobs.workbook_rows.ask import passages_block

    passages = passages_of([PLAN, ISMS])

    block = passages_block(
        passages, [0, 1], [1], ("For all policies:", "For this one:")
    )

    assert block.index("For all policies:") < block.index("[2] isms")
    assert block.index("[2] isms") < block.index("For this one:")
    assert block.index("For this one:") < block.index("[1] contingency-plan")


def test_a_refused_answer_may_not_turn_into_another(workbook, config):
    """Refused, a Yes may find better evidence or give way; a switch to No goes to a person."""

    def ask(system, turns, schema, shared):
        if system.startswith("verify"):
            return ModelReply(json.dumps({"supported": False, "missing": "Off topic."}))
        if len(turns) == 1:
            return _reply(QUOTE)
        return ModelReply(
            json.dumps(
                {
                    "quotes": [{"passage": 1, "quote": QUOTE}],
                    "answer": "No",
                    "comment": "",
                    "confidence": "high",
                }
            )
        )

    model = Model()
    model.ask = ask

    filled = fill_workbook(workbook, [PLAN], config, model)

    result = filled.results[0]
    assert (result.answer, result.said) == ("Needs review", "Yes")
    assert result.codes == ["ANSWER_SWITCHED", "NEEDS_REVIEW"]
    assert [step["step"] for step in result.trace] == [
        "answer",
        "check",
        "after the check",
    ]


def test_a_fallback_that_says_why_is_not_asked_again(workbook, looking_config):
    """Only a doubtful fallback gets a second look: one that quotes nothing, is sure, and says
    what is open stays as it is."""
    asked: list[list[tuple[str, str]]] = []

    def ask(system, turns, schema, shared):
        asked.append(turns)
        return ModelReply(
            json.dumps(
                {
                    "quotes": [],
                    "answer": "Needs review",
                    "comment": "The plan says nothing of virtualization.",
                    "confidence": "high",
                }
            )
        )

    model = Model()
    model.ask = ask

    filled = fill_workbook(workbook, [PLAN], looking_config, model)

    assert [r.looked_again for r in filled.results] == [False, False]
    assert len(asked) == 2


def test_a_switched_answer_keeps_what_was_refused_and_why(workbook, config):
    """The switch goes to a person with the refused quotes and the check's reason, and the
    requester's comment cell gets that reason rather than either answer's claim."""

    def ask(system, turns, schema, shared):
        if system.startswith("verify"):
            return ModelReply(json.dumps({"supported": False, "missing": "Off topic."}))
        if len(turns) == 1:
            return _reply(QUOTE)
        return ModelReply(
            json.dumps(
                {
                    "quotes": [{"passage": 1, "quote": REVIEWED}],
                    "answer": "No",
                    "comment": "We never do this.",
                    "confidence": "high",
                }
            )
        )

    model = Model()
    model.ask = ask

    result = fill_workbook(workbook, [PLAN, ISMS], config, model).results[0]

    assert (result.said, result.missing) == ("Yes", "Off topic.")
    assert [c.quote for c in result.cited] == [QUOTE]
    assert comment_text(result, config) == "Off topic."


def test_an_empty_reply_is_asked_again_without_an_empty_assistant_turn(
    workbook, config
):
    """A call that came back empty is asked once more in a single user turn, never sent back
    as an empty assistant turn, which Anthropic's API refuses."""
    sent: list[list[tuple[str, str]]] = []

    def ask(system, turns, schema, shared):
        sent.append(list(turns))
        if system.startswith("verify"):
            return ModelReply(json.dumps({"supported": True, "missing": ""}))
        if len(sent) == 1:
            return ModelReply("")
        return _reply(QUOTE)

    model = Model()
    model.ask = ask

    result = fill_workbook(
        workbook, [PLAN, ISMS], config, model, only=lambda row: row.row == 3
    ).results[0]

    assert [role for role, _ in sent[1]] == ["user"]
    assert all(text.strip() for turns in sent for _, text in turns)
    assert result.answer == "Yes"


def test_a_refused_answer_kept_on_quotes_nowhere_in_the_sources_keeps_the_refusal(
    workbook, config
):
    """Asked again after a refusal, the model keeps its Yes on a quote no source holds: the
    row still shows the refused quote and the check's reason, not "no quote was found"."""

    def ask(system, turns, schema, shared):
        if system.startswith("verify"):
            return ModelReply(json.dumps({"supported": False, "missing": "Off topic."}))
        if len(turns) == 1:
            return _reply(QUOTE)
        return _reply("Every system is virtualized under a written security policy.")

    model = Model()
    model.ask = ask

    result = fill_workbook(workbook, [PLAN, ISMS], config, model).results[0]

    assert (result.answer, result.said, result.missing) == (
        "Needs review",
        "Yes",
        "Off topic.",
    )
    assert "NOT_SUPPORTED" in result.codes and "QUOTE_NOT_FOUND" not in result.codes
    assert [c.quote for c in result.cited] == [QUOTE]


@pytest.mark.parametrize(
    "fallback",
    [
        {
            "quotes": [{"passage": 1, "quote": QUOTE}],
            "comment": "Open.",
            "confidence": "high",
        },
        {"quotes": [], "comment": "", "confidence": "high"},
    ],
)
def test_a_fallback_that_quotes_or_says_nothing_gets_a_second_look(
    workbook, looking_config, fallback
):
    """Quoting something, or leaving the comment empty, marks a fallback as doubtful."""

    def ask(system, turns, schema, shared):
        return ModelReply(json.dumps({**fallback, "answer": "Needs review"}))

    model = Model()
    model.ask = ask

    filled = fill_workbook(workbook, [PLAN], looking_config, model)

    assert [r.looked_again for r in filled.results] == [True, True]


def test_a_cancel_during_embedding_stops_the_run(workbook, config, tmp_path):
    """A stop asked for while the library is embedded ends the run before any question."""
    from modules.jobs.workbook_rows.fill import FillStoppedError

    long = SourceText(
        9, "long", "\n\n".join(f"## P{n}\n\nWords {n}." for n in range(400))
    )
    stopping = json.loads((tmp_path / "job" / "job.json").read_text(encoding="utf-8"))
    stopping["max_whole_chars"] = 100
    (tmp_path / "job" / "job.json").write_text(json.dumps(stopping), encoding="utf-8")
    small = load_config(tmp_path / "job" / "job.json")
    calls = iter(range(10_000))

    def embed(texts, query):
        return [[1.0, 0.0] for _ in texts]

    with pytest.raises(FillStoppedError):
        fill_workbook(
            workbook,
            [long],
            small,
            Model(),
            embed=embed,
            stop=lambda: next(calls) >= 1,
        )


def test_a_malformed_standing_block_refuses_the_pack(tmp_path, config):
    """A pack whose standing block is not an object is refused as a bad config."""
    from modules.jobs.packs.manifest import PackRefusedError

    job = tmp_path / "job" / "job.json"
    raw = json.loads(job.read_text(encoding="utf-8"))
    raw["standing"] = "policies"
    job.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(PackRefusedError):
        load_config(job)


def test_the_check_reads_what_a_quote_s_ellipsis_leaves_out(workbook, config):
    """For a quote whose parts "..." joins, the second check is shown the source in full."""
    plan = SourceText(
        3,
        "contingency-plan",
        "## Plan\n\nThe procedures shall be documented, and for production only, "
        "in a formal contingency plan.",
    )
    claims: list[str] = []

    def ask(system, turns, schema, shared):
        if system.startswith("verify"):
            claims.append(turns[0][1])
            return ModelReply(json.dumps({"supported": True, "missing": ""}))
        return _reply(
            "The procedures shall be documented ... in a formal contingency plan."
        )

    model = Model()
    model.ask = ask

    fill_workbook(workbook, [plan], config, model)

    assert "for production only" in claims[0]


def test_an_unreadable_quote_repair_keeps_what_the_model_claimed(workbook, config):
    """A repair that cannot be read leaves the unfound answer, so the row says what it was."""

    def ask(system, turns, schema, shared):
        if len(turns) == 1:
            return _reply("Words that no policy of the firm holds anywhere at all.")
        return ModelReply("not json")

    model = Model()
    model.ask = ask

    result = fill_workbook(workbook, [PLAN], config, model).results[0]

    assert (result.answer, result.said, result.codes) == (
        "Needs review",
        "Yes",
        ["QUOTE_NOT_FOUND", "NEEDS_REVIEW"],
    )


def test_a_loose_quote_is_shown_the_sentence_it_meant_when_asked_again(
    workbook, config
):
    """The quote repair carries the closest source sentence for the model to copy."""
    repairs: list[str] = []

    def ask(system, turns, schema, shared):
        if system.startswith("verify"):
            return ModelReply(json.dumps({"supported": True, "missing": ""}))
        if len(turns) == 1:
            return _reply("The procedures are documented in a formal contingency plan.")
        repairs.append(turns[-1][1])
        return _reply(QUOTE)

    model = Model()
    model.ask = ask

    filled = fill_workbook(workbook, [PLAN], config, model)

    assert f'"{QUOTE}"' in repairs[0]
    assert [r.answer for r in filled.results] == ["Yes", "Yes"]


def test_a_pack_s_standing_passages_reach_the_prompt_under_its_label(
    workbook, tmp_path, config
):
    """From job.json to the prompt: the standing query's passage comes first, under the label."""
    job = tmp_path / "job" / "job.json"
    raw = json.loads(job.read_text(encoding="utf-8"))
    raw["max_whole_chars"] = 50
    raw["standing"] = {
        "queries": ["how every policy is reviewed and approved"],
        "label": "For all policies:",
        "then": "For this question:",
    }
    job.write_text(json.dumps(raw), encoding="utf-8")
    standing = load_config(job)
    prompts: list[str] = []

    def ask(system, turns, schema, shared):
        prompts.append(turns[0][1])
        return ModelReply(
            json.dumps(
                {
                    "quotes": [],
                    "answer": "Needs review",
                    "comment": "Open.",
                    "confidence": "high",
                }
            )
        )

    model = Model()
    model.ask = ask

    fill_workbook(workbook, [PLAN, ISMS], standing, model)

    first = next(p for p in prompts if "contingency plan documented" in p)
    assert (
        first.index("For all policies:")
        < first.index("isms")
        < first.index("For this question:")
    )


def test_one_question_whose_call_fails_goes_to_a_person_and_the_rest_are_answered(
    workbook, config
):
    """A call that fails outright on one row leaves that row to a person with the reason; the
    other rows are answered as usual."""

    def ask(system, turns, schema, shared):
        if "virtualization" in turns[0][1]:
            raise RuntimeError("400 Bad Request: prompt too long")
        return Model().ask(system, turns, schema, shared)

    model = Model()
    model.ask = ask

    failed, answered = fill_workbook(workbook, [PLAN, ISMS], config, model).results

    assert (failed.answer, failed.codes) == ("Needs review", ["CALL_FAILED"])
    assert "prompt too long" in failed.missing
    assert answered.answer == "Yes"


def test_a_call_that_fails_on_every_question_fails_the_run(workbook, config):
    """When no question can be asked, the connection is broken: the run fails rather than end
    as a sheet of rows left to a person."""

    def ask(system, turns, schema, shared):
        raise RuntimeError("401 Unauthorized")

    model = Model()
    model.ask = ask

    with pytest.raises(RuntimeError, match="401"):
        fill_workbook(workbook, [PLAN, ISMS], config, model)


GATE = {
    "answers": ["No"],
    "quote": r"\b(applies to|provided by|out of scope)\b",
    "comment": r"\bdocuments?\b[^.]{0,40}\bdo(es)?\s+not\s+state",
}
SCOPED = SourceText(
    5,
    "scope",
    "## Scope\n\nThis standard applies to laptops issued by the firm.\n\n"
    "## Rules\n\nStaff must not store client data on removable media.",
)


@pytest.fixture
def gated_config(tmp_path: Path, config):
    """The same job, with a statement gate on No and a second look that may only find a Yes."""
    folder = tmp_path / "job"
    (folder / "prompts" / "second_look.md").write_text(
        "Look again, part by part, or answer $fallback.", encoding="utf-8"
    )
    raw = json.loads((folder / "job.json").read_text(encoding="utf-8"))
    raw["statement_gate"] = GATE
    raw["second_look"] = {"prompt": "prompts/second_look.md", "answers": ["Yes"]}
    raw["verify"]["answers"] = ["Yes", "No"]
    (folder / "job.json").write_text(json.dumps(raw), encoding="utf-8")
    return load_config(folder / "job.json")


def _no(quote: str, comment: str = "We do not.") -> ModelReply:
    return ModelReply(
        json.dumps(
            {
                "quotes": [{"passage": 1, "quote": quote}] if quote else [],
                "answer": "No",
                "comment": comment,
                "confidence": "high",
            }
        )
    )


@pytest.mark.parametrize(
    ("reply", "why"),
    [
        (
            _no("This standard applies to laptops issued by the firm."),
            "scope or a provider",
        ),
        (
            _no(
                "Staff must not store client data on removable media.",
                comment="The documents do not state that virtualization is used.",
            ),
            "leave unsaid",
        ),
    ],
)
def test_a_no_resting_on_a_scope_or_on_silence_goes_to_a_person_unchecked(
    workbook, gated_config, reply, why
):
    """A No whose quote only limits a rule's scope, or whose comment says the documents are
    silent, is not a statement that the firm does not do it: no check can make it one."""
    checks: list[str] = []

    def ask(system, turns, schema, shared):
        if system.startswith("verify"):
            checks.append(turns[0][1])
            return ModelReply(json.dumps({"supported": True, "missing": ""}))
        return reply

    model = Model()
    model.ask = ask

    result = fill_workbook(
        workbook, [SCOPED], gated_config, model, only=lambda row: row.row == 2
    ).results[0]

    assert (result.answer, result.said) == ("Needs review", "No")
    assert result.codes[0] == "NO_STATEMENT" and why in result.missing
    assert checks == []


@pytest.mark.parametrize(
    ("supported", "answer"), [(True, "No"), (False, "Needs review")]
)
def test_a_no_on_a_stated_prohibition_goes_on_to_the_check(
    workbook, gated_config, supported, answer
):
    """A quote that forbids the thing is a statement: the gate lets it through to the check,
    which then decides, so a No the check refuses is not written."""
    checks: list[str] = []

    def ask(system, turns, schema, shared):
        if system.startswith("verify"):
            checks.append(turns[0][1])
            return ModelReply(
                json.dumps({"supported": supported, "missing": "Off topic."})
            )
        return _no("Staff must not store client data on removable media.")

    model = Model()
    model.ask = ask

    result = fill_workbook(
        workbook, [SCOPED], gated_config, model, only=lambda row: row.row == 2
    ).results[0]

    assert result.answer == answer and "NO_STATEMENT" not in result.codes
    assert len(checks) == (1 if supported else 2)


def test_a_refused_no_asked_again_onto_a_scope_keeps_its_refusal(
    workbook, gated_config
):
    """Asked for better evidence, a refused No that now rests on a scope sentence is held by
    the gate on that turn too: the refusal stands, and no second check is asked."""
    checks: list[str] = []

    def ask(system, turns, schema, shared):
        if system.startswith("verify"):
            checks.append(turns[0][1])
            return ModelReply(json.dumps({"supported": False, "missing": "Off topic."}))
        if len(turns) == 1:
            return _no("Staff must not store client data on removable media.")
        return _no("This standard applies to laptops issued by the firm.")

    model = Model()
    model.ask = ask

    result = fill_workbook(
        workbook, [SCOPED], gated_config, model, only=lambda row: row.row == 2
    ).results[0]

    assert (result.answer, result.said, result.missing) == (
        "Needs review",
        "No",
        "Off topic.",
    )
    assert "NOT_SUPPORTED" in result.codes and len(checks) == 1
    assert [c.quote for c in result.cited] == [
        "Staff must not store client data on removable media."
    ]
    assert "statement gate" in [step["step"] for step in result.trace]


def test_the_gate_reads_a_quote_by_its_words(workbook, gated_config):
    """A scope phrase split by a hyphen or a line break in the source is caught as surely as
    the phrase itself, and the comment cell says why in a sentence of its own."""
    hyphened = SourceText(
        6,
        "hyphened",
        "## Scope\n\nContractors' laptops are out-of-scope\nfor this standard.",
    )

    def ask(system, turns, schema, shared):
        if system.startswith("verify"):
            return ModelReply(json.dumps({"supported": True, "missing": ""}))
        return _no("Contractors' laptops are out-of-scope for this standard.")

    model = Model()
    model.ask = ask

    result = fill_workbook(
        workbook, [hyphened], gated_config, model, only=lambda row: row.row == 2
    ).results[0]

    assert result.codes[0] == "NO_STATEMENT"
    assert comment_text(result, gated_config).startswith("The only evidence for No")


def test_a_second_look_that_turns_caution_into_a_no_keeps_the_caution(
    workbook, gated_config
):
    """The second look is asked for evidence of what the question asks; a No it gives
    instead falls back to the first answer, which goes to a person."""

    def ask(system, turns, schema, shared):
        if system.startswith("verify"):
            return ModelReply(json.dumps({"supported": True, "missing": ""}))
        if "Look again, part by part" in turns[-1][1]:
            return _no("Staff must not store client data on removable media.")
        return ModelReply(
            json.dumps(
                {
                    "quotes": [],
                    "answer": "Needs review",
                    "comment": "",
                    "confidence": "low",
                }
            )
        )

    model = Model()
    model.ask = ask

    result = fill_workbook(
        workbook, [SCOPED], gated_config, model, only=lambda row: row.row == 2
    ).results[0]

    assert result.looked_again and result.answer == "Needs review"
    assert [step["step"] for step in result.trace][:2] == ["answer", "second look"]
