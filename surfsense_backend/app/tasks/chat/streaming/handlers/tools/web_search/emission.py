"""web_search: citations parsed from provider XML."""

from __future__ import annotations

import re
from collections.abc import Iterator

from app.tasks.chat.streaming.handlers.tools.emission_context import (
    ToolCompletionEmissionContext,
)


def iter_completion_emission_frames(
    ctx: ToolCompletionEmissionContext,
) -> Iterator[str]:
    out = ctx.tool_output
    xml = out.get("result", str(out)) if isinstance(out, dict) else str(out)
    citations: dict[str, dict[str, str]] = {}
    for m in re.finditer(
        r"<title><!\[CDATA\[(.*?)\]\]></title>\s*<url><!\[CDATA\[(.*?)\]\]></url>",
        xml,
    ):
        title, url = m.group(1).strip(), m.group(2).strip()
        if url.startswith("http") and url not in citations:
            citations[url] = {"title": title}
    for m in re.finditer(
        r"<chunk\s+id='([^']*)'><!\[CDATA\[([\s\S]*?)\]\]></chunk>",
        xml,
    ):
        chunk_url, content = m.group(1).strip(), m.group(2).strip()
        if chunk_url.startswith("http") and chunk_url in citations and content:
            citations[chunk_url]["snippet"] = (
                content[:200] + "…" if len(content) > 200 else content
            )
    yield ctx.emit_tool_output_card(
        {"status": "completed", "citations": citations},
    )
