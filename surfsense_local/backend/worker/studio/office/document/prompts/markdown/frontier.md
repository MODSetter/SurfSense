Write a $label in Markdown from the sources below. A builder turns your Markdown into the file, and the reader opens it cold without the sources.
$focus
How to work the material:

- The sources are raw material, not an outline to walk. Read all of them, decide what the document is for, and let its structure follow. A section per source is the failure mode.
- Prefer the specific figure, date or name over the general statement. Where sources disagree, say so rather than choosing silently.
- Distinguish what is settled from what is proposed, pending or conditional.
- Put only facts the sources state into the document: no outside knowledge, no invented precision, never a placeholder.

Markdown to use: one `# ` title line first, then `## ` and `### ` headings; paragraphs; `-` and `1.` lists, nested by indenting; tables with a header row; **bold**, *italic* and [links](https://...).

$figures

To chart numbers the sources state, write a fenced block whose language is `chart` holding one JSON object: {"type": "bar", "title": "Yearly costs", "labels": ["2025", "2026"], "series": [{"name": "Cost", "values": [12, 48]}]}. The type is bar, line or pie; each series has one number per label, and a pie has one series.

No HTML. Return only the Markdown.
