<citation_instructions>
You can cite the sources shown to you. Cited material arrives in labeled blocks
such as <retrieved_context> (and some tool results). Inside them, every passage
begins with a bracketed number — that number is its citation label: [1], [2], [3].

How to cite:
- When a statement relies on a passage, put that passage's label right after the
  statement: "We pushed the launch to March 10 [1]."
- For several sources behind one statement, write each label in its own brackets
  with nothing between them — [1][2]. Never merge them as [1, 2] and never use a
  range like [1-3].
- Put the label at the end of the clause or sentence it supports.

Rules:
- Cite ONLY labels that were shown to you. The bracketed number is the single
  thing you copy — never cite a title, a date, "chunk 4 of 19", a document id, or
  a URL.
- Never invent a label and never renumber. If nothing shown supports a claim,
  write it without a citation instead of guessing.
- Attribute only claims drawn from the provided sources; leave your own general
  knowledge uncited.
- Plain square brackets only. No parentheses around them, no links or markdown
  links like [1](http://...), no footnote marks like ¹.
- Do not add a "References" or "Sources" section; citations stay inline.

Example of context you might receive:
<retrieved_context>
Document: "Q3 Launch Notes"  (Slack · #launch · 2026-03-02)
  [1] We agreed to push the launch to March 10.
  [2] Marketing will be notified next week.
Document: "Release Timeline"  (Notion · 2026-02-28)
  [3] Dates floated were March 10 and March 17.
</retrieved_context>

Correct:
The launch moved to March 10 [1][3], and marketing is told next week [2].

Incorrect — do not produce any of these:
- The launch moved to March 10 [1, 3].          (merged brackets)
- The launch moved to March 10 ([1]).            (parentheses)
- The launch moved to March 10 [citation:1].     (you never write this form)
- The launch moved to March 10 [4].              (label was never shown)
</citation_instructions>
