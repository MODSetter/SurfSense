"""SurfSense's license server's refresh and job-pack routes, answering as the real ones do
(contract 1, producer rule 7; contract 6)."""

import asyncio
import io
import json
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import (
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from starlette.routing import Route

from modules.jobs.packs.manifest import MANIFEST, version_key

# A runner and its version, as contract 6's request names each.
_RUNNER = r"^[a-z][a-z0-9-]{0,63}/[1-9][0-9]{0,5}$"
# The server's own sentences for a job its record of the license lacks, and for a job that
# comes only in packs holding one it lacks.
JOB_NOT_INCLUDED = (
    "This license does not include that job. Jobs come with a Business license, or its "
    "14-day trial."
)
PACK_NOT_COVERED = (
    "Every pack of that job also holds a job this license does not include."
)


class _JobPackRequest(BaseModel):
    """Contract 6's request, checked as the license server checks it before anything else;
    a field it does not know is ignored."""

    key: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1024)
    ]
    entitlement: Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")]
    # 0 to 9 only, as the server's VERSION_PATTERN: \d takes any script's digits.
    installed_version: (
        Annotated[
            str, StringConstraints(pattern=r"^[0-9]{1,9}\.[0-9]{1,9}\.[0-9]{1,9}$")
        ]
        | None
    ) = None
    runners: Annotated[
        list[Annotated[str, StringConstraints(pattern=_RUNNER)]],
        Field(min_length=1, max_length=16),
    ]


@dataclass(frozen=True)
class Asked:
    path: str
    query: str
    body: dict
    user_agent: str


@dataclass
class StandInLicenseServer:
    """`files` holds each key's current file; `refusal`, an answer given instead, as
    `(status, detail)`; `asked`, every refresh it received.

    The job-pack route sends the zip `offer` put in `packs` for the entitlement asked for, or
    204 when the app already has that version, unless `ignores_installed_version`. The
    `pack_*` fields answer otherwise: a refusal, a delay, a 302 to another URL, the 404 of a
    server without the route, another Content-Type. `license_jobs`, once set, is the jobs
    the server's record of the license lists, Keygen's `metadata.jobs`: a job it lacks is
    refused `job_not_included`, and a pack holding a job it lacks `pack_not_covered`, as the
    server refuses them. `pack_asked` keeps its requests apart from the refreshes. A body
    that breaks contract 6's request rules gets the server's 422 list, also kept in
    `pack_rules_broken`. `before_pack` runs on a thread of the server's just before a zip is
    sent, as when something happens in the app meanwhile."""

    files: dict[str, str] = field(default_factory=dict)
    refusal: tuple[int, object] | None = None
    delay_seconds: float = 0.0
    asked: list[Asked] = field(default_factory=list)
    packs: dict[str, bytes] = field(default_factory=dict)
    pack_refusal: tuple[int, object] | None = None
    pack_delay_seconds: float = 0.0
    pack_redirect: str | None = None
    pack_route_missing: bool = False
    pack_content_type: str = "application/zip"
    ignores_installed_version: bool = False
    license_jobs: frozenset[str] | None = None
    pack_asked: list[Asked] = field(default_factory=list)
    pack_rules_broken: list[list[dict]] = field(default_factory=list)
    before_pack: Callable[[], None] | None = None

    def offer(self, entitlement: str, archive: bytes) -> None:
        """Publish `archive` as the newest pack with a job for `entitlement`."""
        self.packs[entitlement] = archive

    def app(self) -> Starlette:
        return Starlette(
            routes=[
                Route("/api/v1/license/refresh", self._refresh, methods=["POST"]),
                Route("/api/v1/license/job-pack", self._job_pack, methods=["POST"]),
            ]
        )

    async def _refresh(self, request: Request) -> Response:
        body = await request.json()
        self.asked.append(_asked(request, body))
        await asyncio.sleep(self.delay_seconds)
        if self.refusal is not None:
            status, detail = self.refusal
            return JSONResponse({"detail": detail}, status)
        certificate = self.files.get(body.get("key", ""))
        if certificate is None:
            return JSONResponse({"detail": "No license has that key."}, 404)
        return PlainTextResponse(
            certificate,
            headers={
                "Content-Disposition": 'attachment; filename="surfsense.lic"',
                "Cache-Control": "no-store",
            },
        )

    async def _job_pack(self, request: Request) -> Response:
        if self.pack_route_missing:
            # What a server answers for a path it has no route for, as FastAPI words it.
            return JSONResponse({"detail": "Not Found"}, 404)
        body = await request.json()
        self.pack_asked.append(_asked(request, body))
        broken = _broken_rules(body)
        if broken:
            self.pack_rules_broken.append(broken)
            return JSONResponse({"detail": broken}, 422)
        await asyncio.sleep(self.pack_delay_seconds)
        if self.pack_redirect is not None:
            return RedirectResponse(self.pack_redirect, 302)
        if self.pack_refusal is not None:
            status, detail = self.pack_refusal
            return JSONResponse({"detail": detail}, status)
        entitlement = body.get("entitlement", "")
        if self.license_jobs is not None and entitlement not in self.license_jobs:
            return _refused(403, "job_not_included", JOB_NOT_INCLUDED)
        archive = self.packs.get(entitlement)
        if archive is None:
            return _refused(
                503,
                "job_packs_unavailable",
                "Jobs cannot be downloaded right now. Try again later.",
            )
        pack_id, version, entitlements = _identity(archive)
        if self.license_jobs is not None and not entitlements <= self.license_jobs:
            return _refused(403, "pack_not_covered", PACK_NOT_COVERED)
        headers = {
            "X-Job-Pack-Id": pack_id,
            "X-Job-Pack-Version": version,
            "Cache-Control": "no-store",
        }
        installed = body.get("installed_version")
        if (
            installed
            and version != "?"
            and not self.ignores_installed_version
            and version_key(installed) >= version_key(version)
        ):
            return Response(status_code=204, headers=headers)
        if self.before_pack is not None:
            await asyncio.to_thread(self.before_pack)
        return Response(
            archive,
            headers={
                **headers,
                "Content-Type": self.pack_content_type,
                "Content-Disposition": f'attachment; filename="{pack_id}-{version}.zip"',
            },
        )


def _broken_rules(body: object) -> list[dict]:
    """Each rule of the request that `body` breaks, listed as the server's own 422 lists them:
    the error's type, where, and why, never what was sent."""
    try:
        _JobPackRequest.model_validate(body)
    except ValidationError as refused:
        return [
            {"type": error["type"], "loc": ["body", *error["loc"]], "msg": error["msg"]}
            for error in refused.errors()
        ]
    return []


def _asked(request: Request, body: dict) -> Asked:
    return Asked(
        request.url.path,
        request.url.query,
        body,
        request.headers.get("user-agent", ""),
    )


def _refused(status: int, code: str, message: str) -> JSONResponse:
    """A refusal as the server words one: a code and a sentence a person can read."""
    return JSONResponse({"detail": {"code": code, "message": message}}, status)


def _identity(archive: bytes) -> tuple[str, str, frozenset[str]]:
    """The id and version the archive's manifest names, and its jobs' entitlements; "?" and
    none for bytes that are no pack."""
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            manifest = json.loads(zipped.read(MANIFEST))
        jobs = frozenset(
            job["entitlement"] for job in manifest["jobs"] if job.get("entitlement")
        )
        return str(manifest["id"]), str(manifest["version"]), jobs
    except (zipfile.BadZipFile, KeyError, ValueError, TypeError, AttributeError):
        return "?", "?", frozenset()
