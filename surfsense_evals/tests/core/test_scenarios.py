"""Tests for the shared scenario formatter used in head-to-head reports."""

from __future__ import annotations

from surfsense_evals.core.scenarios import format_scenario_md


def test_head_to_head_renders_both_arms_same_slug():
    extra = {
        "scenario": "head-to-head",
        "provider_model": "anthropic/claude-sonnet-4.5",
    }
    line = format_scenario_md(extra)
    assert "head-to-head" in line
    assert "anthropic/claude-sonnet-4.5" in line


def test_head_to_head_includes_vision_slug_when_recorded():
    extra = {
        "scenario": "head-to-head",
        "provider_model": "anthropic/claude-sonnet-4.5",
        "vision_provider_model": "anthropic/claude-sonnet-4.5",
    }
    line = format_scenario_md(extra)
    assert "ingest VLM" in line
    assert "claude-sonnet-4.5" in line


def test_symmetric_cheap_calls_out_native_arm_disadvantage():
    extra = {
        "scenario": "symmetric-cheap",
        "provider_model": "openai/gpt-5.4-mini",
        "vision_provider_model": "anthropic/claude-sonnet-4.5",
    }
    line = format_scenario_md(extra)
    assert "**symmetric-cheap**" in line
    assert "gpt-5.4-mini" in line
    # The "structurally loses" disclaimer must be there so reviewers
    # don't read this as a fair comparison.
    assert "structurally loses" in line.lower() or "structurally_loses" in line.lower()


def test_cost_arbitrage_distinguishes_native_and_surfsense_slugs():
    extra = {
        "scenario": "cost-arbitrage",
        "provider_model": "openai/gpt-5.4-mini",
        "native_arm_model": "anthropic/claude-sonnet-4.5",
        "vision_provider_model": "anthropic/claude-sonnet-4.5",
    }
    line = format_scenario_md(extra)
    assert "**cost-arbitrage**" in line
    # Both slugs surface; reader can see the asymmetry at a glance.
    assert "anthropic/claude-sonnet-4.5" in line
    assert "openai/gpt-5.4-mini" in line
    assert "fraction of the per-query cost" in line


def test_legacy_artifact_without_scenario_renders_as_head_to_head():
    """Old run_artifact.json files don't have ``scenario`` — must still render."""

    extra = {"provider_model": "anthropic/claude-sonnet-4.5"}
    line = format_scenario_md(extra)
    assert "head-to-head" in line


def test_none_extra_does_not_crash():
    line = format_scenario_md(None)
    assert "head-to-head" in line
