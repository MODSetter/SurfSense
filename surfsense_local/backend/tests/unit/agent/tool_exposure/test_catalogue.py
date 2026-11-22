"""The line each ready plugin gets in the agent's instructions, so nothing ready is unknown to it."""

import pytest

from modules.agent.tool_exposure.catalogue import CataloguedPlugin, catalogue

pytestmark = pytest.mark.unit


def test_every_plugin_is_named_with_its_tools_and_how_to_load_them() -> None:
    """One line per plugin, its tools named, under how to load them."""
    text = catalogue(
        [
            CataloguedPlugin("linear", "Linear", "Issue tracking.", ["create_issue"]),
            CataloguedPlugin("gcal", "Google Calendar", "", ["list_events"]),
        ]
    )

    assert "Linear (@linear): Issue tracking. Tools: linear_create_issue" in text
    assert "Google Calendar (@gcal). Tools: gcal_list_events" in text
    assert "surfsense_open_plugin" in text
    assert "surfsense_find_tools" in text


def test_a_plugin_that_cannot_be_reached_says_so() -> None:
    """Its line stays, so the agent can say why, but names no tools to load."""
    text = catalogue(
        [CataloguedPlugin("linear", "Linear", "Issues.", ["a"], reachable=False)]
    )

    assert "Linear (@linear): cannot be reached now." in text
    assert "linear_a" not in text


def test_tool_names_are_left_out_before_any_plugin_is() -> None:
    """Every plugin keeps its line; names fill what room is left."""
    many = [
        CataloguedPlugin(f"p{n}", f"Plugin {n}", "", [f"tool_{i}" for i in range(80)])
        for n in range(20)
    ]

    text = catalogue(many, room=4_000)

    assert len(text) <= 4_000
    for n in range(20):
        assert f"Plugin {n} (@p{n})" in text


def test_no_plugin_no_catalogue() -> None:
    """Nothing connected adds nothing to the instructions."""
    assert catalogue([]) == ""
