"""Render artifact pages inside an existing sandbox session."""

from __future__ import annotations

import shlex
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.sandbox import SandboxSession


@dataclass(frozen=True, slots=True)
class PreparedPdf:
    build_dir: str
    source_path: str
    pdf_path: str


async def _run(session: SandboxSession, command: str, *, step: str) -> str:
    result = await session.run_command(command)
    if not result.ok:
        detail = result.output.strip() or f"exit code {result.exit_code}"
        raise RuntimeError(f"{step} failed: {detail}")
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
    quoted_build = shlex.quote(build_dir)
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
        profile = f"/tmp/surfsense-soffice-{build_id}"
        await _run(
            session,
            " ".join(
                (
                    "soffice",
                    "--headless",
                    f"-env:UserInstallation={shlex.quote(f'file://{profile}')}",
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

    return PreparedPdf(
        build_dir=build_dir,
        source_path=source_path,
        pdf_path=pdf_path,
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
