---
name: quiz
description: Create strict JSON single-answer multiple-choice quizzes.
---

# Quiz

Create one `/workspace/<slug>.json` file. JSON is the canonical quiz; do not
write a separate Markdown summary.

## Contract

Use exactly this closed version-one shape:

```json
{
  "schema_version": 1,
  "title": "Quiz title",
  "questions": [
    {
      "question_text": "One focused question",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_option_index": 1,
      "explanation_text": "Why Option B is correct."
    }
  ]
}
```

- Include 5–30 questions. Use an explicitly requested count within that range;
  otherwise create exactly 10. If the requested count is outside the range,
  stop and explain the supported range instead of clamping it.
- Plan distinct assessment targets before writing. Do not duplicate,
  paraphrase, reverse, or pad weak questions to reach the minimum.
- If the available source cannot support five defensible questions, stop
  without creating filler.
- Every question has exactly four distinct options and exactly one objectively
  correct option. `correct_option_index` is an integer from `0` through `3`.
- Write three plausible distractors. Avoid “All of the above,” “None of the
  above,” trick wording, grammar clues, and obvious correct-position patterns.
- `explanation_text` is required and should concisely teach why the selected
  answer is correct.
- Title: 1–200 characters. Question and each option: 1–4,000. Explanation:
  1–12,000.
- Content is plain text. The only formatting syntax is LaTeX: use `\(...\)` for
  inline math and `\[...\]` for display math. Escape each backslash as `\\` in
  JSON. Keep delimiters and braces balanced and do not nest math delimiters.
- Do not add fields, change `schema_version`, use Markdown or raw HTML, include
  links or media, duplicate question text, or use `null`.
- Write UTF-8 JSON without comments or a byte-order mark.

## Verify and save

Call:

```text
verify_artifact(path="/workspace/<slug>.json", format="quiz")
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
quiz to `expected_output_path`, verify that path as `quiz`, and save with the
returned `artifact_id` and `expected_generation`. Do not edit the derived
`markdown_path` or reconstruct the quiz with vision.
