"""Tests for the agent feature-flag system."""

from __future__ import annotations

import pytest

from app.agents.new_chat.feature_flags import (
    AgentFeatureFlags,
    reload_for_tests,
)

pytestmark = pytest.mark.unit


def _clear_all(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [
        "SURFSENSE_DISABLE_NEW_AGENT_STACK",
        "SURFSENSE_ENABLE_CONTEXT_EDITING",
        "SURFSENSE_ENABLE_COMPACTION_V2",
        "SURFSENSE_ENABLE_RETRY_AFTER",
        "SURFSENSE_ENABLE_MODEL_FALLBACK",
        "SURFSENSE_ENABLE_MODEL_CALL_LIMIT",
        "SURFSENSE_ENABLE_TOOL_CALL_LIMIT",
        "SURFSENSE_ENABLE_TOOL_CALL_REPAIR",
        "SURFSENSE_ENABLE_DOOM_LOOP",
        "SURFSENSE_ENABLE_PERMISSION",
        "SURFSENSE_ENABLE_BUSY_MUTEX",
        "SURFSENSE_ENABLE_LLM_TOOL_SELECTOR",
        "SURFSENSE_ENABLE_SKILLS",
        "SURFSENSE_ENABLE_SPECIALIZED_SUBAGENTS",
        "SURFSENSE_ENABLE_KB_PLANNER_RUNNABLE",
        "SURFSENSE_ENABLE_ACTION_LOG",
        "SURFSENSE_ENABLE_REVERT_ROUTE",
        "SURFSENSE_ENABLE_STREAM_PARITY_V2",
        "SURFSENSE_ENABLE_PLUGIN_LOADER",
        "SURFSENSE_ENABLE_OTEL",
    ]:
        monkeypatch.delenv(name, raising=False)


def test_defaults_match_shipped_agent_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_all(monkeypatch)
    flags = reload_for_tests()
    assert isinstance(flags, AgentFeatureFlags)
    assert flags.disable_new_agent_stack is False
    assert flags.enable_context_editing is True
    assert flags.enable_compaction_v2 is True
    assert flags.enable_retry_after is True
    assert flags.enable_model_fallback is False
    assert flags.enable_model_call_limit is True
    assert flags.enable_tool_call_limit is True
    assert flags.enable_tool_call_repair is True
    assert flags.enable_doom_loop is True
    assert flags.enable_permission is True
    assert flags.enable_busy_mutex is True
    assert flags.enable_llm_tool_selector is False
    assert flags.enable_skills is True
    assert flags.enable_specialized_subagents is True
    assert flags.enable_kb_planner_runnable is True
    assert flags.enable_action_log is True
    assert flags.enable_revert_route is True
    assert flags.enable_stream_parity_v2 is True
    assert flags.enable_plugin_loader is False
    assert flags.enable_otel is False
    assert flags.any_new_middleware_enabled() is True


def test_master_kill_switch_overrides_individual_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_all(monkeypatch)
    monkeypatch.setenv("SURFSENSE_DISABLE_NEW_AGENT_STACK", "true")
    monkeypatch.setenv("SURFSENSE_ENABLE_CONTEXT_EDITING", "true")
    monkeypatch.setenv("SURFSENSE_ENABLE_PERMISSION", "true")

    flags = reload_for_tests()
    assert flags.disable_new_agent_stack is True
    assert flags.enable_context_editing is False
    assert flags.enable_permission is False
    assert flags.any_new_middleware_enabled() is False


@pytest.mark.parametrize("truthy", ["1", "true", "TRUE", "yes", "on"])
def test_individual_flags_truthy_values(
    monkeypatch: pytest.MonkeyPatch, truthy: str
) -> None:
    _clear_all(monkeypatch)
    monkeypatch.setenv("SURFSENSE_ENABLE_RETRY_AFTER", truthy)
    flags = reload_for_tests()
    assert flags.enable_retry_after is True
    assert flags.any_new_middleware_enabled() is True


@pytest.mark.parametrize("falsy", ["0", "false", "no", "off", "", "garbage"])
def test_individual_flags_falsy_values(
    monkeypatch: pytest.MonkeyPatch, falsy: str
) -> None:
    _clear_all(monkeypatch)
    monkeypatch.setenv("SURFSENSE_ENABLE_RETRY_AFTER", falsy)
    flags = reload_for_tests()
    assert flags.enable_retry_after is False


def test_each_flag_can_be_set_independently(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_all(monkeypatch)
    flag_to_env = {
        "enable_context_editing": "SURFSENSE_ENABLE_CONTEXT_EDITING",
        "enable_compaction_v2": "SURFSENSE_ENABLE_COMPACTION_V2",
        "enable_retry_after": "SURFSENSE_ENABLE_RETRY_AFTER",
        "enable_model_fallback": "SURFSENSE_ENABLE_MODEL_FALLBACK",
        "enable_model_call_limit": "SURFSENSE_ENABLE_MODEL_CALL_LIMIT",
        "enable_tool_call_limit": "SURFSENSE_ENABLE_TOOL_CALL_LIMIT",
        "enable_tool_call_repair": "SURFSENSE_ENABLE_TOOL_CALL_REPAIR",
        "enable_doom_loop": "SURFSENSE_ENABLE_DOOM_LOOP",
        "enable_permission": "SURFSENSE_ENABLE_PERMISSION",
        "enable_busy_mutex": "SURFSENSE_ENABLE_BUSY_MUTEX",
        "enable_llm_tool_selector": "SURFSENSE_ENABLE_LLM_TOOL_SELECTOR",
        "enable_skills": "SURFSENSE_ENABLE_SKILLS",
        "enable_specialized_subagents": "SURFSENSE_ENABLE_SPECIALIZED_SUBAGENTS",
        "enable_kb_planner_runnable": "SURFSENSE_ENABLE_KB_PLANNER_RUNNABLE",
        "enable_action_log": "SURFSENSE_ENABLE_ACTION_LOG",
        "enable_revert_route": "SURFSENSE_ENABLE_REVERT_ROUTE",
        "enable_stream_parity_v2": "SURFSENSE_ENABLE_STREAM_PARITY_V2",
        "enable_plugin_loader": "SURFSENSE_ENABLE_PLUGIN_LOADER",
        "enable_otel": "SURFSENSE_ENABLE_OTEL",
    }

    for attr, env_name in flag_to_env.items():
        _clear_all(monkeypatch)
        monkeypatch.setenv(env_name, "false")
        flags = reload_for_tests()
        assert getattr(flags, attr) is False, f"{attr} did not flip off for {env_name}"
