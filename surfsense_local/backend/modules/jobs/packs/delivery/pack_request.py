"""One request to SurfSense's licence server for the newest pack of one job (contract 6, consumer
rules 3, 4 and 6): the key in the body, never in the URL, and never a redirect followed, so the
app reaches no host but the licence server."""

from __future__ import annotations

import json
import logging
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

import httpx

from modules.jobs.packs.delivery.outcomes import OutcomeCode, default_message
from modules.jobs.packs.installed import packs_dir
from modules.jobs.packs.integrity import MAX_PACK_BYTES
from modules.jobs.packs.manifest import RUNNERS
from modules.license.renewal.renewed_file import USER_AGENT

PACK_ROUTE = "/api/v1/license/job-pack"
CONNECT_SECONDS = 10.0
# Per read, not for the whole body: a 50 MB pack on a slow line still arrives.
READ_SECONDS = 60.0
# A refusal's body is a code and a sentence; past this it is not one.
MAX_DETAIL_BYTES = 64 * 1024
# A 422 list is the app's own bug; its first few errors say which field.
_LOGGED_ERRORS = 5

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Downloaded:
    # The zip, in the packs folder under a scratch name; the caller removes it.
    path: Path


@dataclass(frozen=True)
class Answered:
    outcome: OutcomeCode
    message: str
    detail: str | None = None


async def request_pack(
    server: str, key: str, entitlement: str, installed_version: str | None
) -> Downloaded | Answered:
    """The pack the server sent, on disk, or what it answered instead. Neither the key nor the
    body is ever logged."""
    body: dict[str, object] = {
        "key": key,
        "entitlement": entitlement,
        "runners": list(RUNNERS),
    }
    if installed_version is not None:
        body["installed_version"] = installed_version
    try:
        async with (
            httpx.AsyncClient(
                timeout=httpx.Timeout(READ_SECONDS, connect=CONNECT_SECONDS),
                headers={"User-Agent": USER_AGENT},
                follow_redirects=False,
            ) as http,
            http.stream("POST", f"{server}{PACK_ROUTE}", json=body) as response,
        ):
            _log_offer(response, entitlement)
            if response.status_code == 200:
                return await _downloaded(response, entitlement)
            return _answered(response.status_code, await _detail(response), entitlement)
    except httpx.HTTPError as failed:
        logger.info(
            "job pack for %s not fetched: %s", entitlement, type(failed).__name__
        )
        return Answered("unavailable", default_message("unavailable"))


def _log_offer(response: httpx.Response, entitlement: str) -> None:
    """The pack the headers name, for the log only: the zip's own manifest decides."""
    pack_id = response.headers.get("x-job-pack-id")
    if pack_id is not None:
        logger.info(
            "license server answered %d for %s: %s %s",
            response.status_code,
            entitlement,
            pack_id[:64],
            response.headers.get("x-job-pack-version", "")[:32],
        )


async def _downloaded(
    response: httpx.Response, entitlement: str
) -> Downloaded | Answered:
    media = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media != "application/zip":
        logger.warning(
            "job pack for %s not taken: the license server sent %s, not a zip",
            entitlement,
            media[:64] or "no type",
        )
        return Answered("unavailable", default_message("unavailable"))
    folder = packs_dir()
    path: Path | None = None
    written = 0
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            dir=folder, prefix=".download-", suffix=".zip", delete=False
        ) as file:
            path = Path(file.name)
            async for chunk in response.aiter_bytes():
                written += len(chunk)
                if written > MAX_PACK_BYTES:
                    break
                file.write(chunk)
    except OSError as unwritten:
        # A full disk, or a packs folder that cannot be made: the installed pack stays,
        # and the codes after this one are still asked for.
        _discard(path)
        logger.warning("job pack for %s not written: %s", entitlement, unwritten)
        return Answered("not_written", default_message("not_written"))
    except BaseException:
        _discard(path)
        raise
    if written > MAX_PACK_BYTES:
        _discard(path)
        return Answered("refused", "The pack is larger than 50 MB.", "PACK_TOO_LARGE")
    return Downloaded(path)


def _discard(path: Path | None) -> None:
    """The download's scratch file, closed by then: Windows cannot remove a file still open.
    One left behind is swept by a later install."""
    if path is not None:
        with suppress(OSError):
            path.unlink(missing_ok=True)


async def _detail(response: httpx.Response) -> object:
    """The answer's `detail`, read from at most MAX_DETAIL_BYTES; None without one."""
    data = b""
    async for chunk in response.aiter_bytes():
        data += chunk
        if len(data) > MAX_DETAIL_BYTES:
            return None
    try:
        answer = json.loads(data)
    except (ValueError, RecursionError):
        return None
    return answer.get("detail") if isinstance(answer, dict) else None


def _answered(status: int, detail: object, entitlement: str) -> Answered:
    """Consumer rule 6: every answer keeps the installed pack; only a 404 that names a
    license refusal is one, since a server without the route answers 404 too."""
    named = detail if isinstance(detail, dict) else {}
    code = named.get("code") if isinstance(named.get("code"), str) else None
    said = named.get("message")
    message = said if isinstance(said, str) and said.strip() else None
    if status == 204:
        return Answered("current", default_message("current"))
    if status == 403:
        # The license lacks the job, or every pack of it holds a job the license lacks; any
        # other code is a refusal of the license itself.
        outcome: OutcomeCode = "license_not_valid"
        if code == "job_not_included":
            outcome = "job_not_included"
        elif code == "pack_not_covered":
            outcome = "pack_not_covered"
        return Answered(outcome, message or default_message(outcome), code)
    if status == 404 and code == "license_not_found":
        return Answered("license_not_found", default_message("license_not_found"), code)
    if status == 409 and code == "needs_newer_app":
        return Answered(
            "needs_newer_app", message or default_message("needs_newer_app"), code
        )
    if status == 422 and code == "unknown_job":
        logger.warning("the license server sells no job %s", entitlement)
        return Answered("unknown_job", message or default_message("unknown_job"), code)
    if status == 422 and isinstance(detail, list):
        errors = [
            (error.get("type"), error.get("loc"))
            for error in detail[:_LOGGED_ERRORS]
            if isinstance(error, dict)
        ]
        logger.error(
            "the license server refused the app's job-pack request (422): %s", errors
        )
        return Answered("unavailable", default_message("unavailable"))
    if status == 429:
        return Answered("rate_limited", default_message("rate_limited"), code)
    logger.info(
        "job pack for %s not sent: the license server answered %d", entitlement, status
    )
    return Answered("unavailable", default_message("unavailable"), code)
