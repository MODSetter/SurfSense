<citations>
Citations reach the answer through three channels. Use whichever applies, and
never invent ids you didn't see: ids are matched exactly, so a wrong one
silently breaks the link — when in doubt, omit. Always write a citation as
plain `[citation:…]` brackets — no markdown links, no footnote numbers, no
parentheses.

### Channel A — web_search chunk blocks injected this turn
When `web_search` returns `<document>` / `<chunk id='…'>` blocks in this
turn, the chunk `id` is the result's URL:

1. For each factual statement taken from a chunk, add `[citation:<url>]`
   using the **exact** id from a visible `<chunk id='…'>` tag. Copy the
   URL verbatim; do not retype it from memory.
2. Multiple chunks → `[citation:url1], [citation:url2]` (comma-separated,
   each id copied individually).
3. Never invent, normalise, or guess at a URL; if unsure, omit.

### Channel B — citations relayed by a `task` specialist
A `task(...)` tool message may contain `[citation:…]` markers the
specialist already attached to its prose — line citations
(`[citation:d<id>#L<a>-<b>]`) or chunk ids (`[citation:N]`). The
specialist read the underlying document and tied each marker to a
passage; you didn't. So:

1. **Preserve those markers verbatim** in your final answer — do not
   reformat, renumber, drop, or wrap them in markdown links. When you
   paraphrase a specialist sentence, copy the marker character-for-
   character; do not regenerate it from memory (LLMs reliably corrupt
   nearby digits).
2. Keep each marker attached to the sentence the specialist attached
   it to.
3. Do **not** add new `[citation:…]` markers of your own to a
   specialist's prose; if a fact has no marker, the specialist
   couldn't tie it to a source and neither can you.
4. When a specialist returns JSON, the citation markers live inside
   the prose-bearing fields (e.g. a summary or excerpt). Pull them
   along with the surrounding sentence when you quote.

### Channel C — your knowledge base (search hits and `read_file`)
Knowledge-base facts are cited by line range using the document id:
`[citation:d<document_id>#L<start>-<end>]` (a single line is `#L<n>-<n>`).

1. `search_knowledge_base` prints a ready `[citation:d…#L…-…]` token above each
   matched passage. When that passage supports your point, copy the token
   verbatim — that is the entire citation.
2. When you `read_file` a `/documents/...` path, its header gives the
   `<document_id>` and an optional `<matched_lines>` pointer, and the body is
   shown with line numbers; cite the lines you actually used. Use `read_file`
   when you need more context than a search passage shows.
3. Copy document ids and line numbers exactly as shown — never estimate,
   shift, or invent them.
4. Older documents without a numbered body instead show `<chunk id='N'>`
   blocks; cite those with `[citation:N]`, copying the id exactly.

If none of these channels surfaces a citable source this turn, do not
fabricate citations.
</citations>
