"""The Office pack's install: download, verify, unpack, check, then switch to it.

In memory, like the model installs: one uvicorn worker serves the local app.
Its own slot, so it never waits behind a model download.
"""

import asyncio
import contextlib
import logging
import os
import shutil
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from modules.runtime_packs.office import layout, records
from modules.runtime_packs.office.download import (
    DownloadRefusedError,
    download_pack_file,
)
from modules.runtime_packs.office.pin import PackFile
from modules.runtime_packs.office.program import program_in
from modules.runtime_packs.office.runtime import OfficeRuntime
from modules.runtime_packs.office.smoke import smoke_test
from modules.runtime_packs.office.soffice.errors import OfficeError
from modules.runtime_packs.office.unpack.unpack import unpack

logger = logging.getLogger(__name__)

_STAGING = ".staging-"
_REMOVED = ".removed-"


class OfficeInUseError(Exception):
    """A LibreOffice run holds a file in the version folder (Windows refuses the rename)."""


@dataclass
class Activity:
    """What the install is doing now; `phase` None when nothing runs."""

    phase: str | None = None
    completed: int = 0
    total: int = 0
    error: dict[str, str] | None = None
    subscribers: set[asyncio.Event] = field(default_factory=set)


class OfficeInstaller:
    def __init__(
        self,
        file: PackFile | None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        unpacker: Callable[..., Path] = unpack,
        smoke: Callable[[OfficeRuntime], None] = smoke_test,
        version_of: Callable[[OfficeRuntime], str] | None = None,
    ) -> None:
        self.file = file
        self._transport = transport
        self._unpack = unpacker
        # Also what confirming an installed LibreOffice runs.
        self.smoke = smoke
        self.version_of = version_of
        self._task: asyncio.Task[None] | None = None
        self.activity = Activity()
        _sweep_leftovers()

    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        """Begin in the background; the caller checked egress, a pin and that none runs."""
        self.activity.error = None
        self._set("downloading", 0, self.file.size)
        self._task = asyncio.create_task(self._run(self.file))

    async def cancel(self) -> bool:
        """Stop a running install; a partial download stays for the next attempt.

        Returns once an unpack or check under way has ended, so nothing still
        writes into the version folders.
        """
        if not self.running():
            return False
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        return True

    def remove(self) -> None:
        """Forget a confirmed LibreOffice and delete the pack. Raises OfficeInUseError.

        The pack is moved aside first, so a refused move changes nothing.
        """
        pack = records.read_pack()
        removed = None
        if pack is not None:
            removed = _moved_aside(layout.versions_dir() / Path(pack.root).parts[0])
        records.write_confirmed(None)
        records.write_pack(None)
        if removed is not None:
            shutil.rmtree(removed, ignore_errors=True)
        shutil.rmtree(layout.downloads_dir(), ignore_errors=True)
        self.activity.error = None
        self._changed()

    def subscribe(self) -> asyncio.Event:
        changed = asyncio.Event()
        self.activity.subscribers.add(changed)
        return changed

    def unsubscribe(self, changed: asyncio.Event) -> None:
        self.activity.subscribers.discard(changed)

    async def _run(self, file: PackFile) -> None:
        try:
            await self._install(file)
            self._set(None)
        except asyncio.CancelledError:
            self._set(None)
            raise
        except (DownloadRefusedError, _StepFailedError) as error:
            self._fail(error.code, str(error))
        except httpx.HTTPError as error:
            self._fail("download_failed", str(error))
        except OfficeError as error:
            self._fail("smoke_failed", str(error))
        except Exception as error:
            logger.exception("Office pack install failed")
            self._fail("install_failed", str(error))

    async def _install(self, file: PackFile) -> None:
        upstream = layout.downloads_dir() / Path(file.url).name
        async for progress in download_pack_file(
            file, upstream, transport=self._transport
        ):
            self._set("downloading", progress.completed, progress.total)
        self._set("unpacking")
        # Its own per attempt, so no attempt ever unpacks into another's folder.
        staging = (
            layout.versions_dir()
            / f"{file.version}{_STAGING}{os.getpid()}-{uuid.uuid4().hex[:8]}"
        )
        try:
            root = await self._checked(file, upstream, staging)
        # A failed or cancelled build is over a gigabyte, and nothing writes to it now.
        except BaseException:
            await asyncio.to_thread(shutil.rmtree, staging, ignore_errors=True)
            raise
        final = layout.versions_dir() / file.version
        # Unrecorded, but never deleted in place: a run may still hold it.
        try:
            aside = _moved_aside(final)
        except OfficeInUseError as error:
            raise _StepFailedError("in_use", str(error)) from error
        if aside is not None:
            await asyncio.to_thread(shutil.rmtree, aside, ignore_errors=True)
        staging.rename(final)
        relative = (final / root.relative_to(staging)).relative_to(
            layout.versions_dir()
        )
        records.write_pack(records.PackRecord(file.version, relative.as_posix()))
        upstream.unlink(missing_ok=True)
        _sweep_other_versions(keep=file.version)

    async def _checked(self, file: PackFile, upstream: Path, staging: Path) -> Path:
        """Unpack into `staging` and run the smoke there; the install root inside it."""
        try:
            root = await _to_its_end(self._unpack, file.packaging, upstream, staging)
        except Exception as error:
            raise _StepFailedError("unpack_failed", str(error)) from error
        self._set("checking")
        await _to_its_end(
            self.smoke, OfficeRuntime(program_in(root), file.version, "pack")
        )
        return root

    def _set(self, phase: str | None, completed: int = 0, total: int = 0) -> None:
        self.activity.phase = phase
        self.activity.completed = completed
        self.activity.total = total
        self._changed()

    def _fail(self, code: str, message: str) -> None:
        logger.warning("Office pack install failed: %s: %s", code, message)
        self.activity.error = {"code": code, "message": message}
        self._set(None)

    def _changed(self) -> None:
        for changed in self.activity.subscribers:
            changed.set()


class _StepFailedError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


async def _to_its_end[T](call: Callable[..., T], *args: object) -> T:
    """`call` in a thread; a cancel waits for it to end, since msiexec, tar and soffice run on."""
    work = asyncio.ensure_future(asyncio.to_thread(call, *args))
    try:
        return await asyncio.shield(work)
    except asyncio.CancelledError:
        with contextlib.suppress(Exception):
            await work
        raise


def _moved_aside(folder: Path) -> Path | None:
    """`folder` renamed for deleting, or None when it is gone. Raises OfficeInUseError."""
    if not folder.exists():
        return None
    aside = folder.with_name(f"{folder.name}{_REMOVED}{time.time_ns()}")
    try:
        folder.rename(aside)
    except OSError as error:
        raise OfficeInUseError(str(error)) from error
    return aside


def _sweep_leftovers() -> None:
    """Half-unpacked and removed folders from an earlier run."""
    versions = layout.versions_dir()
    if not versions.is_dir():
        return
    for folder in versions.iterdir():
        if _STAGING in folder.name or _REMOVED in folder.name:
            shutil.rmtree(folder, ignore_errors=True)


def _sweep_other_versions(*, keep: str) -> None:
    """An older version is deleted once the new one is in use; one in use stays."""
    for folder in layout.versions_dir().iterdir():
        if folder.name != keep and folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)
