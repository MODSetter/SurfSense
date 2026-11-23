"""A document script is checked before it runs: open brackets are closed with a note, any other
syntax error comes back with its line, a caret and a hint."""

import ast

import pytest

from modules.agent.tool_endpoint.script_check import ScriptSyntaxError, checked_script

pytestmark = pytest.mark.unit


def test_a_script_that_parses_is_run_as_written_with_no_note() -> None:
    """Most scripts: nothing changes and the result says nothing more."""
    script = 'from surfsense_docs import Doc\n\nDoc("Brief").save()\n'

    assert checked_script(script) == (script, None)


def test_a_script_sent_inside_a_markdown_fence_runs_without_it() -> None:
    """Small models wrap the script as they would in a chat reply."""
    script, note = checked_script('```python\nprint("x")\n```')

    assert script == 'print("x")'
    assert note is not None and "Markdown fence" in note


def test_a_call_left_open_at_the_end_is_closed_and_the_note_names_its_line() -> None:
    """The commonest slip: the last table call of a long script missing its `)`."""
    script = (
        "from surfsense_docs import Doc\n"
        'doc = Doc("Budget")\n'
        'doc.table(["Item", "Cost"], [["Beds", 1200], ["Soil", 450]]\n'
    )

    fixed, note = checked_script(script)

    ast.parse(fixed)
    assert fixed.rstrip().endswith("]])")
    assert note is not None
    assert "closed the ( opened on line 3 at the end of the script" in note
    assert note.endswith("Check that the result is what you meant.")


def test_an_inner_bracket_left_open_is_closed_before_the_outer_one() -> None:
    """The rows' `]` goes in where the call's `)` showed it was missing."""
    script = 'doc.table(["Item", "Cost"], [["Beds", 1200], ["Soil", 450])\ndoc.save()\n'

    fixed, note = checked_script(script)

    assert fixed.splitlines() == [
        'doc.table(["Item", "Cost"], [["Beds", 1200], ["Soil", 450]])',
        "doc.save()",
    ]
    assert note is not None
    assert "closed the [ opened on line 1 before the ) on line 1" in note


def test_a_closing_bracket_with_no_opening_one_is_not_guessed_at() -> None:
    """Removing a bracket could change what the script means: the model fixes it."""
    with pytest.raises(ScriptSyntaxError) as refused:
        checked_script('print("x"))\n')

    message = str(refused.value)
    assert message.startswith("The script does not parse, so it was not run. Line 1:")
    assert "this closing bracket has no opening one" in message


def test_any_other_syntax_error_comes_back_with_its_line_a_caret_and_a_hint() -> None:
    """The model learns where and how without a run."""
    script = 'title = "Brief"\nif title\n    print(title)\n'

    with pytest.raises(ScriptSyntaxError) as refused:
        checked_script(script)

    message = str(refused.value)
    assert "Line 2: expected ':'." in message
    assert ">    2 | if title" in message
    assert any(line.strip() == "^" for line in message.splitlines())
    assert message.endswith(
        "Hint: add the colon this line needs. Fix it and render again."
    )
