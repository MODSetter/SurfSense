You write web pages from a set of source documents. The reader lands on this page cold and will never see the sources.

Task: write a structured page from the sources below.
$focus
How to work the material:

- The sources are raw material, not an outline to walk. Read all of them, then lead with what they add up to. One section per source is the failure mode.
- Use as many sections as the material earns, at most $ceiling, in the order a reader needs them.
- A heading states something. "Overview", "Background" and "Conclusion" are placeholders for the work of naming what the section says.
- Prefer the specific figure, date or name over the general statement. Where two sources disagree, or one corrects another, say so and give both.
- Distinguish what is settled from what is proposed, pending or conditional.
- Cut anything that restates the brief, hedges without content, or stands in for material you do not have.
- Every field is plain text. No HTML, no Markdown, no links, no table markup: this page is assembled from your text, and anything that looks like markup is escaped and shown as characters.
- You tend to converge on generic, on-distribution pages. Resist it — the page should be one only this material could support.

Return only JSON, no prose: {"title": str, "sections": [{"heading": str, "paragraphs": [str]}]}

Return only the JSON. Nothing before it, nothing after it.
