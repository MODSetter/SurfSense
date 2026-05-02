"""Unit tests for the SurfSense filesystem middleware new behaviors.

Covers:
* cloud cwd defaults to ``/documents`` and relative paths resolve under it
* cloud writes outside ``/documents/`` are rejected unless basename starts
  with ``temp_``
* cloud writes/edits to the anonymous document are rejected (read-only)
* helper methods on the middleware (``_resolve_relative``,
  ``_check_cloud_write_namespace``, ``_default_cwd``)

These tests use ``__new__`` to bypass the heavy ``__init__`` and exercise
the helper methods directly so the test surface stays narrow and fast.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.middleware.filesystem import (
    SurfSenseFilesystemMiddleware,
    _build_filesystem_system_prompt,
    _build_tool_descriptions,
)

pytestmark = pytest.mark.unit


def _make_middleware(mode: FilesystemMode = FilesystemMode.CLOUD):
    middleware = SurfSenseFilesystemMiddleware.__new__(SurfSenseFilesystemMiddleware)
    middleware._filesystem_mode = mode
    return middleware


def _runtime(state: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(state=state or {})


class TestCloudCwdDefaults:
    def test_default_cwd_in_cloud_is_documents_root(self):
        m = _make_middleware()
        assert m._default_cwd() == "/documents"

    def test_default_cwd_in_desktop_is_root(self):
        m = _make_middleware(FilesystemMode.DESKTOP_LOCAL_FOLDER)
        assert m._default_cwd() == "/"

    def test_current_cwd_uses_state_when_set(self):
        m = _make_middleware()
        runtime = _runtime({"cwd": "/documents/notes"})
        assert m._current_cwd(runtime) == "/documents/notes"

    def test_current_cwd_falls_back_to_default(self):
        m = _make_middleware()
        runtime = _runtime({})
        assert m._current_cwd(runtime) == "/documents"

    def test_current_cwd_ignores_invalid(self):
        m = _make_middleware()
        runtime = _runtime({"cwd": "not-absolute"})
        assert m._current_cwd(runtime) == "/documents"


class TestRelativePathResolution:
    def test_relative_path_resolves_against_cwd(self):
        m = _make_middleware()
        runtime = _runtime({"cwd": "/documents/projects"})
        assert (
            m._resolve_relative("notes.md", runtime) == "/documents/projects/notes.md"
        )

    def test_relative_path_with_dotdot(self):
        m = _make_middleware()
        runtime = _runtime({"cwd": "/documents/a/b"})
        assert m._resolve_relative("../c.md", runtime) == "/documents/a/c.md"

    def test_absolute_path_is_kept(self):
        m = _make_middleware()
        runtime = _runtime({"cwd": "/documents"})
        assert m._resolve_relative("/other/x.md", runtime) == "/other/x.md"

    def test_empty_path_returns_cwd(self):
        m = _make_middleware()
        runtime = _runtime({"cwd": "/documents/projects"})
        assert m._resolve_relative("", runtime) == "/documents/projects"


class TestCloudWriteNamespacePolicy:
    def test_documents_path_allowed(self):
        m = _make_middleware()
        runtime = _runtime()
        assert m._check_cloud_write_namespace("/documents/foo.md", runtime) is None

    def test_documents_root_allowed(self):
        m = _make_middleware()
        runtime = _runtime()
        assert m._check_cloud_write_namespace("/documents", runtime) is None

    def test_temp_basename_anywhere_allowed(self):
        m = _make_middleware()
        runtime = _runtime()
        assert m._check_cloud_write_namespace("/temp_scratch.md", runtime) is None
        assert m._check_cloud_write_namespace("/foo/temp_x.md", runtime) is None
        assert m._check_cloud_write_namespace("/documents/temp_x.md", runtime) is None

    def test_other_paths_rejected(self):
        m = _make_middleware()
        runtime = _runtime()
        err = m._check_cloud_write_namespace("/foo/bar.md", runtime)
        assert err is not None
        assert "must target /documents" in err

    def test_anon_doc_path_is_read_only(self):
        m = _make_middleware()
        runtime = _runtime(
            {
                "kb_anon_doc": {
                    "path": "/documents/uploaded.xml",
                    "title": "uploaded",
                    "content": "",
                    "chunks": [],
                }
            }
        )
        err = m._check_cloud_write_namespace("/documents/uploaded.xml", runtime)
        assert err is not None
        assert "read-only" in err

    def test_desktop_mode_skips_namespace_policy(self):
        m = _make_middleware(FilesystemMode.DESKTOP_LOCAL_FOLDER)
        runtime = _runtime()
        assert m._check_cloud_write_namespace("/random/path.md", runtime) is None


class TestModeSpecificPrompts:
    """The prompt and tool descriptions must only describe the active mode.

    Cross-mode noise wastes tokens and confuses the model with rules it
    cannot use this session.
    """

    def test_cloud_prompt_omits_desktop_section(self):
        prompt = _build_filesystem_system_prompt(
            FilesystemMode.CLOUD, sandbox_available=False
        )
        assert "Local Folder Mode" not in prompt
        assert "mount-prefixed" not in prompt
        assert "Persistence Rules" in prompt
        assert "/documents" in prompt
        assert "temp_" in prompt

    def test_desktop_prompt_omits_cloud_persistence_rules(self):
        prompt = _build_filesystem_system_prompt(
            FilesystemMode.DESKTOP_LOCAL_FOLDER, sandbox_available=False
        )
        assert "Persistence Rules" not in prompt
        assert "Workspace Tree" not in prompt
        assert "<priority_documents>" not in prompt
        assert "Local Folder Mode" in prompt
        assert "mount-prefixed" in prompt

    def test_cloud_tool_descs_omit_desktop_phrases(self):
        descs = _build_tool_descriptions(FilesystemMode.CLOUD)
        for name in (
            "write_file",
            "edit_file",
            "move_file",
            "mkdir",
            "rm",
            "rmdir",
            "list_tree",
            "grep",
        ):
            text = descs[name]
            assert "Desktop" not in text, f"{name} leaks desktop hints"
            assert "Cloud mode:" not in text, f"{name} qualifies a cloud-only desc"

    def test_desktop_tool_descs_omit_cloud_phrases(self):
        descs = _build_tool_descriptions(FilesystemMode.DESKTOP_LOCAL_FOLDER)
        for name in (
            "write_file",
            "edit_file",
            "move_file",
            "mkdir",
            "rm",
            "rmdir",
            "list_tree",
            "grep",
        ):
            text = descs[name]
            assert "Cloud" not in text, f"{name} leaks cloud hints"
            assert "/documents/" not in text, f"{name} mentions cloud namespace"
            assert "temp_" not in text, f"{name} mentions cloud temp_ semantics"

    def test_cloud_descs_include_rm_and_rmdir(self):
        descs = _build_tool_descriptions(FilesystemMode.CLOUD)
        assert "rm" in descs and "rmdir" in descs
        assert "Deletes a single file" in descs["rm"]
        assert "Deletes an empty directory" in descs["rmdir"]
        assert "rmdir" in descs["rmdir"] and "POSIX" in descs["rmdir"]

    def test_desktop_descs_warn_about_irreversibility(self):
        descs = _build_tool_descriptions(FilesystemMode.DESKTOP_LOCAL_FOLDER)
        assert "NOT reversible" in descs["rm"]
        assert "NOT reversible" in descs["rmdir"]

    def test_sandbox_addendum_appended_when_available(self):
        prompt = _build_filesystem_system_prompt(
            FilesystemMode.CLOUD, sandbox_available=True
        )
        assert "execute_code" in prompt
        assert "Code Execution" in prompt

    def test_sandbox_addendum_absent_when_unavailable(self):
        prompt = _build_filesystem_system_prompt(
            FilesystemMode.CLOUD, sandbox_available=False
        )
        assert "execute_code" not in prompt
