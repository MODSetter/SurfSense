"""Lock the sandbox boundary: disallowed filters/tests reject, finalize coerces non-strings.

These behaviors live in ``environment.py`` but are observed through the
public ``render_template`` surface — the same surface every step uses.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from jinja2.exceptions import TemplateError

from app.automations.templating.render import render_template

pytestmark = pytest.mark.unit


def test_environment_rejects_filters_not_in_the_allowlist() -> None:
    """A template that pipes through a Jinja built-in **not** in the
    allowlist (e.g. ``pprint``) must fail rather than rendering. Locks
    the sandbox surface against accidental re-introduction of removed
    filters."""
    with pytest.raises(TemplateError):
        render_template("{{ value | pprint }}", {"value": {"k": 1}})


def test_environment_finalizes_datetime_output_to_iso_string() -> None:
    """A datetime that lands directly at an output site is stringified
    via ``isoformat()`` rather than producing ``str(datetime)`` (which
    has a space separator). Locks the wire shape templates produce
    when emitting ``inputs.fired_at`` and other datetime values."""
    dt = datetime(2026, 5, 28, 14, 30, tzinfo=UTC)

    assert (
        render_template("{{ moment }}", {"moment": dt}) == "2026-05-28T14:30:00+00:00"
    )


def test_environment_finalizes_none_output_to_empty_string() -> None:
    """A ``None`` at an output site becomes the empty string. Lets
    templates write ``{{ inputs.last_fired_at }}`` unconditionally on
    the first run without exploding on the null."""
    assert render_template("{{ missing }}", {"missing": None}) == ""


def test_environment_finalizes_dict_output_to_json() -> None:
    """A dict at an output site is JSON-serialized. Same for lists.
    Locks the wire shape so users embedding structured values into
    prompts get deterministic, parseable output."""
    rendered = render_template("{{ payload }}", {"payload": {"a": 1, "b": [2, 3]}})

    assert rendered == '{"a": 1, "b": [2, 3]}'
