"""Tests for the prompt fragment composer (Tier 3a)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.agents.new_chat.prompts.composer import (
    ALL_TOOL_NAMES_ORDERED,
    compose_system_prompt,
    detect_provider_variant,
)
from app.db import ChatVisibility

pytestmark = pytest.mark.unit


@pytest.fixture
def fixed_today() -> datetime:
    return datetime(2025, 6, 1, 12, 0, tzinfo=UTC)


class TestProviderVariantDetection:
    @pytest.mark.parametrize(
        "model_name,expected",
        [
            ("openai:gpt-4o-mini", "openai_classic"),
            ("openai:gpt-4-turbo", "openai_classic"),
            ("openai:gpt-5", "openai_reasoning"),
            ("openai:gpt-5-codex", "openai_reasoning"),
            ("openai:o1-preview", "openai_reasoning"),
            ("openai:o3-mini", "openai_reasoning"),
            ("anthropic:claude-3-5-sonnet", "anthropic"),
            ("anthropic/claude-opus-4", "anthropic"),
            ("google:gemini-2.0-flash", "google"),
            ("vertex:gemini-1.5-pro", "google"),
            ("groq:mixtral-8x7b", "default"),
            (None, "default"),
            ("", "default"),
        ],
    )
    def test_detection(self, model_name: str | None, expected: str) -> None:
        assert detect_provider_variant(model_name) == expected


class TestCompose:
    def test_default_prompt_has_required_blocks(self, fixed_today: datetime) -> None:
        prompt = compose_system_prompt(today=fixed_today)
        # System instruction wrapper
        assert "<system_instruction>" in prompt
        assert "</system_instruction>" in prompt
        # Date interpolated
        assert "2025-06-01" in prompt
        # Core policy blocks present
        assert "<knowledge_base_only_policy>" in prompt
        assert "<tool_routing>" in prompt
        assert "<parameter_resolution>" in prompt
        assert "<memory_protocol>" in prompt
        # Tools
        assert "<tools>" in prompt
        assert "</tools>" in prompt
        # Citations on by default
        assert "<citation_instructions>" in prompt
        assert "[citation:chunk_id]" in prompt

    def test_team_visibility_uses_team_variants(
        self, fixed_today: datetime
    ) -> None:
        prompt = compose_system_prompt(
            today=fixed_today,
            thread_visibility=ChatVisibility.SEARCH_SPACE,
        )
        # Team-specific phrasing in the agent block
        assert "team space" in prompt
        # Memory protocol mentions team
        assert "team" in prompt
        # Should NOT mention the user-only memory phrasing
        assert "personal knowledge base" not in prompt

    def test_private_visibility_uses_private_variants(
        self, fixed_today: datetime
    ) -> None:
        prompt = compose_system_prompt(
            today=fixed_today,
            thread_visibility=ChatVisibility.PRIVATE,
        )
        assert "personal knowledge base" in prompt
        # Should NOT mention the team-specific phrasing about prefixed authors
        assert "[DisplayName of the author]" not in prompt

    def test_citations_disabled_swaps_block(self, fixed_today: datetime) -> None:
        prompt_on = compose_system_prompt(today=fixed_today, citations_enabled=True)
        prompt_off = compose_system_prompt(today=fixed_today, citations_enabled=False)
        assert "Citations are DISABLED" in prompt_off
        assert "Citations are DISABLED" not in prompt_on
        assert "[citation:chunk_id]" in prompt_on

    def test_enabled_tool_filter_only_includes_listed_tools(
        self, fixed_today: datetime
    ) -> None:
        prompt = compose_system_prompt(
            today=fixed_today,
            enabled_tool_names={"web_search", "scrape_webpage"},
        )
        assert "web_search:" in prompt or "- web_search:" in prompt
        assert "scrape_webpage:" in prompt or "- scrape_webpage:" in prompt
        # Excluded tools should NOT appear in tool listing
        assert "generate_podcast:" not in prompt
        assert "generate_image:" not in prompt

    def test_disabled_tool_note_is_appended(self, fixed_today: datetime) -> None:
        prompt = compose_system_prompt(
            today=fixed_today,
            enabled_tool_names={"web_search"},
            disabled_tool_names={"generate_image", "generate_podcast"},
        )
        assert "DISABLED TOOLS (by user):" in prompt
        assert "Generate Image" in prompt
        assert "Generate Podcast" in prompt

    def test_mcp_routing_block_emits_when_provided(
        self, fixed_today: datetime
    ) -> None:
        prompt = compose_system_prompt(
            today=fixed_today,
            mcp_connector_tools={"My GitLab": ["gitlab_search", "gitlab_create_mr"]},
        )
        assert "<mcp_tool_routing>" in prompt
        assert "My GitLab" in prompt
        assert "gitlab_search" in prompt

    def test_mcp_routing_block_absent_when_no_servers(
        self, fixed_today: datetime
    ) -> None:
        prompt = compose_system_prompt(today=fixed_today, mcp_connector_tools={})
        assert "<mcp_tool_routing>" not in prompt

    def test_provider_block_renders_when_anthropic(
        self, fixed_today: datetime
    ) -> None:
        prompt = compose_system_prompt(
            today=fixed_today, model_name="anthropic:claude-3-5-sonnet"
        )
        assert "<provider_hints>" in prompt
        assert "Anthropic" in prompt or "Claude" in prompt

    def test_provider_block_absent_for_default(self, fixed_today: datetime) -> None:
        prompt = compose_system_prompt(today=fixed_today, model_name="custom:foo")
        assert "<provider_hints>" not in prompt

    def test_custom_system_instructions_override_default(
        self, fixed_today: datetime
    ) -> None:
        custom = "You are a custom assistant. Today is {resolved_today}."
        prompt = compose_system_prompt(
            today=fixed_today, custom_system_instructions=custom
        )
        assert "You are a custom assistant. Today is 2025-06-01." in prompt
        # Default block should NOT be present
        assert "<knowledge_base_only_policy>" not in prompt

    def test_use_default_false_with_no_custom_yields_no_system_block(
        self, fixed_today: datetime
    ) -> None:
        prompt = compose_system_prompt(
            today=fixed_today,
            use_default_system_instructions=False,
        )
        # No system_instruction wrapper but tools/citations still emitted
        assert "<system_instruction>" not in prompt
        assert "<tools>" in prompt

    def test_all_known_tools_have_fragments(self) -> None:
        # Soft assertion: verify that every tool in the canonical order
        # produces non-empty content for at least one variant.
        for tool in ALL_TOOL_NAMES_ORDERED:
            prompt = compose_system_prompt(
                today=datetime(2025, 1, 1, tzinfo=UTC),
                enabled_tool_names={tool},
            )
            assert tool in prompt, f"tool {tool!r} missing from composed prompt"


class TestStableOrderingForCacheStability:
    """Regression guard: prompt cache hit-rate depends on byte-stable prefix."""

    def test_composition_is_deterministic_given_same_inputs(
        self, fixed_today: datetime
    ) -> None:
        a = compose_system_prompt(
            today=fixed_today,
            enabled_tool_names={"web_search", "scrape_webpage"},
            mcp_connector_tools={"X": ["x_a", "x_b"]},
        )
        b = compose_system_prompt(
            today=fixed_today,
            enabled_tool_names={"scrape_webpage", "web_search"},  # set order shouldn't matter
            mcp_connector_tools={"X": ["x_a", "x_b"]},
        )
        assert a == b
