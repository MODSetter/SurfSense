"""Tests for the specialized subagents (explore / report_writer / connector_negotiator)."""

from __future__ import annotations

from langchain_core.tools import tool

from app.agents.new_chat.middleware.permission import PermissionMiddleware
from app.agents.new_chat.subagents import (
    build_connector_negotiator_subagent,
    build_explore_subagent,
    build_report_writer_subagent,
    build_specialized_subagents,
)
from app.agents.new_chat.subagents.config import (
    EXPLORE_READ_TOOLS,
    REPORT_WRITER_TOOLS,
    WRITE_TOOL_DENY_PATTERNS,
)

# ---------------------------------------------------------------------------
# Fake tools used to verify filtering & permission behavior
# ---------------------------------------------------------------------------


@tool
def search_surfsense_docs(query: str) -> str:
    """Search the user's KB."""
    return ""


@tool
def web_search(query: str) -> str:
    """Search the public web."""
    return ""


@tool
def scrape_webpage(url: str) -> str:
    """Scrape a single webpage."""
    return ""


@tool
def read_file(path: str) -> str:
    """Read a file."""
    return ""


@tool
def ls_tree(path: str) -> str:
    """List a tree."""
    return ""


@tool
def grep(pattern: str) -> str:
    """Grep."""
    return ""


@tool
def update_memory(content: str) -> str:
    """Update the user's memory."""
    return ""


@tool
def edit_file(path: str, old: str, new: str) -> str:
    """Edit a file."""
    return ""


@tool
def linear_create_issue(title: str) -> str:
    """Create a Linear issue."""
    return ""


@tool
def slack_send_message(channel: str, text: str) -> str:
    """Send a Slack message."""
    return ""


@tool
def get_connected_accounts() -> str:
    """List connected accounts."""
    return ""


@tool
def generate_report(topic: str) -> str:
    """Generate a report artifact."""
    return ""


ALL_TOOLS = [
    search_surfsense_docs,
    web_search,
    scrape_webpage,
    read_file,
    ls_tree,
    grep,
    update_memory,
    edit_file,
    linear_create_issue,
    slack_send_message,
    get_connected_accounts,
    generate_report,
]


class TestExploreSubagent:
    def test_only_read_tools_are_exposed(self) -> None:
        spec = build_explore_subagent(tools=ALL_TOOLS)
        names = {t.name for t in spec["tools"]}  # type: ignore[index]
        assert names == EXPLORE_READ_TOOLS & {t.name for t in ALL_TOOLS}
        assert "update_memory" not in names
        assert "linear_create_issue" not in names
        assert "edit_file" not in names

    def test_includes_permission_middleware_with_deny_rules(self) -> None:
        spec = build_explore_subagent(tools=ALL_TOOLS)
        permission_mws = [
            m
            for m in spec["middleware"]
            if isinstance(m, PermissionMiddleware)  # type: ignore[index]
        ]
        assert len(permission_mws) == 1
        ruleset = permission_mws[0]._static_rulesets[0]
        assert ruleset.origin == "subagent_explore"
        deny_patterns = {r.permission for r in ruleset.rules if r.action == "deny"}
        assert "update_memory" in deny_patterns
        assert "edit_file" in deny_patterns
        assert "*create*" in deny_patterns
        assert "*send*" in deny_patterns

    def test_skills_inherits_default_sources(self) -> None:
        spec = build_explore_subagent(tools=ALL_TOOLS)
        assert spec["skills"] == ["/skills/builtin/", "/skills/space/"]  # type: ignore[index]

    def test_name_and_description_match_contract(self) -> None:
        spec = build_explore_subagent(tools=ALL_TOOLS)
        assert spec["name"] == "explore"
        assert "read-only" in spec["description"].lower()

    def test_includes_dedup_and_patch_middleware(self) -> None:
        from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware

        from app.agents.new_chat.middleware import DedupHITLToolCallsMiddleware

        spec = build_explore_subagent(tools=ALL_TOOLS)
        types = {type(m) for m in spec["middleware"]}  # type: ignore[index]
        assert PatchToolCallsMiddleware in types
        assert DedupHITLToolCallsMiddleware in types


class TestReportWriterSubagent:
    def test_exposes_only_report_writing_tools(self) -> None:
        spec = build_report_writer_subagent(tools=ALL_TOOLS)
        names = {t.name for t in spec["tools"]}  # type: ignore[index]
        assert names == REPORT_WRITER_TOOLS & {t.name for t in ALL_TOOLS}
        assert "generate_report" in names
        assert "search_surfsense_docs" in names

    def test_deny_rules_block_writes_but_allow_generate_report(self) -> None:
        spec = build_report_writer_subagent(tools=ALL_TOOLS)
        permission_mws = [
            m
            for m in spec["middleware"]
            if isinstance(m, PermissionMiddleware)  # type: ignore[index]
        ]
        ruleset = permission_mws[0]._static_rulesets[0]
        deny_patterns = {r.permission for r in ruleset.rules if r.action == "deny"}
        assert "update_memory" in deny_patterns
        # generate_report MUST not be denied — it's the whole point of the subagent.
        assert "generate_report" not in deny_patterns
        # No deny pattern should match `generate_report` either.
        assert all(
            not _wildcard_matches(pattern, "generate_report")
            for pattern in deny_patterns
        )


class TestConnectorNegotiatorSubagent:
    def test_inherits_all_parent_tools(self) -> None:
        spec = build_connector_negotiator_subagent(tools=ALL_TOOLS)
        names = {t.name for t in spec["tools"]}  # type: ignore[index]
        # Every parent tool is inherited; the deny ruleset enforces behavior
        # at execution time instead of trimming the tool list.
        assert names == {t.name for t in ALL_TOOLS}

    def test_get_connected_accounts_is_present(self) -> None:
        spec = build_connector_negotiator_subagent(tools=ALL_TOOLS)
        names = {t.name for t in spec["tools"]}  # type: ignore[index]
        assert "get_connected_accounts" in names

    def test_deny_ruleset_blocks_mutating_connector_tools(self) -> None:
        spec = build_connector_negotiator_subagent(tools=ALL_TOOLS)
        permission_mws = [
            m
            for m in spec["middleware"]
            if isinstance(m, PermissionMiddleware)  # type: ignore[index]
        ]
        ruleset = permission_mws[0]._static_rulesets[0]
        deny_patterns = {r.permission for r in ruleset.rules if r.action == "deny"}
        # `linear_create_issue` matches the `*_create` deny pattern.
        assert any(_wildcard_matches(p, "linear_create_issue") for p in deny_patterns)
        assert any(_wildcard_matches(p, "slack_send_message") for p in deny_patterns)


class TestBuildSpecializedSubagents:
    def test_returns_five_specs(self) -> None:
        specs = build_specialized_subagents(tools=ALL_TOOLS)
        names = [s["name"] for s in specs]  # type: ignore[index]
        assert names == [
            "explore",
            "report_writer",
            "linear_specialist",
            "slack_specialist",
            "connector_negotiator",
        ]

    def test_all_specs_have_unique_names(self) -> None:
        specs = build_specialized_subagents(tools=ALL_TOOLS)
        names = [s["name"] for s in specs]  # type: ignore[index]
        assert len(set(names)) == len(names)

    def test_extra_middleware_is_prepended_to_each_spec(self) -> None:
        """Sentinel middleware passed via ``extra_middleware`` must appear
        in each subagent's ``middleware`` list, before the local rules.

        This guards against the regression where specialized subagents
        promised filesystem tools (``read_file``, ``ls``, ``grep``) in
        their system prompts but had no filesystem middleware mounted.
        """

        class _Sentinel:
            pass

        sentinel = _Sentinel()
        specs = build_specialized_subagents(
            tools=ALL_TOOLS, extra_middleware=[sentinel]
        )
        for spec in specs:
            mws = spec["middleware"]  # type: ignore[index]
            assert sentinel in mws
            # The sentinel must appear *before* the permission middleware
            # (subagent-local rules), preserving the documented composition
            # order: extra → custom → patch → dedup.
            sentinel_idx = mws.index(sentinel)
            perm_idx = next(
                (i for i, m in enumerate(mws) if isinstance(m, PermissionMiddleware)),
                None,
            )
            assert perm_idx is not None
            assert sentinel_idx < perm_idx


class TestFilterToolsWarningSuppression:
    """Names provided by middleware (read_file, ls, grep, …) must not
    trigger the spurious "missing" warning in :func:`_filter_tools`."""

    def test_middleware_provided_names_are_silent(self, caplog) -> None:
        import logging

        from app.agents.new_chat.subagents.config import _filter_tools

        with caplog.at_level(
            logging.INFO, logger="app.agents.new_chat.subagents.config"
        ):
            # Allowed set asks for two registry tools (one present, one
            # not) plus a bunch of middleware-provided names.
            _filter_tools(
                [search_surfsense_docs],
                allowed_names={
                    "search_surfsense_docs",
                    "scrape_webpage",  # legitimately missing → should warn
                    "read_file",  # mw-provided → suppressed
                    "ls",
                    "grep",
                    "glob",
                    "write_todos",
                },
            )

        warnings = [r.message for r in caplog.records if r.levelno >= logging.INFO]
        # Exactly one warning, and it should mention scrape_webpage but not
        # any middleware-provided name. Inspect the rendered "missing"
        # list (between the brackets) so we don't false-match substrings
        # like ``ls`` inside ``available``.
        assert len(warnings) == 1, warnings
        msg = warnings[0]
        assert "scrape_webpage" in msg
        bracket_section = msg.split("missing: ", 1)[1]
        for noisy in ("read_file", "ls", "grep", "glob", "write_todos"):
            assert f"'{noisy}'" not in bracket_section, msg


class TestDenyPatternsCoverage:
    def test_deny_patterns_cover_canonical_write_tools(self) -> None:
        canonical_writes = [
            "update_memory",
            "edit_file",
            "write_file",
            "move_file",
            "mkdir",
            "linear_create_issue",
            "linear_update_issue",
            "linear_delete_issue",
            "slack_send_message",
            "create_index",
            "update_account",
            "delete_record",
            "send_email",
        ]
        for tool_name in canonical_writes:
            assert any(
                _wildcard_matches(pattern, tool_name)
                for pattern in WRITE_TOOL_DENY_PATTERNS
            ), f"no deny pattern matches {tool_name!r}"

    def test_deny_patterns_do_not_match_safe_read_tools(self) -> None:
        canonical_reads = [
            "search_surfsense_docs",
            "read_file",
            "ls_tree",
            "grep",
            "web_search",
            "scrape_webpage",
            "get_connected_accounts",
            "generate_report",
        ]
        for tool_name in canonical_reads:
            assert not any(
                _wildcard_matches(pattern, tool_name)
                for pattern in WRITE_TOOL_DENY_PATTERNS
            ), f"deny pattern incorrectly matches read tool {tool_name!r}"


def _wildcard_matches(pattern: str, value: str) -> bool:
    """Helper using the same matcher the rule evaluator does."""
    from app.agents.new_chat.permissions import wildcard_match

    return wildcard_match(value, pattern)
