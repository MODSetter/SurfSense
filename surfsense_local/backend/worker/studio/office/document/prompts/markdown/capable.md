Write a $label in Markdown from the sources below, using their facts only. A builder turns your Markdown into the file, so its structure is the document's structure.
$focus
Work in this order:

1. Read every source and note the figures, dates, names and decisions it states.
2. Decide the document: its sections, their order, and which facts go in each. Prefer the specific figure over the general statement.
3. Write it.

Markdown to use:

- One `# ` title line first, then `## ` and `### ` headings.
- Paragraphs; `-` and `1.` lists, nested by indenting; tables with a header row where the facts compare.
- **Bold** and *italic* for emphasis, and links as [text](https://...).

$figures

To chart numbers the sources state, write a fenced block whose language is `chart` holding one JSON object: {"type": "bar", "title": "Yearly costs", "labels": ["2025", "2026"], "series": [{"name": "Cost", "values": [12, 48]}]}. The type is bar, line or pie; each series has one number per label, and a pie has one series. Chart only numbers you found.

Grounding rules:

- Put only facts the sources state into the document. No outside knowledge, no estimates, no placeholder text such as "Lorem ipsum" or "TBD".
- If a source calls something proposed, pending or a draft, say so.

No HTML. Return only the Markdown: no note before it, no explanation after it.
