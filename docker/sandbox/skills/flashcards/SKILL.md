---
name: flashcards
description: Create strict JSON flashcard decks for active-recall study.
---

# Flashcards

Create one `/workspace/<slug>.json` file. JSON is the canonical deck; do not
write a separate Markdown summary.

## Contract

Use exactly this closed version-one shape:

```json
{
  "schema_version": 1,
  "title": "Deck title",
  "cards": [
    {
      "front_text": "One focused recall prompt",
      "back_text": "A sufficient, concise answer",
      "hint_text": "Optional hint with inline math: \\(x^2\\)"
    }
  ]
}
```

- Include 15–100 cards. Use a requested count within that range; otherwise
  choose 30–50 based on the source depth. Use mixed difficulty when unspecified.
  Do not ask for confirmation.
- Test one distinct recall target per card. Plan and deduplicate the targets
  before writing JSON; do not repeat, paraphrase, reverse, or split the same
  fact merely to reach the minimum.
- Report insufficient material only after finding fewer than 15 distinct recall
  targets in the available source and topic. Do not invent filler.
- Title: 1–200 characters. Front: 1–4,000. Back: 1–12,000. Hint:
  1–2,000 when present.
- Keep each front atomic and each back sufficient without testing multiple
  unrelated facts.
- Card fields are plain text. The only formatting syntax allowed is LaTeX:
  use `\(...\)` for inline math or `\[...\]` for display math. Escape each
  backslash as `\\` in JSON. Keep delimiters and braces balanced; do not nest
  math delimiters.
- Omit `hint_text` when no useful hint exists; never use `null`.
- Do not add fields, change `schema_version`, duplicate fronts, or use raw
  HTML or Markdown in card content.
- Write UTF-8 JSON without comments or a byte-order mark.

## Verify and save

Call:

```text
verify_artifact(path="/workspace/<slug>.json", format="flashcards")
```

Fix all blocking findings together, rewrite the JSON once, and reverify the
exact path. If a blocker remains, stop and explain it instead of looping.

After verification returns `status="verified"`, call:

```text
save_artifact(path="/workspace/<slug>.json", title="...")
```

Do not pass `markdown_representation`; the backend derives trusted Markdown
from the exact receipt-bound JSON.

For revisions, edit the restored JSON from `primary_path`, write the complete
deck to `expected_output_path`, verify that path as `flashcards`, and save with
the returned `artifact_id` and `expected_generation`. Do not edit the derived
`markdown_path` or reconstruct the deck with vision.
