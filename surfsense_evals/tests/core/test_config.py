"""Tests for env loading + state.json read/write."""

from __future__ import annotations

import json

from surfsense_evals.core.config import (
    DEFAULT_SCENARIO,
    SCENARIOS,
    SuiteState,
    clear_suite_state,
    get_suite_state,
    load_config,
    set_suite_state,
)


def test_load_config_defaults_to_localhost(tmp_env):  # noqa: ARG001
    config = load_config()
    assert config.surfsense_api_base == "http://localhost:8000"
    assert config.has_jwt_mode() is False
    assert config.has_local_mode() is False
    assert config.credential_mode() == "none"


def test_load_config_picks_up_jwt_env(tmp_env, monkeypatch):  # noqa: ARG001
    monkeypatch.setenv("SURFSENSE_JWT", "tok")
    config = load_config()
    assert config.credential_mode() == "jwt"


def test_load_config_picks_up_local_env(tmp_env, monkeypatch):  # noqa: ARG001
    monkeypatch.setenv("SURFSENSE_USER_EMAIL", "u@x.com")
    monkeypatch.setenv("SURFSENSE_USER_PASSWORD", "pw")
    config = load_config()
    assert config.credential_mode() == "local"


def test_state_roundtrip_per_suite(tmp_env):  # noqa: ARG001
    config = load_config()
    assert get_suite_state(config, "medical") is None
    state = SuiteState(
        search_space_id=1,
        agent_llm_id=-10042,
        provider_model="anthropic/claude-sonnet-4.5",
        created_at="2026-05-11T20-30-00Z",
    )
    set_suite_state(config, "medical", state)
    legal = SuiteState(
        search_space_id=2,
        agent_llm_id=-1,
        provider_model="openai/gpt-5",
        created_at="2026-05-11T21-00-00Z",
    )
    set_suite_state(config, "legal", legal)

    fetched = get_suite_state(config, "medical")
    assert fetched.search_space_id == 1
    assert fetched.provider_model == "anthropic/claude-sonnet-4.5"

    # Other suite untouched after teardown.
    cleared = clear_suite_state(config, "medical")
    assert cleared is True
    assert get_suite_state(config, "medical") is None
    assert get_suite_state(config, "legal").search_space_id == 2

    raw = json.loads(config.state_path.read_text(encoding="utf-8"))
    assert "medical" not in raw["suites"]
    assert "legal" in raw["suites"]


def test_paths_are_per_suite(tmp_env):  # noqa: ARG001
    config = load_config()
    a = config.suite_data_dir("medical")
    b = config.suite_data_dir("legal")
    assert a != b
    assert config.suite_reports_dir("medical").parent == config.reports_dir
    assert config.suite_runs_dir("medical").name == "runs"
    assert config.suite_maps_dir("medical").name == "maps"


# ---------------------------------------------------------------------------
# Scenario state — back-compat + new fields
# ---------------------------------------------------------------------------


def test_legacy_state_back_compat_defaults_to_head_to_head():
    """state.json files written before scenarios shipped must still load.

    Missing ``scenario`` / ``vision_*`` / ``native_arm_model`` keys all
    default to ``head-to-head`` / ``None`` so old setups keep working
    after upgrade — the runner's behaviour exactly mirrors the legacy
    one (both arms answer with ``provider_model``).
    """

    legacy = {
        "search_space_id": 7,
        "agent_llm_id": -123,
        "provider_model": "anthropic/claude-sonnet-4.5",
        "created_at": "2026-05-11T20-30-00Z",
        "ingestion_maps": {},
    }
    state = SuiteState.from_dict(legacy)
    assert state.scenario == DEFAULT_SCENARIO == "head-to-head"
    assert state.vision_llm_config_id is None
    assert state.vision_provider_model is None
    assert state.native_arm_model is None
    # The native arm should still answer with the same slug as SurfSense.
    assert state.effective_native_arm_model == state.provider_model


def test_unknown_scenario_falls_back_to_default():
    """Garbage scenario in state.json → default, not crash.

    Defensive: we'd rather a stale state file render with the safe
    head-to-head behaviour than break the whole run with a KeyError.
    """

    payload = {
        "search_space_id": 1,
        "agent_llm_id": -1,
        "provider_model": "openai/gpt-5",
        "scenario": "unknown-scenario-name",
    }
    state = SuiteState.from_dict(payload)
    assert state.scenario == DEFAULT_SCENARIO


def test_cost_arbitrage_state_persists_native_arm_model(tmp_env):  # noqa: ARG001
    config = load_config()
    state = SuiteState(
        search_space_id=42,
        agent_llm_id=-1,
        provider_model="openai/gpt-5.4-mini",
        created_at="2026-05-11T20-30-00Z",
        scenario="cost-arbitrage",
        vision_llm_config_id=-101,
        vision_provider_model="anthropic/claude-sonnet-4.5",
        native_arm_model="anthropic/claude-sonnet-4.5",
    )
    set_suite_state(config, "medical", state)

    fetched = get_suite_state(config, "medical")
    assert fetched.scenario == "cost-arbitrage"
    assert fetched.vision_llm_config_id == -101
    assert fetched.vision_provider_model == "anthropic/claude-sonnet-4.5"
    assert fetched.native_arm_model == "anthropic/claude-sonnet-4.5"
    # Cost arbitrage's whole point: native arm slug != surfsense slug.
    assert fetched.effective_native_arm_model != fetched.provider_model
    assert fetched.effective_native_arm_model == "anthropic/claude-sonnet-4.5"

    raw = json.loads(config.state_path.read_text(encoding="utf-8"))
    assert raw["suites"]["medical"]["scenario"] == "cost-arbitrage"


def test_scenario_constants_are_stable():
    """Pin the public scenario list; runners + tests key off these strings."""

    assert SCENARIOS == ("head-to-head", "symmetric-cheap", "cost-arbitrage")
    assert DEFAULT_SCENARIO == "head-to-head"
