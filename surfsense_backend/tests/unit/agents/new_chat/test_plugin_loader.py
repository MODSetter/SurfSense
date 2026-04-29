"""Unit tests for the SurfSense plugin entry-point loader."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from langchain.agents.middleware import AgentMiddleware

from app.agents.new_chat.plugin_loader import (
    PLUGIN_ENTRY_POINT_GROUP,
    PluginContext,
    load_allowed_plugin_names_from_env,
    load_plugin_middlewares,
)
from app.agents.new_chat.plugins.year_substituter import (
    _YearSubstituterMiddleware,
    make_middleware as year_substituter_factory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _DummyMiddleware(AgentMiddleware):
    """Trivial middleware used as the success-path return value."""

    tools = ()


def _ctx() -> PluginContext:
    return PluginContext.build(
        search_space_id=1,
        user_id="u",
        thread_visibility="PRIVATE",  # type: ignore[arg-type]
        llm=MagicMock(),
    )


class _FakeEntryPoint:
    """Stand-in for ``importlib.metadata.EntryPoint``."""

    def __init__(self, name: str, factory) -> None:
        self.name = name
        self._factory = factory

    def load(self):
        return self._factory


# ---------------------------------------------------------------------------
# Loader behaviour
# ---------------------------------------------------------------------------


class TestPluginLoaderBasics:
    def test_returns_empty_when_allowlist_is_empty(self) -> None:
        assert load_plugin_middlewares(_ctx(), allowed_plugin_names=[]) == []

    def test_skips_non_allowlisted_plugin(self) -> None:
        called = []

        def factory(_):  # would be an obvious bug if called
            called.append(True)
            return _DummyMiddleware()

        ep = _FakeEntryPoint("dangerous_plugin", factory)
        with patch(
            "app.agents.new_chat.plugin_loader.entry_points",
            return_value=[ep],
        ):
            result = load_plugin_middlewares(
                _ctx(), allowed_plugin_names=["allowed_only"]
            )
        assert result == []
        assert not called

    def test_loads_allowlisted_plugin(self) -> None:
        ep = _FakeEntryPoint("year_substituter", year_substituter_factory)
        with patch(
            "app.agents.new_chat.plugin_loader.entry_points",
            return_value=[ep],
        ):
            result = load_plugin_middlewares(
                _ctx(), allowed_plugin_names={"year_substituter"}
            )
        assert len(result) == 1
        assert isinstance(result[0], _YearSubstituterMiddleware)


class TestPluginLoaderIsolation:
    def test_factory_exception_is_isolated(self) -> None:
        def crashing_factory(_):
            raise RuntimeError("boom")

        ep = _FakeEntryPoint("buggy", crashing_factory)
        with patch(
            "app.agents.new_chat.plugin_loader.entry_points",
            return_value=[ep],
        ):
            result = load_plugin_middlewares(_ctx(), allowed_plugin_names={"buggy"})
        assert result == []  # construction continued without the plugin

    def test_non_middleware_return_is_rejected(self) -> None:
        def bad_factory(_):
            return "not a middleware"

        ep = _FakeEntryPoint("liar", bad_factory)
        with patch(
            "app.agents.new_chat.plugin_loader.entry_points",
            return_value=[ep],
        ):
            result = load_plugin_middlewares(_ctx(), allowed_plugin_names={"liar"})
        assert result == []

    def test_load_phase_exception_is_isolated(self) -> None:
        class _BrokenEP:
            name = "broken"

            def load(self):
                raise ImportError("cannot import")

        with patch(
            "app.agents.new_chat.plugin_loader.entry_points",
            return_value=[_BrokenEP()],
        ):
            result = load_plugin_middlewares(_ctx(), allowed_plugin_names={"broken"})
        assert result == []

    def test_one_failure_does_not_block_others(self) -> None:
        """Two plugins; one crashes during factory; the other still loads."""

        def crashing_factory(_):
            raise RuntimeError("boom")

        eps = [
            _FakeEntryPoint("crashing", crashing_factory),
            _FakeEntryPoint("ok", year_substituter_factory),
        ]
        with patch("app.agents.new_chat.plugin_loader.entry_points", return_value=eps):
            result = load_plugin_middlewares(
                _ctx(), allowed_plugin_names={"crashing", "ok"}
            )
        assert len(result) == 1
        assert isinstance(result[0], _YearSubstituterMiddleware)


class TestAllowlistEnv:
    def test_empty_env_returns_empty_set(self, monkeypatch) -> None:
        monkeypatch.delenv("SURFSENSE_ALLOWED_PLUGINS", raising=False)
        assert load_allowed_plugin_names_from_env() == set()

    def test_parses_comma_separated_value(self, monkeypatch) -> None:
        monkeypatch.setenv("SURFSENSE_ALLOWED_PLUGINS", " year_substituter , noisy , ")
        assert load_allowed_plugin_names_from_env() == {
            "year_substituter",
            "noisy",
        }


class TestPluginContext:
    def test_build_includes_required_fields(self) -> None:
        llm = MagicMock()
        ctx = PluginContext.build(
            search_space_id=42,
            user_id="user-1",
            thread_visibility="PRIVATE",  # type: ignore[arg-type]
            llm=llm,
        )
        assert ctx["search_space_id"] == 42
        assert ctx["user_id"] == "user-1"
        assert ctx["llm"] is llm

    def test_does_not_carry_secrets_or_db_session(self) -> None:
        ctx = _ctx()
        # If a future change tries to add these keys, this test will fail loudly.
        for forbidden in ("api_key", "secret", "db_session", "session"):
            assert forbidden not in ctx


class TestEntryPointGroup:
    def test_group_name_matches_pyproject_convention(self) -> None:
        # Plugins register under `surfsense.plugins`; this is part of our
        # public contract for plugin authors.
        assert PLUGIN_ENTRY_POINT_GROUP == "surfsense.plugins"
