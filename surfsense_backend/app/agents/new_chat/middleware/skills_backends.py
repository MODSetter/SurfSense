"""Skills backends for SurfSense.

Implements two minimal :class:`deepagents.backends.protocol.BackendProtocol`
subclasses tailored for use with :class:`deepagents.middleware.skills.SkillsMiddleware`.

The middleware only needs four methods to load skills from a backend:

* ``ls_info`` / ``als_info`` — list directories under a source path.
* ``download_files`` / ``adownload_files`` — fetch ``SKILL.md`` bytes.

Other ``BackendProtocol`` methods (``read``/``write``/``edit``/``grep_raw`` …)
default to ``NotImplementedError`` from the base class. They are never reached
by the skills middleware because skill content is rendered into the system
prompt at agent build time, not edited at runtime.

Two backends are provided:

* :class:`BuiltinSkillsBackend` — disk-backed read of bundled skills from
  ``app/agents/new_chat/skills/builtin/``.
* :class:`SearchSpaceSkillsBackend` — a thin read-only wrapper over
  :class:`KBPostgresBackend` that filters notes under the privileged folder
  ``/documents/_skills/``.

Both backends are intentionally read-only: skill authoring happens out of band
(via filesystem or a search-space-admin route), so we never expose
``write`` / ``edit`` / ``upload_files``. The base class' ``NotImplementedError``
gives a clean failure mode if anything tries.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from deepagents.backends.composite import CompositeBackend
from deepagents.backends.protocol import (
    BackendProtocol,
    FileDownloadResponse,
    FileInfo,
)
from deepagents.backends.state import StateBackend

if TYPE_CHECKING:
    from langchain.tools import ToolRuntime

    from app.agents.new_chat.middleware.kb_postgres_backend import KBPostgresBackend

logger = logging.getLogger(__name__)


# Limit per Agent Skills spec; matches deepagents.middleware.skills.MAX_SKILL_FILE_SIZE.
_MAX_SKILL_FILE_SIZE = 10 * 1024 * 1024


def _default_builtin_root() -> Path:
    """Return the absolute path to the bundled builtin skills directory.

    Located at ``app/agents/new_chat/skills/builtin/`` relative to this module.
    """
    return (Path(__file__).resolve().parent.parent / "skills" / "builtin").resolve()


class BuiltinSkillsBackend(BackendProtocol):
    """Read-only disk-backed skills source.

    Maps a virtual ``/skills/builtin/`` namespace onto a directory on local disk,
    where each skill is its own subdirectory containing a ``SKILL.md`` file::

        <root>/<skill-name>/SKILL.md

    The middleware calls :meth:`als_info` with the source path and expects a
    ``list[FileInfo]`` whose ``is_dir=True`` entries are descended into. Then it
    calls :meth:`adownload_files` with the synthesized ``SKILL.md`` paths and
    parses YAML frontmatter from the returned ``content`` bytes.

    Mounting under :class:`~deepagents.backends.composite.CompositeBackend` at
    prefix ``/skills/builtin/`` means the middleware can issue paths like
    ``/skills/builtin/kb-research/SKILL.md`` which the composite strips down to
    ``/kb-research/SKILL.md`` before forwarding here. We treat any leading
    slash as anchoring at :attr:`root`.
    """

    def __init__(self, root: Path | str | None = None) -> None:
        self.root: Path = Path(root).resolve() if root else _default_builtin_root()
        if not self.root.exists():
            logger.info(
                "BuiltinSkillsBackend root %s does not exist; skills will be empty.",
                self.root,
            )

    def _resolve(self, path: str) -> Path:
        """Resolve a virtual posix path under :attr:`root`, refusing escapes."""
        bare = path.lstrip("/")
        candidate = (self.root / bare).resolve() if bare else self.root
        # Refuse symlink/.. traversal that escapes the root.
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"path {path!r} escapes builtin skills root") from exc
        return candidate

    def ls_info(self, path: str) -> list[FileInfo]:
        try:
            target = self._resolve(path)
        except ValueError as exc:
            logger.warning("BuiltinSkillsBackend.ls_info refused: %s", exc)
            return []
        if not target.exists() or not target.is_dir():
            return []

        infos: list[FileInfo] = []
        # Build virtual paths anchored at "/" because CompositeBackend already
        # stripped the route prefix before calling us.
        target_virtual = (
            "/"
            if target == self.root
            else ("/" + str(target.relative_to(self.root)).replace("\\", "/"))
        )
        for child in sorted(target.iterdir()):
            child_virtual = (
                target_virtual.rstrip("/") + "/" + child.name
                if target_virtual != "/"
                else "/" + child.name
            )
            info: FileInfo = {
                "path": child_virtual,
                "is_dir": child.is_dir(),
            }
            if child.is_file():
                with contextlib.suppress(OSError):  # pragma: no cover - defensive
                    info["size"] = child.stat().st_size
            infos.append(info)
        return infos

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        for p in paths:
            try:
                target = self._resolve(p)
            except ValueError:
                responses.append(FileDownloadResponse(path=p, error="invalid_path"))
                continue
            if not target.exists():
                responses.append(FileDownloadResponse(path=p, error="file_not_found"))
                continue
            if target.is_dir():
                responses.append(FileDownloadResponse(path=p, error="is_directory"))
                continue
            try:
                # Hard cap to avoid loading rogue mega-files into memory.
                size = target.stat().st_size
                if size > _MAX_SKILL_FILE_SIZE:
                    logger.warning(
                        "Builtin skill file %s exceeds %d bytes; truncating.",
                        target,
                        _MAX_SKILL_FILE_SIZE,
                    )
                    with target.open("rb") as fh:
                        content = fh.read(_MAX_SKILL_FILE_SIZE)
                else:
                    content = target.read_bytes()
            except PermissionError:
                responses.append(
                    FileDownloadResponse(path=p, error="permission_denied")
                )
                continue
            except OSError as exc:  # pragma: no cover - defensive
                logger.warning("Builtin skill read failed %s: %s", target, exc)
                responses.append(FileDownloadResponse(path=p, error="file_not_found"))
                continue
            responses.append(FileDownloadResponse(path=p, content=content, error=None))
        return responses


class SearchSpaceSkillsBackend(BackendProtocol):
    """Read-only view of search-space-authored skills.

    Wraps a :class:`KBPostgresBackend` and only ever reads under the privileged
    folder ``/documents/_skills/`` (configurable). The folder is intended to be
    writable only by search-space admins; this backend never writes.

    The skills middleware expects a layout like::

        /<source_root>/<skill-name>/SKILL.md

    But the KB stores documents like ``/documents/_skills/<name>/SKILL.md``.
    We expose the inner namespace by remapping each path. When mounted under
    :class:`CompositeBackend` at prefix ``/skills/space/`` the paths the
    middleware sees become ``/skills/space/<name>/SKILL.md``; the composite
    strips ``/skills/space/`` and hands us ``/<name>/SKILL.md``, which we
    rewrite to ``/documents/_skills/<name>/SKILL.md`` before forwarding to the
    KB.

    No new database table is needed: the privileged folder convention is
    enforced server-side outside of this class. We intentionally swallow any
    write/edit attempts (the base class raises ``NotImplementedError``).
    """

    DEFAULT_KB_ROOT: str = "/documents/_skills"

    def __init__(
        self,
        kb_backend: KBPostgresBackend,
        *,
        kb_root: str = DEFAULT_KB_ROOT,
    ) -> None:
        self._kb = kb_backend
        # Normalize trailing slash off so we can join cleanly.
        self._kb_root = kb_root.rstrip("/") or "/"

    def _to_kb(self, path: str) -> str:
        """Rewrite a virtual path into the underlying KB namespace."""
        bare = path.lstrip("/")
        if not bare:
            return self._kb_root
        return f"{self._kb_root}/{bare}"

    def _from_kb(self, kb_path: str) -> str:
        """Rewrite a KB path back into our virtual namespace."""
        if not kb_path.startswith(self._kb_root):
            return kb_path  # pragma: no cover - defensive
        rel = kb_path[len(self._kb_root) :]
        return rel if rel.startswith("/") else "/" + rel

    def ls_info(self, path: str) -> list[FileInfo]:
        # KBPostgresBackend exposes only the async API meaningfully; the sync
        # path falls back to ``asyncio.to_thread(...)`` in the base class. We
        # keep this stub to satisfy abstract resolution; the middleware calls
        # ``als_info``.
        raise NotImplementedError("SearchSpaceSkillsBackend is async-only")

    async def als_info(self, path: str) -> list[FileInfo]:
        kb_path = self._to_kb(path)
        try:
            infos = await self._kb.als_info(kb_path)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("SearchSpaceSkillsBackend.als_info failed: %s", exc)
            return []
        remapped: list[FileInfo] = []
        for info in infos:
            kb_p = info.get("path", "")
            if not kb_p.startswith(self._kb_root):
                continue
            remapped.append({**info, "path": self._from_kb(kb_p)})
        return remapped

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        raise NotImplementedError("SearchSpaceSkillsBackend is async-only")

    async def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        kb_paths = [self._to_kb(p) for p in paths]
        responses = await self._kb.adownload_files(kb_paths)
        # Re-map response paths back to the virtual namespace so the middleware
        # correlates them to the input list correctly.
        remapped: list[FileDownloadResponse] = []
        for original, resp in zip(paths, responses, strict=True):
            remapped.append(replace(resp, path=original))
        return remapped


SKILLS_BUILTIN_PREFIX = "/skills/builtin/"
SKILLS_SPACE_PREFIX = "/skills/space/"


def build_skills_backend_factory(
    *,
    builtin_root: Path | str | None = None,
    search_space_id: int | None = None,
) -> Callable[[ToolRuntime], BackendProtocol]:
    """Return a runtime-aware factory for the skills :class:`CompositeBackend`.

    When ``search_space_id`` is provided the composite includes a
    :class:`SearchSpaceSkillsBackend` route at ``/skills/space/`` over a fresh
    per-runtime :class:`KBPostgresBackend`, mirroring how
    :func:`build_backend_resolver` constructs the main filesystem backend.

    When ``search_space_id`` is ``None`` (e.g., desktop-local mode or unit
    tests) only the bundled :class:`BuiltinSkillsBackend` is exposed.

    Returning a factory rather than a fixed instance is intentional: the
    underlying KB backend depends on per-call ``ToolRuntime`` state
    (``staged_dirs``, ``files`` cache, runtime config), so a single shared
    instance cannot serve multiple concurrent agent runs.
    """
    builtin = BuiltinSkillsBackend(builtin_root)

    if search_space_id is None:

        def _factory_builtin_only(runtime: ToolRuntime) -> BackendProtocol:
            # Default StateBackend is intentionally inert: any path outside the
            # ``/skills/builtin/`` route resolves to an empty per-runtime state
            # so the SkillsMiddleware can iterate sources without raising.
            return CompositeBackend(
                default=StateBackend(runtime),
                routes={SKILLS_BUILTIN_PREFIX: builtin},
            )

        return _factory_builtin_only

    def _factory_with_space(runtime: ToolRuntime) -> BackendProtocol:
        # Imported lazily to avoid a hard dependency at module import time:
        # ``KBPostgresBackend`` pulls in DB models, which are unnecessary for
        # the unit-tested builtin path.
        from app.agents.new_chat.middleware.kb_postgres_backend import (
            KBPostgresBackend,
        )

        kb = KBPostgresBackend(search_space_id, runtime)
        space = SearchSpaceSkillsBackend(kb)
        return CompositeBackend(
            default=StateBackend(runtime),
            routes={
                SKILLS_BUILTIN_PREFIX: builtin,
                SKILLS_SPACE_PREFIX: space,
            },
        )

    return _factory_with_space


def default_skills_sources() -> list[str]:
    """Return the canonical source list for SkillsMiddleware (built-in then space)."""
    return [SKILLS_BUILTIN_PREFIX, SKILLS_SPACE_PREFIX]


__all__ = [
    "SKILLS_BUILTIN_PREFIX",
    "SKILLS_SPACE_PREFIX",
    "BuiltinSkillsBackend",
    "SearchSpaceSkillsBackend",
    "build_skills_backend_factory",
    "default_skills_sources",
]
