"""Render artifact pages inside an existing sandbox session."""

from __future__ import annotations

import logging
import shlex
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.sandbox import SandboxSession

logger = logging.getLogger(__name__)


class ArtifactRenderError(RuntimeError):
    """A stable render-stage error safe to return as a verification finding."""


@dataclass(frozen=True, slots=True)
class PreparedPdf:
    build_dir: str
    source_path: str
    pdf_path: str
    profile_dir: str | None = None


async def _run(session: SandboxSession, command: str, *, step: str) -> str:
    result = await session.run_command(command)
    if not result.ok:
        detail = result.output.strip() or f"exit code {result.exit_code}"
        logger.warning("%s failed: %s", step, detail)
        raise ArtifactRenderError(f"{step} failed")
    return result.output.strip()


async def prepare_pdf(
    session: SandboxSession,
    primary_path: str,
    primary_data: bytes,
    *,
    convert_to_pdf: bool,
) -> PreparedPdf:
    """Create a fresh build directory and convert the primary when needed."""
    build_id = uuid.uuid4().hex
    build_dir = f"/tmp/surfsense-verify-{build_id}"
    profile_dir = f"/tmp/surfsense-soffice-{build_id}" if convert_to_pdf else None
    quoted_build = shlex.quote(build_dir)
    try:
        await _run(
            session,
            f"mkdir -p -- {quoted_build}",
            step="creating verification build directory",
        )
        suffix = PurePosixPath(primary_path).suffix.lower()
        source_path = f"{build_dir}/primary{suffix}"
        await session.write_file(source_path, primary_data)

        if convert_to_pdf:
            pdf_path = f"{build_dir}/primary.pdf"
            await _run(
                session,
                " ".join(
                    (
                        "soffice",
                        "--headless",
                        f"-env:UserInstallation={shlex.quote(f'file://{profile_dir}')}",
                        "--convert-to pdf",
                        f"--outdir {quoted_build}",
                        shlex.quote(source_path),
                    )
                ),
                step="converting artifact to PDF",
            )
            await _run(
                session,
                f"test -s {shlex.quote(pdf_path)}",
                step="checking converted PDF",
            )
        else:
            pdf_path = source_path
            await _run(
                session,
                f"test -s {shlex.quote(pdf_path)}",
                step="checking PDF",
            )
    except Exception:
        await cleanup_render_files(
            session,
            build_dir=build_dir,
            profile_dir=profile_dir,
        )
        raise

    return PreparedPdf(
        build_dir=build_dir,
        source_path=source_path,
        pdf_path=pdf_path,
        profile_dir=profile_dir,
    )


async def rasterize_pdf(
    session: SandboxSession, prepared: PreparedPdf
) -> tuple[str, ...]:
    """Rasterize every page after the service has enforced its page ceiling."""
    page_prefix = f"{prepared.build_dir}/page"
    await _run(
        session,
        f"pdftoppm -jpeg -r 100 {shlex.quote(prepared.pdf_path)} "
        f"{shlex.quote(page_prefix)}",
        step="rendering PDF pages",
    )
    quoted_build = shlex.quote(prepared.build_dir)
    pages = await _run(
        session,
        f"set -- {quoted_build}/page-*.jpg; "
        '[ -f "$1" ] || exit 1; printf \'%s\\n\' "$@" | sort -V',
        step="finding rendered pages",
    )
    page_paths = tuple(line for line in pages.splitlines() if line)
    if not page_paths:
        raise RuntimeError("rendering PDF pages produced no images")
    return page_paths


async def cleanup_render_files(
    session: SandboxSession,
    *,
    build_dir: str,
    profile_dir: str | None = None,
) -> None:
    """Best-effort removal of one verification attempt's private files."""
    paths = [build_dir]
    if profile_dir:
        paths.append(profile_dir)
    try:
        await session.run_command(
            f"rm -rf -- {' '.join(shlex.quote(path) for path in paths)}"
        )
    except Exception:
        # Cleanup must not replace the verification verdict with a secondary error.
        return
