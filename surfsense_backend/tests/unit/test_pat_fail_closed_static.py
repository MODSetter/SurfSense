"""Static guards for the fail-closed PAT authorization model."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BACKEND_ROOT / "app"

ALLOW_ANY_EXPECTED = {
    "app.py": "auth: AuthContext = Depends(allow_any_principal)",
    "routes/obsidian_plugin_routes.py": (
        "_auth: AuthContext = Depends(allow_any_principal)"
    ),
    "routes/workspaces_routes.py": ("auth: AuthContext = Depends(allow_any_principal)"),
}

CONNECTOR_LISTERS = [
    "routes/slack_add_connector_route.py",
    "routes/composio_routes.py",
    "routes/google_drive_add_connector_route.py",
    "routes/discord_add_connector_route.py",
    "routes/dropbox_add_connector_route.py",
    "routes/onedrive_add_connector_route.py",
]


def _python_files() -> list[Path]:
    return [path for path in APP_ROOT.rglob("*.py") if "__pycache__" not in path.parts]


def test_current_active_user_is_removed_from_app_tree() -> None:
    offenders = [
        str(path.relative_to(BACKEND_ROOT))
        for path in _python_files()
        if "current_active_user" in path.read_text()
    ]

    assert offenders == []


def test_allow_any_principal_is_only_used_by_bootstrap_allowlist() -> None:
    actual: dict[str, int] = {}
    for path in _python_files():
        text = path.read_text()
        count = text.count("Depends(allow_any_principal)")
        if count:
            actual[str(path.relative_to(APP_ROOT))] = count

    assert actual == dict.fromkeys(ALLOW_ANY_EXPECTED, 1)

    for rel_path, expected_snippet in ALLOW_ANY_EXPECTED.items():
        text = (APP_ROOT / rel_path).read_text()
        assert expected_snippet in text


def test_connector_listers_route_pat_through_workspace_gate() -> None:
    for rel_path in CONNECTOR_LISTERS:
        text = (APP_ROOT / rel_path).read_text()
        assert "auth: AuthContext = Depends(get_auth_context)" in text, rel_path
        assert (
            "await check_workspace_access(session, auth, connector.workspace_id)"
            in text
        ), rel_path


def test_identity_routes_are_session_only() -> None:
    session_only_files = [
        "routes/prompts_routes.py",
        "routes/memory_routes.py",
        "routes/model_list_routes.py",
        "routes/agent_flags_route.py",
        "routes/youtube_routes.py",
        "routes/incentive_tasks_routes.py",
        "notifications/api/api.py",
        "routes/chat_comments_routes.py",
        "routes/public_chat_routes.py",
    ]

    for rel_path in session_only_files:
        text = (APP_ROOT / rel_path).read_text()
        assert "require_session_context" in text, rel_path
        assert "Depends(get_auth_context)" not in text, rel_path


def test_model_connection_personal_writes_default_to_session_required() -> None:
    text = (APP_ROOT / "routes/model_connections_routes.py").read_text()

    assert "allow_spaceless_pat: bool = False" in text
    assert "auth.is_gated and not allow_spaceless_pat" in text
    assert "Managing personal model connections requires an interactive session" in text
