"""The submission form and the intake that reads it agree on every question and choice."""

import re
from pathlib import Path

from registry_check.submission import issue_form as form

TEMPLATE = (
    Path(__file__).resolve().parents[5] / ".github/ISSUE_TEMPLATE/plugin-submit.yml"
)


def test_every_question_the_intake_reads_is_on_the_form():
    text = TEMPLATE.read_text(encoding="utf-8")
    questions = set(re.findall(r"^      label: (.+)$", text, re.MULTILINE))
    read = {
        value
        for name, value in vars(form).items()
        if name.isupper()
        and not name.startswith("_")
        and isinstance(value, str)
        and name not in {"FREE", "PAID"}
    }
    assert read <= questions


def test_both_access_choices_are_offered():
    text = TEMPLATE.read_text(encoding="utf-8")
    # A choice with a colon in it is quoted, or YAML reads it as a mapping.
    choices = {
        c.strip('"') for c in re.findall(r"^        - (.+)$", text, re.MULTILINE)
    }
    assert {form.FREE, form.PAID} <= choices
