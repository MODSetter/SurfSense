"""
Report generation tool for the SurfSense agent.

This module provides a factory function for creating the generate_report tool
that generates a structured Markdown report inline (no Celery). The LLM is
called within the tool, the result is saved to the database, and the tool
returns immediately with a ready status.

This follows the same inline pattern as generate_image and display_image,
NOT the Celery-based podcast pattern.
"""

import logging
import re
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Report
from app.services.llm_service import get_document_summary_llm

logger = logging.getLogger(__name__)

# Prompt template for report generation
_REPORT_PROMPT = """You are an expert report writer. Generate a well-structured, comprehensive Markdown report based on the provided information.

**Topic:** {topic}

**Report Style:** {report_style}

{user_instructions_section}

**Source Content:**
{source_content}

---

**Instructions:**
1. Write the report in well-formatted Markdown.
2. Include a clear title (as a level-1 heading), an executive summary, and logically organized sections.
3. Use headings (##, ###), bullet points, numbered lists, bold/italic text, and tables where appropriate.
4. Cite specific facts, figures, and findings from the source content.
5. Be thorough and comprehensive — include all relevant information from the source content.
6. End with a conclusion or key takeaways section.
7. The report should be professional and ready to export.

Write the report now:
"""


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


def create_generate_report_tool(
    search_space_id: int,
    db_session: AsyncSession,
    thread_id: int | None = None,
):
    """
    Factory function to create the generate_report tool with injected dependencies.

    The tool generates a Markdown report inline using the search space's
    document summary LLM, saves it to the database, and returns immediately.

    Args:
        search_space_id: The user's search space ID
        db_session: Database session for creating the report record
        thread_id: The chat thread ID for associating the report

    Returns:
        A configured tool function for generating reports
    """

    @tool
    async def generate_report(
        topic: str,
        source_content: str,
        report_style: str = "detailed",
        user_instructions: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate a structured Markdown report from provided content.

        Use this tool when the user asks to create, generate, or write a report.
        Common triggers include phrases like:
        - "Generate a report about this"
        - "Write a report from this conversation"
        - "Create a detailed report about..."
        - "Make a research report on..."
        - "Summarize this into a report"

        Args:
            topic: A short, concise title for the report (maximum 8 words). Keep it brief and descriptive — e.g. "AI in Healthcare Analysis: A Comprehensive Report" instead of "Comprehensive Analysis of Artificial Intelligence Applications in Modern Healthcare Systems".
            source_content: The text content to base the report on. This MUST be comprehensive and include:
                * If discussing the current conversation: a detailed summary of the FULL chat history
                * If based on knowledge base search: the key findings and insights from search results
                * You can combine both: conversation context + search results for richer reports
                * The more detailed the source_content, the better the report quality
            report_style: Style of the report. Options: "detailed", "executive_summary", "deep_research", "brief". Default: "detailed"
            user_instructions: Optional specific instructions for the report (e.g., "focus on financial impacts", "include recommendations")

        Returns:
            A dictionary containing:
            - status: "ready" or "failed"
            - report_id: The report ID
            - title: The report title
            - word_count: Number of words in the report
            - message: Status message (or "error" field if failed)
        """
        async def _save_failed_report(error_msg: str) -> int | None:
            """Persist a failed report row so the error is visible later."""
            try:
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
                )
                db_session.add(failed_report)
                await db_session.commit()
                await db_session.refresh(failed_report)
                logger.info(
                    f"[generate_report] Saved failed report {failed_report.id}: {error_msg}"
                )
                return failed_report.id
            except Exception:
                logger.exception("[generate_report] Could not persist failed report row")
                return None

        try:
            # Get the LLM instance for this search space
            llm = await get_document_summary_llm(db_session, search_space_id)
            if not llm:
                error_msg = "No LLM configured. Please configure a language model in Settings."
                report_id = await _save_failed_report(error_msg)
                return {
                    "status": "failed",
                    "error": error_msg,
                    "report_id": report_id,
                    "title": topic,
                }

            # Build the prompt
            user_instructions_section = ""
            if user_instructions:
                user_instructions_section = (
                    f"**Additional Instructions:** {user_instructions}"
                )

            prompt = _REPORT_PROMPT.format(
                topic=topic,
                report_style=report_style,
                user_instructions_section=user_instructions_section,
                source_content=source_content[:100000],  # Cap source content
            )

            # Call the LLM inline
            from langchain_core.messages import HumanMessage

            response = await llm.ainvoke([HumanMessage(content=prompt)])
            report_content = response.content

            if not report_content or not isinstance(report_content, str):
                error_msg = "LLM returned empty or invalid content"
                report_id = await _save_failed_report(error_msg)
                return {
                    "status": "failed",
                    "error": error_msg,
                    "report_id": report_id,
                    "title": topic,
                }

            # Extract metadata (includes "status": "ready")
            metadata = _extract_metadata(report_content)

            # Save to database
            report = Report(
                title=topic,
                content=report_content,
                report_metadata=metadata,
                report_style=report_style,
                search_space_id=search_space_id,
                thread_id=thread_id,
            )
            db_session.add(report)
            await db_session.commit()
            await db_session.refresh(report)

            logger.info(
                f"[generate_report] Created report {report.id}: "
                f"{metadata.get('word_count', 0)} words, "
                f"{metadata.get('section_count', 0)} sections"
            )

            return {
                "status": "ready",
                "report_id": report.id,
                "title": topic,
                "word_count": metadata.get("word_count", 0),
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

