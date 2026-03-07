"""
Report generation tool for the SurfSense agent.

This module provides a factory function for creating the generate_report tool
that generates a structured Markdown report inline (no Celery). The LLM is
called within the tool, the result is saved to the database, and the tool
returns immediately with a ready status.

Uses short-lived database sessions to avoid holding connections during long
LLM calls (30-120+ seconds). Each DB operation (read config, save report)
opens and closes its own session, ensuring no connection is held idle during
the LLM API call.

Generation strategies:
  - Single-shot generation for all new reports
  - Section-level revision for targeted edits (preserves unchanged sections)
  - Full-document revision as fallback for global changes

Source strategies (how source content is collected):
  - "provided"      — Use only the supplied source_content (default, backward-compat)
  - "conversation"  — Same as "provided"; agent passes conversation summary
  - "kb_search"     — Tool searches knowledge base internally with targeted queries
  - "auto"          — Use source_content if sufficient, else search KB as fallback
"""

import asyncio
import json
import logging
import re
from typing import Any

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from app.db import Report, shielded_async_session
from app.services.connector_service import ConnectorService
from app.services.llm_service import get_document_summary_llm

logger = logging.getLogger(__name__)

# ─── Shared Formatting Rules ────────────────────────────────────────────────
# Reusable formatting instructions appended to section-level and review prompts.

_FORMATTING_RULES = """\
- IMPORTANT: Output raw Markdown directly. Do NOT wrap the entire output in a \
code fence (e.g. ```markdown, ````markdown, or any backtick fence). Individual \
code examples and diagrams inside the report should still use fenced code blocks, \
but the report itself must NOT be enclosed in one.
- Maintain proper Markdown formatting throughout.
- When including code examples, ALWAYS format them as proper fenced code blocks \
with the correct language identifier (e.g. ```java, ```python). Code inside code \
blocks MUST have proper line breaks and indentation — NEVER put multiple statements \
on a single line. Each statement, brace, and logical block must be on its own line \
with correct indentation.
- When including Mermaid diagrams, use ```mermaid fenced code blocks. Each Mermaid \
statement MUST be on its own line — NEVER use semicolons to join multiple statements \
on one line. For line breaks inside node labels, use <br> (NOT <br/>).
- When including mathematical formulas or equations, ALWAYS use LaTeX notation. \
NEVER use backtick code spans or Unicode symbols for math."""

# ─── Standard Report Footer ─────────────────────────────────────────────────
# Appended to every generated report after content generation.

_REPORT_FOOTER = "Powered by SurfSense AI."

# ─── Prompt: Single-Shot Report Generation ───────────────────────────────────

_REPORT_PROMPT = """You are an expert report writer. Generate a comprehensive Markdown report.

**Topic:** {topic}
**Report Style:** {report_style}
{user_instructions_section}
{previous_version_section}

**Source Content:**
{source_content}

---

{length_instruction}

Write a well-structured Markdown report with a # title, executive summary, organized sections, and conclusion. Cite facts from the source content. Be thorough and professional.

{formatting_rules}
"""

# ─── Prompt: Full-Document Revision (fallback when section-level fails) ──────

_REVISION_PROMPT = """You are an expert report editor. Apply ONLY the requested changes — do NOT rewrite from scratch.

**Topic:** {topic}
**Report Style:** {report_style}
**Modification Instructions:** {user_instructions_section}

**Source Content (use if relevant):**
{source_content}

---

**EXISTING REPORT:**

{previous_report_content}

---

{length_instruction}

Preserve all structure and content not affected by the modification.

{formatting_rules}
"""

# ─── Prompt: Section-Level Revision — Identify Affected Sections ─────────────

_IDENTIFY_SECTIONS_PROMPT = """You are analyzing a Markdown report to determine which sections need modification based on the user's request.

**User's Modification Request:** {user_instructions}

**Report Sections (indexed starting at 0):**
{sections_listing}

---

Determine which sections need to be modified, added, or removed to fulfill the user's request.

Return ONLY a JSON object with these fields:
- "modify": Array of section indices (0-based) that need content changes
- "add": Array of objects like {{"after_index": 2, "heading": "## New Section Title", "description": "What this section should cover"}} for new sections to insert
- "remove": Array of section indices to remove entirely (use sparingly)
- "reasoning": A brief explanation of your decisions

Guidelines:
- If the change is GLOBAL (e.g., "change the tone", "make the whole report shorter", "translate to Spanish"), include ALL section indices in "modify".
- If the change is TARGETED (e.g., "expand the budget section", "fix the conclusion"), include ONLY the affected section indices.
- For "add a section about X", use the "add" field with the appropriate insertion point.
- Prefer modifying over removing+adding when possible.

Return ONLY valid JSON, no markdown fences:
"""

# ─── Prompt: Section-Level Revision — Revise a Single Section ────────────────

_REVISE_SECTION_PROMPT = """Revise ONLY this section based on the instructions. If the instructions don't apply, return it UNCHANGED.

**Modification Instructions:** {user_instructions}

**Current Section:**
{section_content}

**Context (surrounding sections — for coherence only, do NOT output them):**
{context_sections}

**Source Content:**
{source_content}

---

Keep the same heading and heading level. Preserve content not affected by the modification.
{formatting_rules}
"""

# ─── Prompt: New Section Generation (for section-level add) ─────────────────

_NEW_SECTION_PROMPT = """You are an expert report writer. Write a new section to be inserted into an existing report.

**Report Topic:** {topic}
**Report Style:** {report_style}
**Section Heading:** {heading}
**Section Goal:** {description}
**User Instructions:** {user_instructions}

**Surrounding Context:**
{context_sections}

**Source Content:**
{source_content}

---

**Rules:**
1. Write ONLY this section, starting with the heading "{heading}".
2. Ensure the section flows naturally with the surrounding context.
3. Be comprehensive — cover the topic described above.
{formatting_rules}

Write the new section now:
"""


# ─── Utility Functions ──────────────────────────────────────────────────────


def _strip_wrapping_code_fences(text: str) -> str:
    """Remove wrapping code fences that LLMs often add around Markdown output.

    Handles patterns like:
        ```markdown\\n...content...\\n```
        ````markdown\\n...content...\\n````
        ```md\\n...content...\\n```
        ```\\n...content...\\n```
        ```json\\n...content...\\n```
    Supports 3 or more backticks (LLMs escalate when content has triple-backtick blocks).
    """
    stripped = text.strip()
    # Match opening fence with 3+ backticks and optional language tag
    m = re.match(r"^(`{3,})(?:markdown|md|json)?\s*\n", stripped)
    if m:
        fence = m.group(1)  # e.g. "```" or "````"
        if stripped.endswith(fence):
            stripped = stripped[m.end() :]  # remove opening fence
            stripped = stripped[: -len(fence)].rstrip()  # remove closing fence
    return stripped


def _extract_metadata(content: str) -> dict[str, Any]:
    """Extract metadata from generated Markdown content."""
    # Count section headings
    headings = re.findall(r"^(#{1,6})\s+(.+)$", content, re.MULTILINE)

    # Word count
    word_count = len(content.split())

    # Character count
    char_count = len(content)

    return {
        "status": "ready",
        "word_count": word_count,
        "char_count": char_count,
        "section_count": len(headings),
    }


def _parse_sections(content: str) -> list[dict[str, str]]:
    """Parse Markdown content into sections split by # and ## headings.

    Returns a list of dicts: [{"heading": "## Title", "body": "content..."}, ...]
    Content before the first heading is captured with heading="".
    ### and deeper headings are kept inside their parent ## section's body.
    """
    lines = content.split("\n")
    sections: list[dict[str, str]] = []
    current_heading = ""
    current_body_lines: list[str] = []
    in_code_block = False

    for line in lines:
        # Track code blocks to avoid matching headings inside them
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block

        # Only split on # or ## headings (not ### or deeper) and only outside code blocks
        is_section_heading = (
            not in_code_block
            and re.match(r"^#{1,2}\s+", line)
            and not re.match(r"^#{3,}\s+", line)
        )

        if is_section_heading:
            # Save previous section
            if current_heading or current_body_lines:
                sections.append(
                    {
                        "heading": current_heading,
                        "body": "\n".join(current_body_lines).strip(),
                    }
                )
            current_heading = line.strip()
            current_body_lines = []
        else:
            current_body_lines.append(line)

    # Save last section
    if current_heading or current_body_lines:
        sections.append(
            {
                "heading": current_heading,
                "body": "\n".join(current_body_lines).strip(),
            }
        )

    return sections


def _stitch_sections(sections: list[dict[str, str]]) -> str:
    """Stitch parsed sections back into a single Markdown string."""
    parts = []
    for section in sections:
        if section["heading"]:
            parts.append(section["heading"])
        if section["body"]:
            parts.append(section["body"])
    return "\n\n".join(parts)


# ─── Async Generation Helpers ───────────────────────────────────────────────


async def _revise_with_sections(
    llm: Any,
    parent_content: str,
    user_instructions: str,
    source_content: str,
    topic: str,
    report_style: str,
) -> str | None:
    """Section-level revision: identify affected sections and revise only those.

    Unchanged sections are kept byte-for-byte identical.
    Returns the revised content, or None to trigger full-document revision fallback.
    """
    # Parse report into sections
    sections = _parse_sections(parent_content)
    if len(sections) < 2:
        logger.info(
            "[generate_report] Too few sections for section-level revision, using full revision"
        )
        return None

    # Build a sections listing for the LLM
    sections_listing = ""
    for i, sec in enumerate(sections):
        heading = sec["heading"] or "(preamble — content before first heading)"
        body_preview = (
            sec["body"][:200] + "..." if len(sec["body"]) > 200 else sec["body"]
        )
        sections_listing += f"\n[{i}] {heading}\n    Preview: {body_preview}\n"

    # Step 1: Ask LLM which sections need modification
    identify_prompt = _IDENTIFY_SECTIONS_PROMPT.format(
        user_instructions=user_instructions,
        sections_listing=sections_listing,
    )

    try:
        response = await llm.ainvoke([HumanMessage(content=identify_prompt)])
        raw = response.content
        if not raw or not isinstance(raw, str):
            return None

        raw = _strip_wrapping_code_fences(raw).strip()
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if json_match:
            raw = json_match.group(0)

        plan = json.loads(raw)
        modify_indices: list[int] = plan.get("modify", [])
        add_sections: list[dict[str, Any]] = plan.get("add", [])
        remove_indices: list[int] = plan.get("remove", [])
        reasoning = plan.get("reasoning", "")

        logger.info(
            f"[generate_report] Section-level revision plan: "
            f"modify={modify_indices}, add={len(add_sections)}, "
            f"remove={remove_indices}, reasoning={reasoning}"
        )
    except Exception:
        logger.warning(
            "[generate_report] Failed to identify sections for revision, "
            "falling back to full revision",
            exc_info=True,
        )
        return None

    # If ALL sections need modification, full revision is more efficient and coherent
    if len(modify_indices) >= len(sections):
        logger.info(
            "[generate_report] All sections need modification, deferring to full revision"
        )
        return None

    # Compute total operations for progress tracking
    total_ops = len(modify_indices) + len(add_sections)
    current_op = 0

    # Emit plan summary
    parts = []
    if modify_indices:
        parts.append(
            f"modifying {len(modify_indices)} section{'s' if len(modify_indices) > 1 else ''}"
        )
    if add_sections:
        parts.append(
            f"adding {len(add_sections)} new section{'s' if len(add_sections) > 1 else ''}"
        )
    if remove_indices:
        parts.append(
            f"removing {len(remove_indices)} section{'s' if len(remove_indices) > 1 else ''}"
        )
    plan_summary = ", ".join(parts) if parts else "no changes needed"

    dispatch_custom_event(
        "report_progress",
        {
            "phase": "revision_plan",
            "message": plan_summary.capitalize(),
            "modify_count": len(modify_indices),
            "add_count": len(add_sections),
            "remove_count": len(remove_indices),
            "total_ops": total_ops,
        },
    )

    # Step 2: Revise only the affected sections
    revised_sections = list(sections)  # shallow copy — unmodified sections stay as-is

    for idx in modify_indices:
        if idx < 0 or idx >= len(sections):
            continue

        current_op += 1
        sec = sections[idx]

        # Extract plain section name (strip markdown heading markers)
        section_name = (
            re.sub(r"^#+\s*", "", sec["heading"]).strip()
            if sec["heading"]
            else "Preamble"
        )
        dispatch_custom_event(
            "report_progress",
            {
                "phase": "revising_section",
                "message": f"Revising: {section_name} ({current_op}/{total_ops})...",
            },
        )

        section_content = (
            f"{sec['heading']}\n\n{sec['body']}" if sec["heading"] else sec["body"]
        )

        # Build context from surrounding sections
        context_parts = []
        if idx > 0:
            prev = sections[idx - 1]
            prev_preview = prev["body"][:300] + (
                "..." if len(prev["body"]) > 300 else ""
            )
            context_parts.append(
                f"**Previous section:** {prev['heading']}\n{prev_preview}"
            )
        if idx < len(sections) - 1:
            nxt = sections[idx + 1]
            nxt_preview = nxt["body"][:300] + ("..." if len(nxt["body"]) > 300 else "")
            context_parts.append(f"**Next section:** {nxt['heading']}\n{nxt_preview}")
        context = (
            "\n\n".join(context_parts) if context_parts else "(No surrounding sections)"
        )

        revise_prompt = _REVISE_SECTION_PROMPT.format(
            user_instructions=user_instructions,
            section_content=section_content,
            context_sections=context,
            source_content=source_content[:40000],
            formatting_rules=_FORMATTING_RULES,
        )

        resp = await llm.ainvoke([HumanMessage(content=revise_prompt)])
        revised_text = resp.content
        if revised_text and isinstance(revised_text, str):
            revised_text = _strip_wrapping_code_fences(revised_text).strip()
            # Parse the LLM output back into heading + body
            revised_parsed = _parse_sections(revised_text)
            if revised_parsed:
                revised_sections[idx] = revised_parsed[0]
            else:
                revised_sections[idx] = {
                    "heading": sec["heading"],
                    "body": revised_text,
                }

        logger.info(f"[generate_report] Revised section [{idx}]: {sec['heading']}")

    # Step 3: Handle new section additions (insert in reverse order to preserve indices)
    for add_info in sorted(
        add_sections,
        key=lambda x: x.get("after_index", len(revised_sections) - 1),
        reverse=True,
    ):
        current_op += 1
        after_idx = add_info.get("after_index", len(revised_sections) - 1)
        heading = add_info.get("heading", "## New Section")
        description = add_info.get("description", "")

        # Extract plain section name for progress display
        plain_heading = re.sub(r"^#+\s*", "", heading).strip()
        dispatch_custom_event(
            "report_progress",
            {
                "phase": "adding_section",
                "message": f"Adding: {plain_heading} ({current_op}/{total_ops})...",
            },
        )

        # Build context from the surrounding sections at the insertion point
        ctx_parts = []
        if 0 <= after_idx < len(revised_sections):
            before_sec = revised_sections[after_idx]
            ctx_parts.append(
                f"**Section before:** {before_sec['heading']}\n{before_sec['body'][:300]}"
            )
        insert_idx = min(after_idx + 1, len(revised_sections))
        if insert_idx < len(revised_sections):
            after_sec = revised_sections[insert_idx]
            ctx_parts.append(
                f"**Section after:** {after_sec['heading']}\n{after_sec['body'][:300]}"
            )

        new_prompt = _NEW_SECTION_PROMPT.format(
            topic=topic,
            report_style=report_style,
            heading=heading,
            description=description,
            user_instructions=user_instructions,
            context_sections="\n\n".join(ctx_parts) if ctx_parts else "(None)",
            source_content=source_content[:30000],
            formatting_rules=_FORMATTING_RULES,
        )

        resp = await llm.ainvoke([HumanMessage(content=new_prompt)])
        new_content = resp.content
        if new_content and isinstance(new_content, str):
            new_content = _strip_wrapping_code_fences(new_content).strip()
            new_parsed = _parse_sections(new_content)
            if new_parsed:
                revised_sections.insert(insert_idx, new_parsed[0])
            else:
                revised_sections.insert(
                    insert_idx,
                    {
                        "heading": heading,
                        "body": new_content,
                    },
                )

        logger.info(
            f"[generate_report] Added new section after [{after_idx}]: {heading}"
        )

    # Step 4: Handle removals (reverse order to preserve indices)
    for idx in sorted(remove_indices, reverse=True):
        if 0 <= idx < len(revised_sections):
            logger.info(
                f"[generate_report] Removed section [{idx}]: "
                f"{revised_sections[idx]['heading']}"
            )
            revised_sections.pop(idx)

    return _stitch_sections(revised_sections)


# ─── Tool Factory ───────────────────────────────────────────────────────────


def create_generate_report_tool(
    search_space_id: int,
    thread_id: int | None = None,
    connector_service: ConnectorService | None = None,
    available_connectors: list[str] | None = None,
    available_document_types: list[str] | None = None,
):
    """
    Factory function to create the generate_report tool with injected dependencies.

    The tool generates a Markdown report inline using the search space's
    document summary LLM, saves it to the database, and returns immediately.

    Uses short-lived database sessions for each DB operation so no connection
    is held during the long LLM API call.

    Generation strategies:
      - New reports: single-shot generation (1 LLM call)
      - Revisions (targeted edits): section-level (unchanged sections preserved)
      - Revisions (global changes): full-document revision fallback

    Source strategies:
      - "provided"/"conversation": use only the supplied source_content
      - "kb_search": search the knowledge base internally using targeted queries
      - "auto": use source_content if sufficient, otherwise fall back to KB search

    Args:
        search_space_id: The user's search space ID
        thread_id: The chat thread ID for associating the report
        connector_service: Optional connector service for internal KB search.
            When provided, the tool can search the knowledge base without the
            agent having to call search_knowledge_base separately.
        available_connectors: Optional list of connector types available in the
            search space (used to scope internal KB searches).

    Returns:
        A configured tool function for generating reports
    """

    @tool
    async def generate_report(
        topic: str,
        source_content: str = "",
        source_strategy: str = "provided",
        search_queries: list[str] | None = None,
        report_style: str = "detailed",
        user_instructions: str | None = None,
        parent_report_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Generate a structured Markdown report artifact from provided content.

        Use this tool when the user asks to create, generate, write, produce,
        draft, or summarize into a report-style deliverable.

        Trigger classes include:
        - Direct trigger words WITH creation/modification verb: report,
          document, memo, letter, template, article, guide, blog post,
          one-pager, briefing, comprehensive guide.
        - Creation-intent phrases: "write a report", "generate a document",
          "draft a summary", "create an executive summary".
        - Modification-intent phrases: "revise the report", "update the
          report", "make it shorter", "add a section about X", "expand the
          budget section", "rewrite in formal tone".

        IMPORTANT — what does NOT count as "asking for a report":
        - Questions or discussion about a report or its topic are NOT report
          requests. Respond to these conversationally in chat.
          Examples: "What other examples to put there?", "What else could be
          added?", "Can you explain section 2?", "Is the data accurate?",
          "What's missing?", "How could this be improved?", "What other
          topics are related?"
        - Quick summary requests, explanations, or follow-up questions.
        - The test: Does the message contain a creation/modification VERB
          (write, create, generate, draft, add, revise, update, expand,
          rewrite, make) directed at producing a deliverable? If no verb
          → answer in chat.

        FORMAT/EXPORT RULE:
        - Always generate the report content in Markdown.
        - If the user requests DOCX/Word/PDF or another file format, export
          from the generated Markdown report.

        SOURCE STRATEGY (how to collect source material):
        - source_strategy="conversation" — The conversation already has
          enough context (prior Q&A, pasted text, uploaded files, scraped
          webpages). Pass a thorough summary as source_content.
          NEVER call search_knowledge_base separately first.
        - source_strategy="kb_search" — Search the knowledge base
          internally. Provide 1-5 targeted search_queries. The tool
          handles searching — do NOT call search_knowledge_base first.
        - source_strategy="provided" — Use only what is in source_content
          (default, backward-compatible).
        - source_strategy="auto" — Use source_content if it has enough
          material; otherwise fall back to internal KB search using
          search_queries.

        CONVERSATION REUSE (HIGH PRIORITY):
        - If the user has been asking questions in this chat and the
          conversation contains substantive answers/discussion on the
          topic, prefer source_strategy="conversation" with a thorough
          summary of the full chat history as source_content.
        - The user's prior questions and your answers ARE the source
          material. Do NOT redundantly search the knowledge base for
          information that is already in the chat.

        VERSIONING — parent_report_id:
        - Set parent_report_id when the user wants to MODIFY, REVISE,
          IMPROVE, UPDATE, EXPAND, or ADD CONTENT TO an existing report
          that was already generated in this conversation.
        - This includes both explicit AND implicit modification requests.
          If the user references the existing report using words like "it",
          "this", "here", "the report", or clearly refers to a previously
          generated report, treat it as a revision request.
        - The value must be the report_id from a previous generate_report
          result in this same conversation.
        - Do NOT set parent_report_id when:
          * The user asks for a report on a completely NEW/DIFFERENT topic
          * The user says "generate another report" (new report, not revision)
          * There is no prior report to reference

        Examples of when to SET parent_report_id:
          User: "Make that report shorter" → parent_report_id = <previous report_id>
          User: "Add a cost analysis section to the report" → parent_report_id = <previous report_id>
          User: "Rewrite the report in a more formal tone" → parent_report_id = <previous report_id>
          User: "I want more details about pricing in here" → parent_report_id = <previous report_id>
          User: "Include more examples" → parent_report_id = <previous report_id>
          User: "Can you also cover nutrition in this?" → parent_report_id = <previous report_id>
          User: "Make it more detailed" → parent_report_id = <previous report_id>
          User: "Not bad, but expand on the budget section" → parent_report_id = <previous report_id>
          User: "Also mention the competitor landscape" → parent_report_id = <previous report_id>

        Examples of when to LEAVE parent_report_id as None:
          User: "Generate a report on climate change" → None (new topic)
          User: "Write me a report about the budget" → None (new topic)
          User: "Create another report, this time about marketing" → None
          User: "Now write one about travel trends in Europe" → None (new topic)

        Args:
            topic: Short title for the report (max ~8 words).
            source_content: Text to base the report on. Can be empty when
                using source_strategy="kb_search".
            source_strategy: How to collect source material. One of
                "provided", "conversation", "kb_search", or "auto".
            search_queries: When source_strategy is "kb_search" or "auto",
                provide 1-5 targeted search queries for the knowledge base.
                These should be specific, not just the topic repeated.
            report_style: "detailed", "deep_research", or "brief".
            user_instructions: Optional focus or modification instructions.
                When revising (parent_report_id set), describe WHAT TO CHANGE.
            parent_report_id: ID of a previous report to revise (creates new
                version in the same version group).

        Returns:
            Dict with status, report_id, title, word_count, and message.
        """
        # Initialize version tracking variables (used by _save_failed_report closure)
        parent_report_content: str | None = None
        report_group_id: int | None = None

        async def _save_failed_report(error_msg: str) -> int | None:
            """Persist a failed report row using a short-lived session."""
            try:
                async with shielded_async_session() as session:
                    failed_report = Report(
                        title=topic,
                        content=None,
                        report_metadata={
                            "status": "failed",
                            "error_message": error_msg,
                        },
                        report_style=report_style,
                        search_space_id=search_space_id,
                        thread_id=thread_id,
                        report_group_id=report_group_id,
                    )
                    session.add(failed_report)
                    await session.commit()
                    await session.refresh(failed_report)
                    # If this is a new group (v1 failed), set group to self
                    if not failed_report.report_group_id:
                        failed_report.report_group_id = failed_report.id
                        await session.commit()
                    logger.info(
                        f"[generate_report] Saved failed report {failed_report.id}: {error_msg}"
                    )
                    return failed_report.id
            except Exception:
                logger.exception(
                    "[generate_report] Could not persist failed report row"
                )
                return None

        try:
            # ── Phase 1: READ (short-lived session) ──────────────────────
            # Fetch parent report and LLM config, then close the session
            # so no DB connection is held during the long LLM call.
            async with shielded_async_session() as read_session:
                if parent_report_id:
                    parent_report = await read_session.get(Report, parent_report_id)
                    if parent_report:
                        report_group_id = parent_report.report_group_id
                        parent_report_content = parent_report.content
                        logger.info(
                            f"[generate_report] Creating new version from parent {parent_report_id} "
                            f"(group {report_group_id})"
                        )
                    else:
                        logger.warning(
                            f"[generate_report] parent_report_id={parent_report_id} not found, "
                            "creating standalone report"
                        )

                llm = await get_document_summary_llm(read_session, search_space_id)
            # read_session closed — connection returned to pool

            if not llm:
                error_msg = (
                    "No LLM configured. Please configure a language model in Settings."
                )
                report_id = await _save_failed_report(error_msg)
                return {
                    "status": "failed",
                    "error": error_msg,
                    "report_id": report_id,
                    "title": topic,
                }

            # Build the user instructions string
            user_instructions_section = ""
            if user_instructions:
                user_instructions_section = (
                    f"**Additional Instructions:** {user_instructions}"
                )

            # ── Phase 1b: SOURCE COLLECTION (smart KB search) ────────────
            # Decide whether to augment source_content with KB search results.
            effective_source = source_content or ""

            strategy = (source_strategy or "provided").lower().strip()

            needs_kb_search = False
            if strategy == "kb_search":
                needs_kb_search = True
            elif strategy == "auto":
                # Heuristic: if source_content has fewer than 200 words,
                # it's likely insufficient — augment with KB search.
                word_count_estimate = len(effective_source.split())
                if word_count_estimate < 200:
                    needs_kb_search = True
                    logger.info(
                        f"[generate_report] auto strategy: source has ~{word_count_estimate} words, "
                        "triggering KB search"
                    )
            # "provided" and "conversation" → use source_content as-is

            if needs_kb_search and connector_service and search_queries:
                query_count = min(len(search_queries), 5)
                dispatch_custom_event(
                    "report_progress",
                    {
                        "phase": "kb_search",
                        "message": f"Searching knowledge base ({query_count} queries)...",
                    },
                )
                logger.info(
                    f"[generate_report] Running internal KB search with "
                    f"{query_count} queries: {search_queries[:5]}"
                )
                try:
                    from .knowledge_base import search_knowledge_base_async

                    # Run all queries in parallel, each with its own session
                    async def _run_single_query(q: str) -> str:
                        async with shielded_async_session() as kb_session:
                            kb_connector_svc = ConnectorService(
                                kb_session, search_space_id
                            )
                            return await search_knowledge_base_async(
                                query=q,
                                search_space_id=search_space_id,
                                db_session=kb_session,
                                connector_service=kb_connector_svc,
                                top_k=10,
                                available_connectors=available_connectors,
                                available_document_types=available_document_types,
                            )

                    kb_results = await asyncio.gather(
                        *[_run_single_query(q) for q in search_queries[:5]]
                    )

                    # Merge non-empty results into source_content
                    kb_text_parts = [r for r in kb_results if r and r.strip()]
                    if kb_text_parts:
                        kb_combined = "\n\n---\n\n".join(kb_text_parts)
                        if effective_source.strip():
                            effective_source = (
                                effective_source
                                + "\n\n--- Knowledge Base Search Results ---\n\n"
                                + kb_combined
                            )
                        else:
                            effective_source = kb_combined

                        # Count docs found (rough: count <document> tags)
                        doc_count = kb_combined.count("<document>")
                        dispatch_custom_event(
                            "report_progress",
                            {
                                "phase": "kb_search_done",
                                "message": f"Found {doc_count} relevant documents"
                                if doc_count
                                else f"Found results from {len(kb_text_parts)} queries",
                            },
                        )
                        logger.info(
                            f"[generate_report] KB search added ~{len(kb_combined)} chars "
                            f"from {len(kb_text_parts)} queries"
                        )
                    else:
                        dispatch_custom_event(
                            "report_progress",
                            {
                                "phase": "kb_search_done",
                                "message": "No results found in knowledge base",
                            },
                        )
                        logger.info("[generate_report] KB search returned no results")

                except Exception as e:
                    logger.warning(
                        f"[generate_report] Internal KB search failed: {e}. "
                        "Proceeding with existing source_content."
                    )
            elif needs_kb_search and not connector_service:
                logger.warning(
                    "[generate_report] KB search requested but connector_service "
                    "not available. Using source_content as-is."
                )
            elif needs_kb_search and not search_queries:
                logger.warning(
                    "[generate_report] KB search requested but no search_queries "
                    "provided. Using source_content as-is."
                )

            capped_source = effective_source[:100000]  # Cap source content

            # Length constraint — only when user explicitly asks for brevity
            length_instruction = ""
            if report_style == "brief":
                length_instruction = (
                    "**LENGTH CONSTRAINT (MANDATORY):** The user wants a SHORT report. "
                    "Keep it concise — aim for ~400 words (~1 page) unless a different "
                    "length is specified in the Additional Instructions above. "
                    "Prioritize brevity over thoroughness. Do NOT write a long report."
                )

            # ── Phase 2: LLM GENERATION (no DB connection held) ──────────

            report_content: str | None = None

            if parent_report_content:
                # ─── REVISION MODE ───────────────────────────────────────
                # Strategy: Try section-level revision first (preserves
                # unchanged sections byte-for-byte). Falls back to full-
                # document revision if section identification fails or if
                # all sections need changes.
                dispatch_custom_event(
                    "report_progress",
                    {
                        "phase": "revision_start",
                        "message": "Analyzing sections to modify...",
                    },
                )
                logger.info(
                    "[generate_report] Revision mode — attempting section-level revision"
                )
                report_content = await _revise_with_sections(
                    llm=llm,
                    parent_content=parent_report_content,
                    user_instructions=user_instructions
                    or "Improve and refine the report.",
                    source_content=capped_source,
                    topic=topic,
                    report_style=report_style,
                )

                if report_content is None:
                    # Fallback: full-document revision
                    dispatch_custom_event(
                        "report_progress",
                        {"phase": "writing", "message": "Rewriting your full report"},
                    )
                    logger.info(
                        "[generate_report] Section-level revision deferred, "
                        "using full-document revision"
                    )
                    prompt = _REVISION_PROMPT.format(
                        topic=topic,
                        report_style=report_style,
                        user_instructions_section=user_instructions_section
                        or "Improve and refine the report.",
                        source_content=capped_source,
                        previous_report_content=parent_report_content,
                        length_instruction=length_instruction,
                        formatting_rules=_FORMATTING_RULES,
                    )
                    response = await llm.ainvoke([HumanMessage(content=prompt)])
                    report_content = response.content

            else:
                # ─── NEW REPORT MODE ─────────────────────────────────────
                # Single-shot generation: one LLM call produces the full
                # report. Fast, globally coherent, and cost-efficient.
                dispatch_custom_event(
                    "report_progress",
                    {"phase": "writing", "message": "Writing your report"},
                )
                logger.info(
                    "[generate_report] New report — using single-shot generation"
                )
                prompt = _REPORT_PROMPT.format(
                    topic=topic,
                    report_style=report_style,
                    user_instructions_section=user_instructions_section,
                    previous_version_section="",
                    source_content=capped_source,
                    length_instruction=length_instruction,
                    formatting_rules=_FORMATTING_RULES,
                )
                response = await llm.ainvoke([HumanMessage(content=prompt)])
                report_content = response.content

            # ── Validate LLM output ──────────────────────────────────────

            if not report_content or not isinstance(report_content, str):
                error_msg = "LLM returned empty or invalid content"
                report_id = await _save_failed_report(error_msg)
                return {
                    "status": "failed",
                    "error": error_msg,
                    "report_id": report_id,
                    "title": topic,
                }

            # LLMs often wrap output in ```markdown ... ``` fences — strip them
            report_content = _strip_wrapping_code_fences(report_content)

            if not report_content:
                error_msg = "LLM returned empty or invalid content"
                report_id = await _save_failed_report(error_msg)
                return {
                    "status": "failed",
                    "error": error_msg,
                    "report_id": report_id,
                    "title": topic,
                }

            # Strip any existing footer(s) carried over from parent version(s)
            while report_content.rstrip().endswith(_REPORT_FOOTER):
                idx = report_content.rstrip().rfind(_REPORT_FOOTER)
                report_content = report_content[:idx].rstrip()
                if report_content.rstrip().endswith("---"):
                    report_content = report_content.rstrip()[:-3].rstrip()

            # Append exactly one standard disclaimer
            report_content += "\n\n---\n\n" + _REPORT_FOOTER

            # Extract metadata (includes "status": "ready")
            metadata = _extract_metadata(report_content)

            # ── Phase 3: WRITE (short-lived session) ─────────────────────
            # Save the report to the database, then close the session.
            async with shielded_async_session() as write_session:
                report = Report(
                    title=topic,
                    content=report_content,
                    report_metadata=metadata,
                    report_style=report_style,
                    search_space_id=search_space_id,
                    thread_id=thread_id,
                    report_group_id=report_group_id,
                )
                write_session.add(report)
                await write_session.commit()
                await write_session.refresh(report)

                # If this is a brand-new report (v1), set report_group_id = own id
                if not report.report_group_id:
                    report.report_group_id = report.id
                    await write_session.commit()

                saved_report_id = report.id
                saved_group_id = report.report_group_id
            # write_session closed — connection returned to pool

            logger.info(
                f"[generate_report] Created report {saved_report_id} "
                f"(group={saved_group_id}): "
                f"{metadata.get('word_count', 0)} words, "
                f"{metadata.get('section_count', 0)} sections"
            )

            return {
                "status": "ready",
                "report_id": saved_report_id,
                "title": topic,
                "word_count": metadata.get("word_count", 0),
                "is_revision": bool(parent_report_content),
                "message": f"Report generated successfully: {topic}",
            }

        except Exception as e:
            error_message = str(e)
            logger.exception(f"[generate_report] Error: {error_message}")
            report_id = await _save_failed_report(error_message)

            return {
                "status": "failed",
                "error": error_message,
                "report_id": report_id,
                "title": topic,
            }

    return generate_report
