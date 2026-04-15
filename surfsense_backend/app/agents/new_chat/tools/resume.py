"""
Resume generation tool for the SurfSense agent.

Generates a structured resume as Typst source code using the rendercv package.
The LLM outputs Typst markup which is validated via typst.compile() before
persisting.  The compiled PDF is served on-demand by the preview endpoint.

Uses the same short-lived session pattern as generate_report so no DB
connection is held during the long LLM call.
"""

import logging
import re
from typing import Any

import typst
from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from app.db import Report, shielded_async_session
from app.services.llm_service import get_document_summary_llm

logger = logging.getLogger(__name__)

# ─── Typst / rendercv Reference ──────────────────────────────────────────────
# Embedded in the generation prompt so the LLM knows the exact API.

_RENDERCV_REFERENCE = """\
You MUST output valid Typst source code using the rendercv package.
The file MUST start with the import and show rule below.

```typst
#import "@preview/rendercv:0.3.0": *

#show: rendercv.with(
  name: "Full Name",
  section-titles-type: "with_partial_line",
)
```

Available components (use ONLY these):

= Full Name                              // Top-level heading — the person's name
#headline([Job Title or Tagline])        // Subtitle below the name
#connections(                            // Contact info row
  [City, Country],
  [#link("mailto:email@example.com")[email\\@example.com]],
  [#link("https://github.com/user")[github.com/user]],
  [#link("https://linkedin.com/in/user")[linkedin.com/in/user]],
)

== Section Title                         // Section heading (Experience, Education, Skills, etc.)

#regular-entry(                          // Work experience, projects, publications
  [*Role/Title*, Company Name -- Location],
  [Start -- End],
  main-column-second-row: [
    - Bullet point achievement
    - Another achievement
  ],
)

#education-entry(                        // Education
  [*Institution*, Degree in Field -- Location],
  [Start -- End],
  main-column-second-row: [
    - GPA, honours, relevant coursework
  ],
)

#summary([Short paragraph summary])     // Optional summary/objective
#content-area([Free-form content])       // Freeform text block

RULES:
- Output ONLY valid Typst code. No explanatory text before or after.
- Do NOT wrap output in ```typst code fences.
- Escape @ symbols inside link labels with a backslash: email\\@example.com
- Every section MUST use == heading.
- Use #regular-entry() for experience, projects, publications, certifications.
- Use #education-entry() for education.
- For skills, use plain bold + text: *Languages:* Python, TypeScript
- Keep content professional, concise, and achievement-oriented.
- Use action verbs for bullet points (Led, Built, Designed, Reduced, etc.).
"""

# ─── Prompts ─────────────────────────────────────────────────────────────────

_RESUME_PROMPT = """\
You are an expert resume writer. Generate a professional resume as Typst source code.

{rendercv_reference}

**User Information:**
{user_info}

{user_instructions_section}

Generate the complete Typst source file now:
"""

_REVISION_PROMPT = """\
You are an expert resume editor. Modify the existing resume according to the instructions.
Apply ONLY the requested changes — do NOT rewrite sections that are not affected.

{rendercv_reference}

**Modification Instructions:** {user_instructions}

**EXISTING RESUME (Typst source):**

{previous_content}

---

Output the complete, updated Typst source file with the changes applied:
"""

_FIX_COMPILE_PROMPT = """\
The Typst source you generated failed to compile. Fix the error while preserving all content.

**Compilation Error:**
{error}

**Your Previous Output:**
{source}

{rendercv_reference}

Output the corrected Typst source file:
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


# ─── Tool Factory ───────────────────────────────────────────────────────────


def create_generate_resume_tool(
    search_space_id: int,
    thread_id: int | None = None,
):
    """
    Factory function to create the generate_resume tool.

    Generates a Typst-based resume, validates it via compilation,
    and stores the source in the Report table with content_type='typst'.
    """

    @tool
    async def generate_resume(
        user_info: str,
        user_instructions: str | None = None,
        parent_report_id: int | None = None,
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

        Returns:
            Dict with status, report_id, title, and content_type.
        """
        report_group_id: int | None = None
        parent_content: str | None = None

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
                logger.exception("[generate_resume] Could not persist failed report row")
                return None

        try:
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
                error_msg = "No LLM configured. Please configure a language model in Settings."
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
                prompt = _REVISION_PROMPT.format(
                    rendercv_reference=_RENDERCV_REFERENCE,
                    user_instructions=user_instructions or "Improve and refine the resume.",
                    previous_content=parent_content,
                )
            else:
                dispatch_custom_event(
                    "report_progress",
                    {"phase": "writing", "message": "Building your resume"},
                )
                prompt = _RESUME_PROMPT.format(
                    rendercv_reference=_RENDERCV_REFERENCE,
                    user_info=user_info,
                    user_instructions_section=user_instructions_section,
                )

            response = await llm.ainvoke([HumanMessage(content=prompt)])
            typst_source = response.content

            if not typst_source or not isinstance(typst_source, str):
                error_msg = "LLM returned empty or invalid content"
                report_id = await _save_failed_report(error_msg)
                return {
                    "status": "failed",
                    "error": error_msg,
                    "report_id": report_id,
                    "title": "Resume",
                    "content_type": "typst",
                }

            typst_source = _strip_typst_fences(typst_source)

            # ── Phase 3: COMPILE-VALIDATE-RETRY ───────────────────────────
            # Attempt 1
            dispatch_custom_event(
                "report_progress",
                {"phase": "compiling", "message": "Compiling resume..."},
            )

            compile_error: str | None = None
            for attempt in range(2):
                try:
                    _compile_typst(typst_source)
                    compile_error = None
                    break
                except Exception as e:
                    compile_error = str(e)
                    logger.warning(
                        f"[generate_resume] Compile attempt {attempt + 1} failed: {compile_error}"
                    )

                    if attempt == 0:
                        dispatch_custom_event(
                            "report_progress",
                            {"phase": "fixing", "message": "Fixing compilation issue..."},
                        )
                        fix_prompt = _FIX_COMPILE_PROMPT.format(
                            error=compile_error,
                            source=typst_source,
                            rendercv_reference=_RENDERCV_REFERENCE,
                        )
                        fix_response = await llm.ainvoke(
                            [HumanMessage(content=fix_prompt)]
                        )
                        if fix_response.content and isinstance(fix_response.content, str):
                            typst_source = _strip_typst_fences(fix_response.content)

            if compile_error:
                error_msg = f"Typst compilation failed after 2 attempts: {compile_error}"
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

            # Extract a title from the Typst source (the = heading is the person's name)
            title_match = re.search(r"^=\s+(.+)$", typst_source, re.MULTILINE)
            name = title_match.group(1).strip() if title_match else None
            resume_title = f"{name} - Resume" if name else "Resume"

            metadata: dict[str, Any] = {
                "status": "ready",
                "word_count": len(typst_source.split()),
                "char_count": len(typst_source),
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
                "message": f"Resume generated successfully: {resume_title}",
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
