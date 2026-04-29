"""Tests for the skills backends used by SurfSense's SkillsMiddleware."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.agents.new_chat.middleware.skills_backends import (
    SKILLS_BUILTIN_PREFIX,
    SKILLS_SPACE_PREFIX,
    BuiltinSkillsBackend,
    SearchSpaceSkillsBackend,
    build_skills_backend_factory,
    default_skills_sources,
)


@pytest.fixture
def skills_root(tmp_path: Path) -> Path:
    """Build a small synthetic skill-tree used by the tests."""
    root = tmp_path / "skills"
    (root / "alpha").mkdir(parents=True)
    (root / "alpha" / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: alpha skill\n---\n# Alpha\n"
    )
    (root / "beta").mkdir(parents=True)
    (root / "beta" / "SKILL.md").write_text(
        "---\nname: beta\ndescription: beta skill\n---\n# Beta\n"
    )
    (root / "_orphan_file.md").write_text("not a skill, just a stray file")
    return root


class TestBuiltinSkillsBackendListing:
    def test_lists_skill_directories_at_root(self, skills_root: Path) -> None:
        backend = BuiltinSkillsBackend(skills_root)
        infos = backend.ls_info("/")
        names = {info["path"] for info in infos}
        assert "/alpha" in names
        assert "/beta" in names
        assert "/_orphan_file.md" in names
        for info in infos:
            if info["path"] in {"/alpha", "/beta"}:
                assert info["is_dir"] is True

    def test_lists_skill_md_under_skill_directory(self, skills_root: Path) -> None:
        backend = BuiltinSkillsBackend(skills_root)
        infos = backend.ls_info("/alpha")
        paths = {info["path"] for info in infos}
        assert paths == {"/alpha/SKILL.md"}
        assert infos[0]["is_dir"] is False
        assert infos[0]["size"] > 0

    def test_returns_empty_for_missing_path(self, skills_root: Path) -> None:
        backend = BuiltinSkillsBackend(skills_root)
        assert backend.ls_info("/nonexistent") == []

    def test_returns_empty_when_root_missing(self, tmp_path: Path) -> None:
        backend = BuiltinSkillsBackend(tmp_path / "definitely-missing")
        assert backend.ls_info("/") == []
        assert backend.download_files(["/x/SKILL.md"])[0].error == "file_not_found"

    def test_refuses_path_traversal(self, skills_root: Path) -> None:
        backend = BuiltinSkillsBackend(skills_root)
        assert backend.ls_info("/../../../etc") == []
        responses = backend.download_files(["/../../../etc/passwd"])
        assert responses[0].error == "invalid_path"


class TestBuiltinSkillsBackendDownload:
    def test_downloads_skill_md_content(self, skills_root: Path) -> None:
        backend = BuiltinSkillsBackend(skills_root)
        responses = backend.download_files(["/alpha/SKILL.md", "/beta/SKILL.md"])
        assert len(responses) == 2
        assert responses[0].path == "/alpha/SKILL.md"
        assert responses[0].content is not None
        assert b"name: alpha" in responses[0].content
        assert responses[1].error is None

    def test_marks_directory_as_is_directory_error(self, skills_root: Path) -> None:
        backend = BuiltinSkillsBackend(skills_root)
        responses = backend.download_files(["/alpha"])
        assert responses[0].error == "is_directory"

    def test_marks_missing_file_as_file_not_found(self, skills_root: Path) -> None:
        backend = BuiltinSkillsBackend(skills_root)
        responses = backend.download_files(["/alpha/missing.md"])
        assert responses[0].error == "file_not_found"
        assert responses[0].content is None

    def test_response_path_matches_input_for_correlation(
        self, skills_root: Path
    ) -> None:
        backend = BuiltinSkillsBackend(skills_root)
        inputs = ["/alpha/SKILL.md", "/missing.md", "/beta/SKILL.md"]
        responses = backend.download_files(inputs)
        assert [r.path for r in responses] == inputs


class TestBuiltinSkillsBackendIntegration:
    """Mirror the call sequence the SkillsMiddleware actually uses."""

    def test_skills_middleware_call_pattern(self, skills_root: Path) -> None:
        backend = BuiltinSkillsBackend(skills_root)

        infos = asyncio.run(backend.als_info("/"))
        skill_dirs = [i["path"] for i in infos if i.get("is_dir")]
        assert sorted(skill_dirs) == ["/alpha", "/beta"]

        skill_md_paths = [f"{p}/SKILL.md" for p in skill_dirs]
        responses = asyncio.run(backend.adownload_files(skill_md_paths))
        assert all(r.error is None for r in responses)
        assert all(r.content is not None for r in responses)


class TestBundledSkills:
    def test_default_root_resolves_to_repo_skills_dir(self) -> None:
        backend = BuiltinSkillsBackend()
        assert backend.root.name == "builtin"
        assert backend.root.parent.name == "skills"

    def test_bundled_starter_skills_are_present(self) -> None:
        backend = BuiltinSkillsBackend()
        infos = backend.ls_info("/")
        names = {info["path"].lstrip("/") for info in infos if info.get("is_dir")}
        # Five starter skills required by the Tier 4 plan.
        for required in (
            "kb-research",
            "report-writing",
            "meeting-prep",
            "slack-summary",
            "email-drafting",
        ):
            assert required in names, f"missing starter skill: {required}"

    def test_each_starter_skill_has_valid_skill_md(self) -> None:
        backend = BuiltinSkillsBackend()
        infos = backend.ls_info("/")
        skill_dirs = [info["path"] for info in infos if info.get("is_dir")]
        for skill_dir in skill_dirs:
            md_path = f"{skill_dir}/SKILL.md"
            response = backend.download_files([md_path])[0]
            assert response.error is None, f"missing SKILL.md in {skill_dir}"
            content = response.content.decode("utf-8").replace("\r\n", "\n")
            assert content.startswith("---\n"), f"missing frontmatter in {skill_dir}"
            assert "\nname:" in content
            assert "\ndescription:" in content


class _FakeKBBackend:
    """Stand-in for :class:`KBPostgresBackend` with the two methods we need."""

    def __init__(self, listing: list[dict], file_contents: dict[str, bytes]) -> None:
        self._listing = listing
        self._file_contents = file_contents
        self.last_ls_path: str | None = None
        self.last_download_paths: list[str] | None = None

    async def als_info(self, path: str):
        self.last_ls_path = path
        return self._listing

    async def adownload_files(self, paths):
        from deepagents.backends.protocol import FileDownloadResponse

        self.last_download_paths = list(paths)
        out: list[FileDownloadResponse] = []
        for p in paths:
            content = self._file_contents.get(p)
            if content is None:
                out.append(FileDownloadResponse(path=p, error="file_not_found"))
            else:
                out.append(FileDownloadResponse(path=p, content=content))
        return out


class TestSearchSpaceSkillsBackend:
    def test_remaps_paths_when_listing(self) -> None:
        listing = [
            {"path": "/documents/_skills/policy", "is_dir": True},
            {"path": "/documents/_skills/policy/SKILL.md", "is_dir": False},
            {"path": "/documents/other-folder/x.md", "is_dir": False},
        ]
        kb = _FakeKBBackend(listing=listing, file_contents={})
        backend = SearchSpaceSkillsBackend(kb)
        infos = asyncio.run(backend.als_info("/"))
        assert kb.last_ls_path == "/documents/_skills"
        paths = [info["path"] for info in infos]
        assert "/policy" in paths
        assert "/policy/SKILL.md" in paths
        # Unrelated KB documents must NOT leak into the skills namespace.
        assert all(not p.startswith("/documents") for p in paths)

    def test_remaps_paths_when_downloading(self) -> None:
        kb = _FakeKBBackend(
            listing=[],
            file_contents={
                "/documents/_skills/policy/SKILL.md": b"---\nname: policy\n---\n",
            },
        )
        backend = SearchSpaceSkillsBackend(kb)
        responses = asyncio.run(backend.adownload_files(["/policy/SKILL.md"]))
        assert kb.last_download_paths == ["/documents/_skills/policy/SKILL.md"]
        assert responses[0].path == "/policy/SKILL.md"
        assert responses[0].error is None
        assert responses[0].content is not None

    def test_sync_methods_raise_not_implemented(self) -> None:
        backend = SearchSpaceSkillsBackend(_FakeKBBackend([], {}))
        with pytest.raises(NotImplementedError):
            backend.ls_info("/")
        with pytest.raises(NotImplementedError):
            backend.download_files(["/x"])

    def test_custom_kb_root_is_honored(self) -> None:
        kb = _FakeKBBackend(
            listing=[
                {"path": "/skills_admin/x", "is_dir": True},
            ],
            file_contents={},
        )
        backend = SearchSpaceSkillsBackend(kb, kb_root="/skills_admin")
        infos = asyncio.run(backend.als_info("/"))
        assert kb.last_ls_path == "/skills_admin"
        assert infos[0]["path"] == "/x"


class TestBackendFactory:
    def test_builtin_only_factory_returns_composite(self) -> None:
        factory = build_skills_backend_factory()
        backend = factory(runtime=None)  # type: ignore[arg-type]
        from deepagents.backends.composite import CompositeBackend

        assert isinstance(backend, CompositeBackend)
        assert SKILLS_BUILTIN_PREFIX in backend.routes
        assert SKILLS_SPACE_PREFIX not in backend.routes

    def test_default_skills_sources_lists_builtin_then_space(self) -> None:
        sources = default_skills_sources()
        assert sources == [SKILLS_BUILTIN_PREFIX, SKILLS_SPACE_PREFIX]
