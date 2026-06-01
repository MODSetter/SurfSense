"""Lock the public template-rendering surface: render, predicate, recursive."""

from __future__ import annotations

import pytest
from jinja2 import UndefinedError

from app.automations.templating.render import (
    evaluate_predicate,
    render_template,
    render_value,
)

pytestmark = pytest.mark.unit


def test_render_template_substitutes_context_variables() -> None:
    """A template referencing a context variable produces the substituted
    string. Most basic contract of the template engine."""
    result = render_template("Hello {{ name }}!", {"name": "World"})

    assert result == "Hello World!"


def test_render_template_raises_on_undefined_variable() -> None:
    """Referencing a variable that isn't in the context raises rather than
    rendering the empty string. Locks the StrictUndefined safety net so
    template typos surface as run failures instead of silent corruption."""
    with pytest.raises(UndefinedError):
        render_template("Hello {{ missing }}!", {})


def test_evaluate_predicate_returns_truthy_outcome_of_expression() -> None:
    """``evaluate_predicate`` compiles a Jinja **expression** (not template
    body) and coerces the value to ``bool``. Drives ``step.when`` gating."""
    assert evaluate_predicate("inputs.count > 0", {"inputs": {"count": 3}}) is True
    assert evaluate_predicate("inputs.count > 0", {"inputs": {"count": 0}}) is False


def test_render_value_renders_strings_recursively_through_dicts_and_lists() -> None:
    """``render_value`` walks dicts and lists, renders string leaves through
    the template engine, and leaves non-strings untouched. This is the
    primitive ``execute_step`` uses to render step params at run time."""
    context = {"inputs": {"name": "World"}, "topic": "weekly"}

    rendered = render_value(
        {
            "greeting": "Hello {{ inputs.name }}",
            "tags": ["{{ topic }}", "static"],
            "config": {"retries": 3, "label": "{{ topic }}-{{ inputs.name }}"},
        },
        context,
    )

    assert rendered == {
        "greeting": "Hello World",
        "tags": ["weekly", "static"],
        "config": {"retries": 3, "label": "weekly-World"},
    }
