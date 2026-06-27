from __future__ import annotations

import importlib
import operator
import sys
import types
from typing import Annotated, Any

import pytest
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

pytestmark = pytest.mark.unit

_GRAPH_MODULE = "app.agents.video_presentation.graph"
_NODES_MODULE = "app.agents.video_presentation.nodes"
_TARGET_NODE = "generate_slide_scene_codes"
_BARRIER_SOURCES = ("create_slide_audio", "assign_slide_themes")


class _DelayedState(TypedDict, total=False):
    calls: Annotated[list[str], operator.add]
    audio_ready: bool
    themes_ready: bool


def _config(thread_id: str = "video-presentation-graph-test") -> dict[str, Any]:
    return {
        "configurable": {
            "search_space_id": 1,
            "thread_id": thread_id,
            "video_title": "Test deck",
        }
    }


def _input_state() -> dict[str, Any]:
    return {"db_session": None, "source_content": "source material"}


def _build_video_graph(monkeypatch: pytest.MonkeyPatch, calls: list[str]):
    nodes = types.ModuleType(_NODES_MODULE)

    async def create_presentation_slides(_state, config):
        _ = config
        calls.append("create_presentation_slides")
        return {"slides": [{"slide_number": 1, "title": "Intro"}]}

    async def create_slide_audio(_state, config):
        _ = config
        calls.append("create_slide_audio")
        return {"slide_audio_results": [{"slide_number": 1}]}

    async def assign_slide_themes(_state, config):
        _ = config
        calls.append("assign_slide_themes")
        return {"slide_theme_assignments": {1: ("corporate", "light")}}

    async def generate_slide_scene_codes(state, config):
        _ = config
        calls.append(_TARGET_NODE)
        assert state.slide_audio_results == [{"slide_number": 1}]
        assert state.slide_theme_assignments == {1: ("corporate", "light")}
        return {"slide_scene_codes": [{"slide_number": 1, "code": "", "title": ""}]}

    nodes.create_presentation_slides = create_presentation_slides
    nodes.create_slide_audio = create_slide_audio
    nodes.assign_slide_themes = assign_slide_themes
    nodes.generate_slide_scene_codes = generate_slide_scene_codes

    monkeypatch.setitem(sys.modules, _NODES_MODULE, nodes)
    monkeypatch.delitem(sys.modules, _GRAPH_MODULE, raising=False)

    graph_module = importlib.import_module(_GRAPH_MODULE)
    return graph_module.build_graph()


@pytest.mark.asyncio
async def test_video_presentation_graph_generates_scene_codes_once(monkeypatch):
    calls: list[str] = []
    graph = _build_video_graph(monkeypatch, calls)

    await graph.ainvoke(_input_state(), _config())

    assert calls.count(_TARGET_NODE) == 1
    scene_index = calls.index(_TARGET_NODE)
    assert calls.index("create_slide_audio") < scene_index
    assert calls.index("assign_slide_themes") < scene_index


def test_video_presentation_graph_registers_single_barrier_trigger(monkeypatch):
    graph = _build_video_graph(monkeypatch, [])

    assert graph.builder.waiting_edges == {(_BARRIER_SOURCES, _TARGET_NODE)}
    assert not {
        edge
        for edge in graph.builder.edges
        if edge[0] in _BARRIER_SOURCES and edge[1] == _TARGET_NODE
    }

    join_channel = f"join:{'+'.join(_BARRIER_SOURCES)}:{_TARGET_NODE}"
    assert join_channel in graph.channels
    assert graph.nodes[_TARGET_NODE].triggers.count(join_channel) == 1


@pytest.mark.asyncio
async def test_barrier_fires_once_when_one_branch_finishes_a_superstep_later():
    def create_presentation_slides(_state):
        return {"calls": ["create_presentation_slides"]}

    def create_slide_audio(_state):
        return {"calls": ["create_slide_audio"]}

    def finish_slide_audio(_state):
        return {"calls": ["finish_slide_audio"], "audio_ready": True}

    def assign_slide_themes(_state):
        return {"calls": ["assign_slide_themes"], "themes_ready": True}

    def generate_slide_scene_codes(state):
        assert state["audio_ready"] is True
        assert state["themes_ready"] is True
        return {"calls": [_TARGET_NODE]}

    workflow = StateGraph(_DelayedState)
    workflow.add_node("create_presentation_slides", create_presentation_slides)
    workflow.add_node("create_slide_audio", create_slide_audio)
    workflow.add_node("finish_slide_audio", finish_slide_audio)
    workflow.add_node("assign_slide_themes", assign_slide_themes)
    workflow.add_node(_TARGET_NODE, generate_slide_scene_codes)

    workflow.add_edge(START, "create_presentation_slides")
    workflow.add_edge("create_presentation_slides", "create_slide_audio")
    workflow.add_edge("create_presentation_slides", "assign_slide_themes")
    workflow.add_edge("create_slide_audio", "finish_slide_audio")
    workflow.add_edge(["finish_slide_audio", "assign_slide_themes"], _TARGET_NODE)
    workflow.add_edge(_TARGET_NODE, END)

    result = await workflow.compile().ainvoke({"calls": []})

    calls = result["calls"]
    assert calls.count(_TARGET_NODE) == 1
    assert calls.index("assign_slide_themes") < calls.index(_TARGET_NODE)
    assert calls.index("finish_slide_audio") < calls.index(_TARGET_NODE)
