"""Prompts used by the memory service."""

FORCED_REWRITE_PROMPT = """\
You are a memory curator. The following memory document exceeds the character \
limit and must be shortened.

RULES:
1. Rewrite the document to be under {target} characters.
2. Output Markdown only. Use clear `##` headings and concise bullet points.
3. New-format bullets should look like: `- YYYY-MM-DD: memory text`.
4. If the input contains legacy markers like `(YYYY-MM-DD) [fact]`, preserve the
   information but remove the inline marker in the output.
5. Preserve durable instructions and preferences before generic facts when
   compressing personal memory.
6. Preserve existing headings when useful; merge duplicate headings and bullets.
7. Output ONLY the consolidated markdown — no explanations, no wrapping.

<memory_document>
{content}
</memory_document>"""
