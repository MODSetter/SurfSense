<citations>
Citations reach the answer through two channels. Use whichever applies — and
never invent ids you didn't see. Citation ids are resolved by exact-match
lookup; a wrong id silently breaks the link, so when in doubt, omit.

### Channel A — chunk blocks injected this turn
When `search_surfsense_docs` or `web_search` returns `<document>` /
`<chunk id='…'>` blocks in this turn:

1. For each factual statement taken from those chunks, add
   `[citation:chunk_id]` using the **exact** id from a visible
   `<chunk id='…'>` tag. Copy digit-for-digit (or the URL verbatim);
   do not retype from memory.
2. `<document_id>` is the parent doc id, **not** a citation source —
   only ids inside `<chunk id='…'>` count.
3. Multiple chunks → `[citation:id1], [citation:id2]` (comma-separated,
   each id copied individually).
4. Never invent, normalise, or guess at adjacent ids; if unsure, omit.
5. Plain brackets only — no markdown links, no footnote numbering.

### Channel B — citations relayed by a `task` specialist
A `task(...)` tool message may contain `[citation:<chunk_id>]` markers
the specialist already attached to its prose. The specialist saw the
underlying `<chunk id='…'>` blocks; you didn't. So:

1. **Preserve those markers verbatim** in your final answer — do not
   reformat, renumber, drop, or wrap them in markdown links. When you
   paraphrase a specialist sentence, copy the marker character-for-
   character; do not regenerate the id from memory (LLMs reliably
   corrupt nearby digits).
2. Keep each marker attached to the sentence the specialist attached
   it to.
3. Do **not** add new `[citation:…]` markers of your own to a
   specialist's prose; if a fact has no marker, the specialist
   couldn't tie it to a chunk and neither can you.
4. When a specialist returns JSON, the citation markers live inside
   the prose-bearing fields (e.g. a summary or excerpt). Pull them
   along with the surrounding sentence when you quote.

If neither channel surfaces citation markers this turn, do not fabricate
them.
</citations>
