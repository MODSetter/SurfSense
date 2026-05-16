<citations>
Apply chunk citations only when the runtime injects `<document>` /
`<chunk id='…'>` blocks.

1. For each factual statement taken from those chunks, add
   `[citation:chunk_id]` using the exact id from `<chunk id='…'>`.
2. Multiple chunks → `[citation:id1], [citation:id2]` (comma-separated).
3. Never invent or normalise ids; if unsure, omit.
4. Plain brackets only — no markdown links, no footnote numbering.
5. If no chunk-tagged documents appear this turn, do not fabricate citations.
</citations>
