"""`submission`: what the intake workflow posts on the issue, and the entry it writes once accepted."""

import json

from registry_check.__main__ import main
from registry_check.static.checked_list import problems_in
from registry_check.submission.listing import list_submission
from registry_check.submission.submission_check import Submission
from registry_check.submission.submission_comment import submission_comment
from tests.registry_files import SQUARE_SVG, valid_entry, write_registry


def accepted_entry():
    return valid_entry(id="acme-docs", name="Acme Docs", icon="acme-docs.svg")


def test_a_blank_form_is_answered_with_each_question_to_fill(tmp_path):
    registry, first_party = write_registry(tmp_path, [])
    issue = tmp_path / "issue.md"
    issue.write_text("### Plugin name\n\n_No response_\n")
    comment = tmp_path / "comment.md"
    code = main(
        [
            "submission",
            "--issue", str(issue),
            "--comment", str(comment),
            "--registry", str(registry),
            "--first-party", str(first_party),
        ]
    )  # fmt: skip
    assert code == 1
    assert "- **Plugin name:** required" in comment.read_text()


def test_a_passing_submission_shows_its_entry_and_what_happens_next():
    text = submission_comment(Submission(accepted_entry(), icon=SQUARE_SVG))
    assert '"id": "acme-docs"' in text
    assert "registry: accept" in text


def test_a_problem_carrying_submitted_text_cannot_mention_or_mark_up():
    text = submission_comment(Submission(None, problems=["Tool names: '@team <b>'"]))
    assert "@team" not in text
    assert "<b>" not in text


def test_an_accepted_submission_is_listed_with_its_icon_and_passes_the_rules(
    tmp_path,
):
    registry, first_party = write_registry(tmp_path, [valid_entry()])
    list_submission(Submission(accepted_entry(), icon=SQUARE_SVG), registry)
    plugins = json.loads(registry.read_text())["plugins"]
    assert [e["id"] for e in plugins] == ["acme", "acme-docs"]
    assert (tmp_path / "icons" / "acme-docs.svg").read_bytes() == SQUARE_SVG
    assert registry.read_text().endswith("}\n")
    assert problems_in(registry, first_party) == []


def test_a_failing_submission_still_shows_its_notes():
    text = submission_comment(
        Submission(None, problems=["Privacy policy URL: required"], warnings=["x: y"])
    )
    assert "- x: y" in text
