"""Mode-specific system-prompt assembly tests for the LIVE filesystem middleware.

Ported from ``TestModeSpecificPrompts`` in the former
``tests/unit/middleware/test_filesystem_middleware.py`` (which exercised the
dead twin ``app.agents.shared.middleware.filesystem._build_filesystem_system_prompt``).

These drive the production ``build_system_prompt`` so the prompt the model
actually receives stays mode-scoped: cloud rules don't leak into desktop
sessions and vice-versa, and the sandbox section appears only when available.

The per-tool *description* assertions from the old suite are intentionally NOT
ported: they assert exact prompt copy (tightly coupled to the old wording) and
guard prompt token hygiene rather than the code-movement refactor this suite
protects.
"""

from __future__ import annotations

import pytest

from app.agents.multi_agent_chat.shared.middleware.filesystem.system_prompt import (
    build_system_prompt,
)
from app.agents.shared.filesystem_selection import FilesystemMode

pytestmark = pytest.mark.unit


class TestModeSpecificPrompts:
    def test_cloud_prompt_omits_desktop_section(self):
        prompt = build_system_prompt(FilesystemMode.CLOUD, sandbox_available=False)
        assert "Local Folder Mode" not in prompt
        assert "mount-prefixed" not in prompt
        assert "Persistence Rules" in prompt
        assert "/documents" in prompt
        assert "temp_" in prompt

    def test_desktop_prompt_omits_cloud_persistence_rules(self):
        prompt = build_system_prompt(
            FilesystemMode.DESKTOP_LOCAL_FOLDER, sandbox_available=False
        )
        assert "Persistence Rules" not in prompt
        assert "Workspace Tree" not in prompt
        assert "Local Folder Mode" in prompt
        assert "mount-prefixed" in prompt

    def test_sandbox_addendum_appended_when_available(self):
        prompt = build_system_prompt(FilesystemMode.CLOUD, sandbox_available=True)
        assert "execute_code" in prompt
        assert "Code Execution" in prompt

    def test_sandbox_addendum_absent_when_unavailable(self):
        prompt = build_system_prompt(FilesystemMode.CLOUD, sandbox_available=False)
        assert "execute_code" not in prompt
