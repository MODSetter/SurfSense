"""
Resume generation tool for the SurfSense agent.

Generates a structured resume as Typst source code using the rendercv package.
The LLM outputs only the content body (= heading, sections, entries) while
the template header (import + show rule) is hardcoded and prepended by the
backend.  This eliminates LLM errors in the complex configuration block.

Templates are stored in a registry so new designs can be added by defining
a new entry in _TEMPLATES.

Uses the same short-lived session pattern as generate_report so no DB
connection is held during the long LLM call.
"""

import io
import logging
import re
from datetime import UTC, datetime
from typing import Any

import pypdf
import typst
from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from app.db import Report, shielded_async_session
from app.services.llm_service import get_document_summary_llm

logger = logging.getLogger(__name__)


# ─── Template Registry ───────────────────────────────────────────────────────
# Each template defines:
#   header              - Typst import + show rule with {name}, {year}, {month}, {day} placeholders
#   component_reference - component docs shown to the LLM
#   rules               - generation rules for the LLM

_TEMPLATES: dict[str, dict[str, str]] = {
    "classic": {
        "header": """\
#import "@preview/rendercv:0.3.0": *

#show: rendercv.with(
  name: "{name}",
  title: "{name} - Resume",
  footer: context {{ [#emph[{name} -- #str(here().page())\\/#str(counter(page).final().first())]] }},
  top-note: [ #emph[Last updated in {month_name} {year}] ],
  locale-catalog-language: "en",
  text-direction: ltr,
  page-size: "us-letter",
  page-top-margin: 0.7in,
  page-bottom-margin: 0.7in,
  page-left-margin: 0.7in,
  page-right-margin: 0.7in,
  page-show-footer: false,
  page-show-top-note: true,
  colors-body: rgb(0, 0, 0),
  colors-name: rgb(0, 0, 0),
  colors-headline: rgb(0, 0, 0),
  colors-connections: rgb(0, 0, 0),
  colors-section-titles: rgb(0, 0, 0),
  colors-links: rgb(0, 0, 0),
  colors-footer: rgb(128, 128, 128),
  colors-top-note: rgb(128, 128, 128),
  typography-line-spacing: 0.6em,
  typography-alignment: "justified",
  typography-date-and-location-column-alignment: right,
  typography-font-family-body: "XCharter",
  typography-font-family-name: "XCharter",
  typography-font-family-headline: "XCharter",
  typography-font-family-connections: "XCharter",
  typography-font-family-section-titles: "XCharter",
  typography-font-size-body: 10pt,
  typography-font-size-name: 25pt,
  typography-font-size-headline: 10pt,
  typography-font-size-connections: 10pt,
  typography-font-size-section-titles: 1.2em,
  typography-small-caps-name: false,
  typography-small-caps-headline: false,
  typography-small-caps-connections: false,
  typography-small-caps-section-titles: false,
  typography-bold-name: false,
  typography-bold-headline: false,
  typography-bold-connections: false,
  typography-bold-section-titles: true,
  links-underline: true,
  links-show-external-link-icon: false,
  header-alignment: center,
  header-photo-width: 3.5cm,
  header-space-below-name: 0.7cm,
  header-space-below-headline: 0.7cm,
  header-space-below-connections: 0.7cm,
  header-connections-hyperlink: true,
  header-connections-show-icons: false,
  header-connections-display-urls-instead-of-usernames: true,
  header-connections-separator: "|",
  header-connections-space-between-connections: 0.5cm,
  section-titles-type: "with_full_line",
  section-titles-line-thickness: 0.5pt,
  section-titles-space-above: 0.5cm,
  section-titles-space-below: 0.3cm,
  sections-allow-page-break: true,
  sections-space-between-text-based-entries: 0.15cm,
  sections-space-between-regular-entries: 0.42cm,
  entries-date-and-location-width: 4.15cm,
  entries-side-space: 0cm,
  entries-space-between-columns: 0.1cm,
  entries-allow-page-break: false,
  entries-short-second-row: false,
  entries-degree-width: 1cm,
  entries-summary-space-left: 0cm,
  entries-summary-space-above: 0.08cm,
  entries-highlights-bullet: text(13pt, [\\u{2022}], baseline: -0.6pt),
  entries-highlights-nested-bullet: text(13pt, [\\u{2022}], baseline: -0.6pt),
  entries-highlights-space-left: 0cm,
  entries-highlights-space-above: 0.08cm,
  entries-highlights-space-between-items: 0.08cm,
  entries-highlights-space-between-bullet-and-text: 0.3em,
  date: datetime(
    year: {year},
    month: {month},
    day: {day},
  ),
)

""",
        "component_reference": """\
Available components (use ONLY these):

= Full Name                              // Top-level heading — person's full name

#connections(                            // Contact info row (pipe-separated)
  [City, Country],
  [#link("mailto:email@example.com", icon: false, if-underline: false, if-color: false)[email\\@example.com]],
  [#link("https://linkedin.com/in/user", icon: false, if-underline: false, if-color: false)[linkedin.com\\/in\\/user]],
  [#link("https://github.com/user", icon: false, if-underline: false, if-color: false)[github.com\\/user]],
)

== Section Title                         // Section heading (arbitrary name)

#regular-entry(                          // Work experience, projects, publications, etc.
  [
    #strong[Role/Title], Company Name -- Location
  ],
  [
    Start -- End
  ],
  main-column-second-row: [
    - Achievement or responsibility
    - Another bullet point
  ],
)

#education-entry(                        // Education entries
  [
    #strong[Institution], Degree in Field -- Location
  ],
  [
    Start -- End
  ],
  main-column-second-row: [
    - GPA, honours, relevant coursework
  ],
)

#summary([Short paragraph summary])     // Optional summary inside an entry
#content-area([Free-form content])       // Freeform text block

For skills sections, use one bullet per category label:
- #strong[Category:] item1, item2, item3

For simple list sections (e.g. Honors), use plain bullet points:
- Item one
- Item two
""",
        "rules": """\
RULES:
- Do NOT include any #import or #show lines. Start directly with = Full Name.
- Output ONLY valid Typst content. No explanatory text before or after.
- Do NOT wrap output in ```typst code fences.
- The = heading MUST use the person's COMPLETE full name exactly as provided. NEVER shorten or abbreviate.
- Escape @ symbols inside link labels with a backslash: email\\@example.com
- Escape forward slashes in link display text: linkedin.com\\/in\\/user
- Every section MUST use == heading.
- Use #regular-entry() for experience, projects, publications, certifications, and similar entries.
- Use #education-entry() for education.
- For skills sections, use one bullet line per category with a bold label.
- Keep content professional, concise, and achievement-oriented.
- Use action verbs for bullet points (Led, Built, Designed, Reduced, etc.).
- This template works for ALL professions — adapt sections to the user's field.
- Default behavior should prioritize concise one-page content.
""",
    },
}

DEFAULT_TEMPLATE = "classic"
MIN_RESUME_PAGES = 1
MAX_RESUME_PAGES = 5
MAX_COMPRESSION_ATTEMPTS = 2


# ─── Template Helpers ─────────────────────────────────────────────────────────


def _get_template(template_id: str | None = None) -> dict[str, str]:
    """Get a template by ID, falling back to default."""
    return _TEMPLATES.get(template_id or DEFAULT_TEMPLATE, _TEMPLATES[DEFAULT_TEMPLATE])


_MONTH_NAMES = [
    "",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


def _build_header(template: dict[str, str], name: str) -> str:
    """Build the template header with the person's name and current date."""
    now = datetime.now(tz=UTC)
    return (
        template["header"]
        .replace("{name}", name)
        .replace("{year}", str(now.year))
        .replace("{month}", str(now.month))
        .replace("{day}", str(now.day))
        .replace("{month_name}", _MONTH_NAMES[now.month])
    )


def _strip_header(full_source: str) -> str:
    """Strip the import + show rule from stored source to get the body only.

    Finds the closing parenthesis of the rendercv.with(...) block by tracking
    nesting depth, then returns everything after it.
    """
    show_match = re.search(r"#show:\s*rendercv\.with\(", full_source)
    if not show_match:
        return full_source

    start = show_match.end()
    depth = 1
    i = start
    while i < len(full_source) and depth > 0:
        if full_source[i] == "(":
            depth += 1
        elif full_source[i] == ")":
            depth -= 1
        i += 1

    return full_source[i:].lstrip("\n")


def _extract_name(body: str) -> str | None:
    """Extract the person's full name from the = heading in the body."""
    match = re.search(r"^=\s+(.+)$", body, re.MULTILINE)
    return match.group(1).strip() if match else None


def _strip_imports(body: str) -> str:
    """Remove any #import or #show lines the LLM might accidentally include."""
    lines = body.split("\n")
    cleaned: list[str] = []
    skip_show = False
    depth = 0

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("#import"):
            continue

        if skip_show:
            depth += stripped.count("(") - stripped.count(")")
            if depth <= 0:
                skip_show = False
            continue

        if stripped.startswith("#show:") and "rendercv" in stripped:
            depth = stripped.count("(") - stripped.count(")")
            if depth > 0:
                skip_show = True
            continue

        cleaned.append(line)

    result = "\n".join(cleaned).strip()
    return result


def _build_llm_reference(template: dict[str, str]) -> str:
    """Build the LLM prompt reference from a template."""
    return f"""\
You MUST output valid Typst content for a resume.
Do NOT include any #import or #show lines — those are handled automatically.
Start directly with the = Full Name heading.

{template["component_reference"]}

{template["rules"]}"""


# ─── Prompts ─────────────────────────────────────────────────────────────────

_RESUME_PROMPT = """\
You are an expert resume writer. Generate professional resume content as Typst markup.

{llm_reference}

**User Information:**
{user_info}

**Target Maximum Pages:** {max_pages}

{user_instructions_section}

Generate the resume content now (starting with = Full Name):
"""

_REVISION_PROMPT = """\
You are an expert resume editor. Modify the existing resume according to the instructions.
Apply ONLY the requested changes — do NOT rewrite sections that are not affected.

{llm_reference}

**Target Maximum Pages:** {max_pages}

**Modification Instructions:** {user_instructions}

**EXISTING RESUME CONTENT:**

{previous_content}

---

Output the complete, updated resume content with the changes applied (starting with = Full Name):
"""

_FIX_COMPILE_PROMPT = """\
The resume content you generated failed to compile. Fix the error while preserving all content.

{llm_reference}

**Compilation Error:**
{error}

**Full Typst Source (for context — error line numbers refer to this):**
{full_source}

**Your content starts after the template header. Output ONLY the content portion \
(starting with = Full Name), NOT the #import or #show rule:**
"""

_COMPRESS_TO_PAGE_LIMIT_PROMPT = """\
The resume compiles, but it exceeds the maximum allowed page count.
Compress the resume while preserving high-impact accomplishments and role relevance.

{llm_reference}

**Target Maximum Pages:** {max_pages}
**Current Page Count:** {actual_pages}
**Compression Attempt:** {attempt_number}

Compression priorities (in this order):
1) Keep recent, high-impact, role-relevant bullets.
2) Remove low-impact or redundant bullets.
3) Shorten verbose wording while preserving meaning.
4) Trim older or less relevant details before recent ones.

Return the complete updated Typst content (starting with = Full Name), and keep it at or below the target pages.

**EXISTING RESUME CONTENT:**
{previous_content}
"""


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _strip_typst_fences(text: str) -> str:
    """Remove wrapping ```typst ... ``` fences that LLMs sometimes add."""
    stripped = text.strip()
    m = re.match(r"^(`{3,})(?:typst|typ)?\s*\n", stripped)
    if m:
        fence = m.group(1)
        if stripped.endswith(fence):
            stripped = stripped[m.end() :]
            stripped = stripped[: -len(fence)].rstrip()
    return stripped


def _compile_typst(source: str) -> bytes:
    """Compile Typst source to PDF bytes. Raises on failure."""
    return typst.compile(source.encode("utf-8"))


def _count_pdf_pages(pdf_bytes: bytes) -> int:
    """Count the number of pages in compiled PDF bytes."""
    with io.BytesIO(pdf_bytes) as pdf_stream:
        reader = pypdf.PdfReader(pdf_stream)
        return len(reader.pages)


def _validate_max_pages(max_pages: int) -> int:
    """Validate and normalize max_pages input."""
    if MIN_RESUME_PAGES <= max_pages <= MAX_RESUME_PAGES:
        return max_pages
    msg = (
        f"max_pages must be between {MIN_RESUME_PAGES} and "
        f"{MAX_RESUME_PAGES}. Received: {max_pages}"
    )
    raise ValueError(msg)


# ─── Tool Factory ───────────────────────────────────────────────────────────


def create_generate_resume_tool(
    search_space_id: int,
    thread_id: int | None = None,
):
    """
    Factory function to create the generate_resume tool.

    Generates a Typst-based resume, validates it via compilation,
    and stores the source in the Report table with content_type='typst'.
    The LLM generates only the content body; the template header is
    prepended by the backend.
    """

    @tool
    async def generate_resume(
        user_info: str,
        user_instructions: str | None = None,
        parent_report_id: int | None = None,
        max_pages: int = 1,
    ) -> dict[str, Any]:
        """
        Generate a professional resume as a Typst document.

        Use this tool when the user asks to create, build, generate, write,
        or draft a resume or CV. Also use it when the user wants to modify,
        update, or revise an existing resume generated in this conversation.

        Trigger phrases include:
        - "build me a resume", "create my resume", "generate a CV"
        - "update my resume", "change my title", "add my new job"
        - "make my resume more concise", "reformat my resume"

        Do NOT use this tool for:
        - General questions about resumes or career advice
        - Reviewing or critiquing a resume without changes
        - Cover letters (use generate_report instead)

        VERSIONING — parent_report_id:
        - Set parent_report_id when the user wants to MODIFY an existing
          resume that was already generated in this conversation.
        - Leave as None for new resumes.

        Args:
            user_info: The user's resume content — work experience,
                education, skills, contact info, etc. Can be structured
                or unstructured text.
            user_instructions: Optional style or content preferences
                (e.g. "emphasize leadership", "keep it to one page",
                "use a modern style"). For revisions, describe what to change.
            parent_report_id: ID of a previous resume to revise (creates
                new version in the same version group).
            max_pages: Maximum number of pages for the generated resume.
                Defaults to 1. Allowed range: 1-5.

        Returns:
            Dict with status, report_id, title, and content_type.
        """
        report_group_id: int | None = None
        parent_content: str | None = None

        template = _get_template()
        llm_reference = _build_llm_reference(template)

        async def _save_failed_report(error_msg: str) -> int | None:
            try:
                async with shielded_async_session() as session:
                    failed = Report(
                        title="Resume",
                        content=None,
                        content_type="typst",
                        report_metadata={
                            "status": "failed",
                            "error_message": error_msg,
                        },
                        report_style="resume",
                        search_space_id=search_space_id,
                        thread_id=thread_id,
                        report_group_id=report_group_id,
                    )
                    session.add(failed)
                    await session.commit()
                    await session.refresh(failed)
                    if not failed.report_group_id:
                        failed.report_group_id = failed.id
                        await session.commit()
                    logger.info(
                        f"[generate_resume] Saved failed report {failed.id}: {error_msg}"
                    )
                    return failed.id
            except Exception:
                logger.exception(
                    "[generate_resume] Could not persist failed report row"
                )
                return None

        try:
            try:
                validated_max_pages = _validate_max_pages(max_pages)
            except ValueError as e:
                error_msg = str(e)
                report_id = await _save_failed_report(error_msg)
                return {
                    "status": "failed",
                    "error": error_msg,
                    "report_id": report_id,
                    "title": "Resume",
                    "content_type": "typst",
                }

            # ── Phase 1: READ ─────────────────────────────────────────────
            async with shielded_async_session() as read_session:
                if parent_report_id:
                    parent_report = await read_session.get(Report, parent_report_id)
                    if parent_report:
                        report_group_id = parent_report.report_group_id
                        parent_content = parent_report.content
                        logger.info(
                            f"[generate_resume] Revising from parent {parent_report_id} "
                            f"(group {report_group_id})"
                        )

                llm = await get_document_summary_llm(read_session, search_space_id)

            if not llm:
                error_msg = (
                    "No LLM configured. Please configure a language model in Settings."
                )
                report_id = await _save_failed_report(error_msg)
                return {
                    "status": "failed",
                    "error": error_msg,
                    "report_id": report_id,
                    "title": "Resume",
                    "content_type": "typst",
                }

            # ── Phase 2: LLM GENERATION ───────────────────────────────────

            user_instructions_section = ""
            if user_instructions:
                user_instructions_section = (
                    f"**Additional Instructions:** {user_instructions}"
                )

            if parent_content:
                dispatch_custom_event(
                    "report_progress",
                    {"phase": "writing", "message": "Updating your resume"},
                )
                parent_body = _strip_header(parent_content)
                prompt = _REVISION_PROMPT.format(
                    llm_reference=llm_reference,
                    max_pages=validated_max_pages,
                    user_instructions=user_instructions
                    or "Improve and refine the resume.",
                    previous_content=parent_body,
                )
            else:
                dispatch_custom_event(
                    "report_progress",
                    {"phase": "writing", "message": "Building your resume"},
                )
                prompt = _RESUME_PROMPT.format(
                    llm_reference=llm_reference,
                    user_info=user_info,
                    max_pages=validated_max_pages,
                    user_instructions_section=user_instructions_section,
                )

            response = await llm.ainvoke([HumanMessage(content=prompt)])
            body = response.content

            if not body or not isinstance(body, str):
                error_msg = "LLM returned empty or invalid content"
                report_id = await _save_failed_report(error_msg)
                return {
                    "status": "failed",
                    "error": error_msg,
                    "report_id": report_id,
                    "title": "Resume",
                    "content_type": "typst",
                }

            body = _strip_typst_fences(body)
            body = _strip_imports(body)

            # ── Phase 3: ASSEMBLE + COMPILE ───────────────────────────────
            dispatch_custom_event(
                "report_progress",
                {"phase": "compiling", "message": "Compiling resume..."},
            )

            name = _extract_name(body) or "Resume"
            typst_source = ""
            actual_pages = 0
            compression_attempts = 0
            target_page_met = False

            for compression_round in range(MAX_COMPRESSION_ATTEMPTS + 1):
                header = _build_header(template, name)
                typst_source = header + body
                compile_error: str | None = None
                pdf_bytes: bytes | None = None

                for compile_attempt in range(2):
                    try:
                        pdf_bytes = _compile_typst(typst_source)
                        compile_error = None
                        break
                    except Exception as e:
                        compile_error = str(e)
                        logger.warning(
                            "[generate_resume] Compile attempt %s failed: %s",
                            compile_attempt + 1,
                            compile_error,
                        )

                        if compile_attempt == 0:
                            dispatch_custom_event(
                                "report_progress",
                                {
                                    "phase": "fixing",
                                    "message": "Fixing compilation issue...",
                                },
                            )
                            fix_prompt = _FIX_COMPILE_PROMPT.format(
                                llm_reference=llm_reference,
                                error=compile_error,
                                full_source=typst_source,
                            )
                            fix_response = await llm.ainvoke(
                                [HumanMessage(content=fix_prompt)]
                            )
                            if fix_response.content and isinstance(
                                fix_response.content, str
                            ):
                                body = _strip_typst_fences(fix_response.content)
                                body = _strip_imports(body)
                                name = _extract_name(body) or name
                                header = _build_header(template, name)
                                typst_source = header + body

                if compile_error or not pdf_bytes:
                    error_msg = (
                        "Typst compilation failed after 2 attempts: "
                        f"{compile_error or 'Unknown compile error'}"
                    )
                    report_id = await _save_failed_report(error_msg)
                    return {
                        "status": "failed",
                        "error": error_msg,
                        "report_id": report_id,
                        "title": "Resume",
                        "content_type": "typst",
                    }

                actual_pages = _count_pdf_pages(pdf_bytes)
                if actual_pages <= validated_max_pages:
                    target_page_met = True
                    break

                if compression_round >= MAX_COMPRESSION_ATTEMPTS:
                    break

                compression_attempts += 1
                dispatch_custom_event(
                    "report_progress",
                    {
                        "phase": "compressing",
                        "message": f"Condensing resume to {validated_max_pages} page(s)...",
                    },
                )
                compress_prompt = _COMPRESS_TO_PAGE_LIMIT_PROMPT.format(
                    llm_reference=llm_reference,
                    max_pages=validated_max_pages,
                    actual_pages=actual_pages,
                    attempt_number=compression_attempts,
                    previous_content=body,
                )
                compress_response = await llm.ainvoke(
                    [HumanMessage(content=compress_prompt)]
                )
                if not compress_response.content or not isinstance(
                    compress_response.content, str
                ):
                    error_msg = "LLM returned empty content while compressing resume"
                    report_id = await _save_failed_report(error_msg)
                    return {
                        "status": "failed",
                        "error": error_msg,
                        "report_id": report_id,
                        "title": "Resume",
                        "content_type": "typst",
                    }

                body = _strip_typst_fences(compress_response.content)
                body = _strip_imports(body)
                name = _extract_name(body) or name

            if actual_pages > MAX_RESUME_PAGES:
                error_msg = (
                    "Resume exceeds hard page limit after compression retries. "
                    f"Hard limit: <= {MAX_RESUME_PAGES} page(s), actual: {actual_pages}."
                )
                report_id = await _save_failed_report(error_msg)
                return {
                    "status": "failed",
                    "error": error_msg,
                    "report_id": report_id,
                    "title": "Resume",
                    "content_type": "typst",
                }

            # ── Phase 4: SAVE ─────────────────────────────────────────────
            dispatch_custom_event(
                "report_progress",
                {"phase": "saving", "message": "Saving your resume"},
            )

            resume_title = f"{name} - Resume" if name != "Resume" else "Resume"

            metadata: dict[str, Any] = {
                "status": "ready",
                "word_count": len(typst_source.split()),
                "char_count": len(typst_source),
                "target_max_pages": validated_max_pages,
                "actual_page_count": actual_pages,
                "page_limit_enforced": True,
                "compression_attempts": compression_attempts,
                "target_page_met": target_page_met,
            }

            async with shielded_async_session() as write_session:
                report = Report(
                    title=resume_title,
                    content=typst_source,
                    content_type="typst",
                    report_metadata=metadata,
                    report_style="resume",
                    search_space_id=search_space_id,
                    thread_id=thread_id,
                    report_group_id=report_group_id,
                )
                write_session.add(report)
                await write_session.commit()
                await write_session.refresh(report)

                if not report.report_group_id:
                    report.report_group_id = report.id
                    await write_session.commit()

                saved_id = report.id

            logger.info(f"[generate_resume] Created resume {saved_id}: {resume_title}")

            return {
                "status": "ready",
                "report_id": saved_id,
                "title": resume_title,
                "content_type": "typst",
                "is_revision": bool(parent_content),
                "message": (
                    f"Resume generated successfully: {resume_title}"
                    if target_page_met
                    else (
                        f"Resume generated, but could not fit the target of <= {validated_max_pages} "
                        f"page(s). Final length: {actual_pages} page(s)."
                    )
                ),
            }

        except Exception as e:
            error_message = str(e)
            logger.exception(f"[generate_resume] Error: {error_message}")
            report_id = await _save_failed_report(error_message)
            return {
                "status": "failed",
                "error": error_message,
                "report_id": report_id,
                "title": "Resume",
                "content_type": "typst",
            }

    return generate_resume
