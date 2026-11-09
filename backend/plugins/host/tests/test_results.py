"""A tool's result as the agent reads it: every item in the text, within a byte cap."""

import json
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import Context

from host.app import host_app
from host.tests.mcp_calls import call
from host.tests.serving import serving
from mcp_server.results import more_line, tool_result, wants_text_only

PLUGINS = Path(__file__).parent / "shared_layer_plugins"


def whole(item: dict[str, Any]) -> dict[str, Any]:
    return item


def text(result: Any) -> str:
    return result.content[0].text


def test_each_item_is_a_compact_json_line_after_the_summary() -> None:
    items = [
        {"title": "Lamp", "price": 12.5, "seller": "Acme", "html": "<div>"},
        {"title": "Desk", "price": None, "seller": "Acme"},
    ]

    result = tool_result(
        "2 products",
        items,
        project=lambda item: {key: item.get(key) for key in ("title", "price")},
    )

    assert text(result) == (
        '2 products\n{"title":"Lamp","price":12.5}\n{"title":"Desk"}'
    )
    assert result.structured_content == {"items": items}


def test_nulls_and_empty_values_are_dropped_at_any_depth() -> None:
    item = {
        "a": None,
        "b": "",
        "c": [],
        "d": {},
        "e": {"f": None, "g": 0, "h": False},
        "i": [None, 1, {"j": None}],
    }

    assert text(tool_result("s", [item], project=whole)) == (
        's\n{"e":{"g":0,"h":false},"i":[1]}'
    )


def test_long_strings_are_clipped() -> None:
    result = tool_result("s", [{"text": "x" * 5000}], project=whole, clip_chars=100)

    assert json.loads(text(result).split("\n")[1]) == {"text": "x" * 100 + "…"}


def test_the_text_stops_before_the_byte_cap_and_counts_what_is_left() -> None:
    items = [{"title": f"product {i}", "about": "d" * 200} for i in range(100)]

    body = text(tool_result("100 products", items, project=whole, max_text_bytes=2000))

    lines = body.split("\n")
    shown = len(lines) - 2
    assert len(body.encode()) <= 2000
    assert shown > 0
    assert [json.loads(line)["title"] for line in lines[1:-1]] == [
        f"product {i}" for i in range(shown)
    ]
    assert lines[-1] == (f"{100 - shown} more items not shown: this reply is full")


def test_items_that_all_fit_have_no_count_line() -> None:
    items = [{"title": f"product {i}"} for i in range(3)]
    exact = len(text(tool_result("3 products", items, project=whole)).encode())

    body = text(tool_result("3 products", items, project=whole, max_text_bytes=exact))

    assert len(body.split("\n")) == 4
    assert "more items" not in body


def test_one_item_longer_than_the_cap_shows_what_fits_of_it() -> None:
    """A crawled page longer than the cap still gives the agent its start."""
    items = [
        {"url": "https://example.com", "markdown": "m" * 10_000},
        {"url": "https://example.com/next", "markdown": "n" * 10_000},
    ]

    body = text(
        tool_result(
            "2 pages", items, project=whole, max_text_bytes=3000, clip_chars=50_000
        )
    )

    lines = body.split("\n")
    page = json.loads(lines[1])
    assert len(body.encode()) <= 3000
    assert page["url"] == "https://example.com"
    assert page["markdown"].startswith("mmm")
    assert page["markdown"].endswith("…")
    assert lines[-1] == more_line(1)


def test_one_item_long_from_many_short_strings_shows_its_start() -> None:
    """A place with its reviews: no one string can take the excess, so the line is cut."""
    reviews = [
        {"author": f"reviewer {i}", "text": f"review {i}: " + "great coffee " * 27}
        for i in range(200)
    ]
    items = [{"name": "Cafe", "reviews": reviews}]

    body = text(tool_result("1 place", items, project=dict))

    lines = body.split("\n")
    assert len(body.encode()) <= 32_000
    assert len(lines) == 2
    assert lines[1].startswith('{"name":"Cafe","reviews":[{"author":"reviewer 0",')
    # The first reviews are whole, not cut to an ellipsis each.
    assert '"reviewer 1","text":"review 1: great coffee' in lines[1]
    assert lines[1].endswith("…")
    assert "more items" not in body


def test_a_long_list_first_item_is_cut_and_the_next_still_has_its_place() -> None:
    """The room kept for a count line holds a short last item after the cut one."""
    segments = [{"start": i * 2.5, "text": f"segment {i}"} for i in range(3000)]
    items = [{"title": "Talk", "transcript": segments}, {"title": "Next"}]

    body = text(tool_result("2 videos", items, project=dict, max_text_bytes=5000))

    lines = body.split("\n")
    assert len(body.encode()) <= 5000
    assert lines[1].startswith('{"title":"Talk","transcript":[{"start":0.0,')
    assert lines[1].endswith("…")
    assert lines[2:] == ['{"title":"Next"}']


def test_items_past_the_cap_are_never_serialised() -> None:
    projected: list[int] = []

    def counted(item: dict[str, Any]) -> dict[str, Any]:
        projected.append(item["n"])
        return item

    items = [{"n": i, "about": "d" * 200} for i in range(10_000)]

    body = text(tool_result("s", items, project=counted, max_text_bytes=2000))

    assert len(body.encode()) <= 2000
    assert body.endswith("this reply is full")
    assert len(projected) < 20


def test_text_in_any_script_stays_under_the_cap() -> None:
    items = [{"title": 'Café ☕ 東京 "quoted"\n' * 40} for _ in range(50)]

    body = text(tool_result("s", items, project=whole, max_text_bytes=1500))

    assert len(body.encode()) <= 1500
    assert body.endswith("this reply is full")


def test_a_summary_longer_than_the_cap_is_cut_and_the_items_still_shown() -> None:
    body = text(tool_result("s" * 5000, [{"a": 1}], project=whole, max_text_bytes=1000))

    assert len(body.encode()) <= 1000
    assert body.endswith('…\n{"a":1}')


def test_text_only_leaves_out_the_structured_items() -> None:
    result = tool_result("1 product", [{"a": 1}], project=whole, text_only=True)

    assert result.structured_content is None
    assert text(result) == '1 product\n{"a":1}'


def test_text_only_is_off_outside_a_request() -> None:
    assert wants_text_only(None) is False
    assert wants_text_only(Context()) is False


async def test_through_the_host_the_agent_reads_every_item() -> None:
    with serving(host_app(PLUGINS, {"listing"})) as base:
        progress: list[float] = []
        result = await call(
            f"{base}/listing/mcp", "products", {"count": 3}, progress=progress
        )
        text_only = await call(
            f"{base}/listing/mcp",
            "products",
            {"count": 1},
            headers={"x-surfsense-text-only": "1"},
        )

    assert text(result) == (
        "3 products\n"
        '{"title":"p0","price":0}\n'
        '{"title":"p1","price":1}\n'
        '{"title":"p2","price":2}'
    )
    assert result.structured_content["items"][0] == {
        "title": "p0",
        "price": 0,
        "seller": None,
    }
    # The first stage, then the last item: the others came within the second.
    assert progress == [0.5, 3.0]
    assert text(text_only) == '1 products\n{"title":"p0","price":0}'
    assert text_only.structured_content is None
