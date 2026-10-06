Write a $label in Markdown from the sources below, using their facts only.
$focus
Use:

- one `# ` title line first, then `## ` section headings;
- paragraphs, `-` and `1.` lists, and tables with a header row;
- **bold** and *italic* where they help.

$figures

To chart numbers the sources state, write a fenced block whose language is `chart` holding one JSON object: {"type": "bar", "title": "Yearly costs", "labels": ["2025", "2026"], "series": [{"name": "Cost", "values": [12, 48]}]}. The type is bar, line or pie, and each series has one number per label.

No HTML. Return only the Markdown.
