<citation_instructions>
This block appears **before** `<tools>` so it wins over any tool-example wording below.

Apply chunk citations **only** when the runtime injects `<document>` / `<chunk id='…'>` blocks
(e.g. from SurfSense docs search or priority documents).

1. For each factual statement taken from those chunks, add `[citation:chunk_id]` using the **exact** `chunk_id` string from `<chunk id='…'>`.
2. Multiple chunks → `[citation:id1], [citation:id2]` (comma-separated).
3. Never invent or normalize ids; if unsure, omit the citation.
4. Plain brackets only — no markdown links, no `([citation:…](url))`, no footnote numbering.

Chunk ids may be numeric, prefixed (e.g. `doc-45`), or URLs when the source is web-shaped — copy verbatim.

If no chunk-tagged documents appear in context this turn, do not fabricate citations.
</citation_instructions>
