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
      "front_markdown": "One focused recall prompt",
      "back_markdown": "A sufficient, concise answer",
      "hint_markdown": "Optional hint"
    }
  ]
}
```

- Include 2–100 cards.
- Title: 1–200 characters. Front: 1–4,000. Back: 1–12,000. Hint:
  1–2,000 when present.
- Keep each front atomic and each back sufficient without testing multiple
  unrelated facts.
- Omit `hint_markdown` when no useful hint exists; never use `null`.
- Do not add fields, change `schema_version`, duplicate fronts, or use raw
  HTML, images, links, or headings in card content.
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
