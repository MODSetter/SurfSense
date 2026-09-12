# Phase 11 — Interactive Quiz Artifacts

**Status:** Planned.
**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md).
**Depends on:** phase 1 artifact persistence and manifests, phase 3 signed
verification receipts, phase 8's strict-JSON and per-user interaction-state
precedent, and phase 10 public artifact access.
**Independent of:** spreadsheet hardening and fallback-format verification
except for their shared regression suite.

## 1. Goal

Add generated, single-answer multiple-choice quizzes as first-class artifacts
through the universal artifact flow:

```text
load_artifact_instructions("quiz")
  -> execute
  -> verify_artifact(path=..., format="quiz")
  -> save_artifact(path=...)
```

A quiz artifact:

- stores one strict versioned JSON quiz as its primary file;
- contains 5–30 questions and defaults to exactly 10 when the user does not
  request a count;
- contains exactly four options and exactly one correct option per question;
- uses normal text with the same bounded LaTeX syntax as flashcards, not
  Markdown-authored content;
- derives searchable Markdown from the verified JSON in trusted backend code;
- renders through one interactive viewer in the desktop artifact panel, mobile
  drawer, and phase 10 public artifact surface;
- persists submitted answers and retake scope per authenticated user in the
  existing `Artifact.metadata` JSONB column;
- shows the score only after every question in the active run is answered;
- supports read-only, one-question-at-a-time review of the complete quiz;
- supports `Retake missed` and `Retake all`;
- exposes no shuffle or download control in the quiz viewer.

This phase adds one format adapter, one generation skill, one semantic viewer,
and two bounded artifact-scoped mutation operations. It does not add another
artifact model, agent save tool, panel, mobile drawer, database table, database
column, Alembic migration, attempt-history system, analytics pipeline, or
public mutation API.

## 2. Product and scope decisions

### 2.1 Quiz, not questionnaire

Phase 11 implements a scored quiz. Every question has one objectively correct
answer and three distractors.

A questionnaire, survey, poll, personality test, or form has different
semantics: answers may not be correct, results may require aggregation, and
responses may be collected for an author rather than graded for the respondent.
Those products do not route to `quiz` and are not represented by this schema.

### 2.2 Single-answer version one

Every question has:

- one question;
- exactly four distinct options;
- exactly one correct option;
- one required explanation.

The viewer uses radio-group behavior. Phase 11 does not support multi-select
questions, partial credit, multiple correct answers, confidence ratings,
free-text answers, matching, ordering, true/false special cases, or answer
weights.

This is a deliberate version-one boundary. Multi-select changes authoring
quality, controls, scoring, persistence validation, review language, and
accessibility. If validated product demand appears, add a new schema version
with explicit semantics rather than weakening version one.

### 2.3 Question-count policy

The verified schema accepts 5–30 questions.

- An explicit requested count within 5–30 is used exactly.
- An omitted count defaults to exactly 10.
- A request below 5 or above 30 is a constraint conflict; the agent explains
  the supported range instead of silently clamping it.
- The agent must not duplicate, paraphrase, reverse, or pad weak questions to
  reach the minimum.
- If available source material cannot support five distinct, defensible
  questions, generation stops without saving an invalid or filler quiz.

The 30-question ceiling bounds generation quality, primary-file parsing,
per-user metadata, review length, and panel usability. It is not a database
capacity claim.

### 2.4 Assessment behavior

During an active run:

- questions appear one at a time in canonical JSON order;
- the user selects one option and explicitly submits it;
- an answer is not persisted until submission;
- the viewer advances only after the server accepts the answer;
- submitted answers cannot be changed during that run;
- correctness and the explanation are not revealed during the active run;
- there is no skip action;
- there is no shuffle action;
- there is no previous-question editing path.

After every question in the active run has a submitted answer, the viewer
replaces the question surface with the score section.

The score section shows:

- correct answers as `correct / total`;
- an integer percentage derived from that ratio;
- incorrect count;
- a bounded list of missed question numbers and question text;
- `Review`;
- `Retake missed` when at least one answer is incorrect;
- `Retake all`.

The result is based on the user's latest submitted answer for each question.
The system stores neither a duplicate score nor a correctness flag.

### 2.5 Review behavior

`Review` is available only from a completed score section. It walks every
question in canonical order, not only missed questions.

For each question, review shows:

- question position;
- question text;
- all four options;
- the user's submitted option;
- the correct option;
- whether the user's answer was correct;
- the required explanation;
- previous and next controls;
- an exit control that returns to the score section.

Review is read-only. It creates no API request, metadata field, review event, or
new attempt. The current review index stays in component state and is lost when
the viewer closes.

### 2.6 Retake behavior

`Retake missed` and `Retake all` are user-scoped mutations.

`Retake missed`:

1. is available only after a complete run with at least one incorrect answer;
2. asks the backend to derive the currently incorrect question indexes from
   the verified answer key and the authenticated user's submitted answers;
3. clears answers only for those incorrect questions;
4. preserves correct answers;
5. persists the missed-question indexes as the next active run scope;
6. resumes at the first unanswered question in that scope;
7. shows the score again only when every question in that scope is answered.

The resulting score remains `correct / total questions`, not
`correct / retaken questions`. A successful retake therefore improves the
user's current score without creating attempt history.

`Retake all`:

1. is available after a complete run;
2. clears all submitted answers for that user;
3. restores the complete canonical question scope;
4. resumes at question one.

There is no separate reset button. `Retake all` is the complete reset behavior;
duplicating it in the artifact header would create two controls for the same
mutation.

### 2.7 State ownership

Authenticated state is private to the current user. It is never shared with
workspace collaborators and is never keyed by a user ID supplied by the
client.

Persist:

- submitted answers;
- active run mode;
- active question indexes;
- artifact generation.

Keep local:

- the currently displayed question position;
- the currently selected, unsubmitted option;
- score/review screen selection;
- review position;
- pending, error, focus, and announcement state.

Phase 11 intentionally does not persist:

- immutable attempts;
- historical scores;
- timestamps or duration;
- answer-change history;
- streaks;
- analytics;
- current panel position;
- public visitor state.

If attempt history or reporting becomes a real requirement, use user-owned
rows designed for append-only attempts. Do not grow the artifact metadata map
into an event store.

### 2.8 Download policy

The semantic renderer sets `downloadable: false`, so the panel exposes no quiz
download control.

The format-neutral authenticated and phase 10 public artifact download routes
remain unchanged. The viewer must fetch the JSON primary to render it, so
hiding the control is product presentation, not a secrecy boundary. Phase 11
must not add a format-specific prohibition to the universal file API or claim
that an answer key delivered to a browser cannot be inspected.

## 3. Persistence and format identity

A quiz is:

- one `Document(document_type=ARTIFACT)` containing trusted, derived searchable
  Markdown;
- one `Artifact(format="quiz")`;
- one primary `<slug>.json` `ArtifactFile` with MIME `application/json`;
- no preview file.

Add `QUIZ = "quiz"` to `ArtifactFormat` for typed callers and roster clarity.
The database column remains a string. No Alembic migration is required.

The primary JSON owns quiz semantics and viewer bytes. The document Markdown
owns indexing, search, citations, Git projection, and agent revision context.
The Markdown is generated from the exact verified primary bytes during save.
It is never independently authored or parsed to render the quiz.

`.json` and `application/json` identify only the physical representation.
Explicit `format="quiz"` in the verification receipt, artifact row, manifest,
and renderer registry identifies quiz semantics. Generic JSON and flashcard
JSON must never acquire quiz behavior from MIME or suffix inference.

## 4. Canonical JSON contract

Version one has this complete shape:

```json
{
  "schema_version": 1,
  "title": "HTTP fundamentals",
  "questions": [
    {
      "question_text": "Which HTTP method is commonly used to replace a resource?",
      "options": ["GET", "POST", "PUT", "TRACE"],
      "correct_option_index": 2,
      "explanation_text": "PUT commonly replaces the state of the target resource."
    },
    {
      "question_text": "What is the derivative of \\(x^2\\)?",
      "options": ["\\(x\\)", "\\(2x\\)", "\\(x^3\\)", "\\(2\\)"],
      "correct_option_index": 1,
      "explanation_text": "By the power rule, \\(\\frac{d}{dx}x^2=2x\\)."
    }
  ]
}
```

The schema is closed:

- the top level contains exactly `schema_version`, `title`, and `questions`;
- `schema_version` is the integer `1`, not a boolean or numeric string;
- `title` is a non-empty, single-line string;
- `questions` contains 5–30 ordered entries;
- every question contains exactly `question_text`, `options`,
  `correct_option_index`, and `explanation_text`;
- question and explanation strings are non-empty;
- `options` is an array of exactly four non-empty strings;
- `correct_option_index` is a strict integer from `0` through `3`;
- null and unknown fields fail verification.

Question identity within one immutable artifact generation is its zero-based
array index. Option identity within one question is its zero-based array index.
Revision increments generation and clears progress, so persistent UUIDs would
add structure without preserving required identity.

### 4.1 Bounds

Keep limits in one backend module and mirror them in the generation skill and
frontend schema:

- 5–30 questions;
- default generation count of 10;
- title at most 200 Unicode code points;
- question text at most 4,000 Unicode code points;
- each option at most 4,000 Unicode code points;
- explanation text at most 12,000 Unicode code points;
- existing `ARTIFACT_MAX_FILE_BYTES` for the complete JSON file;
- existing frontend pre-fetch and post-fetch byte limits.

The verifier normalizes only for checks and never rewrites agent bytes. It
rejects:

- empty bytes;
- invalid UTF-8;
- a UTF-8 byte-order mark;
- duplicate JSON object keys;
- `NaN`, `Infinity`, and other non-standard JSON constants;
- unsupported control characters;
- non-object top levels;
- unsupported schema versions;
- missing, extra, null, or wrongly typed fields;
- multiline or overlong titles;
- question counts outside 5–30;
- option arrays with fewer or more than four entries;
- out-of-range or non-integer correct indexes;
- empty or overlong question, option, and explanation text;
- malformed, nested, mismatched, empty, or unclosed LaTeX delimiters;
- unbalanced LaTeX braces;
- duplicate options within a question after Unicode normalization, whitespace
  collapsing, and case folding;
- duplicate question text across the quiz after the same normalization.

Duplicate detection is a bounded structural-quality guard. It does not prove
that differently worded questions assess different concepts or that a
distractor is pedagogically useful.

### 4.2 Text and LaTeX contract

Quiz content uses the same text contract as implemented flashcards:

- ordinary characters are rendered as literal text;
- `\(...\)` denotes inline LaTeX;
- `\[...\]` denotes display LaTeX;
- delimiters cannot nest;
- delimiters and braces must balance;
- JSON escapes each backslash, so `\(x\)` appears as `"\\(x\\)"` in the file.

Content is not authored as Markdown. Markdown punctuation in source text has no
formatting meaning in the viewer and is escaped in the trusted Markdown
projection. Raw HTML is not executed. Active links, images, remote resources,
scripts, and embedded media are not supported.

Extract the existing pure text/LaTeX validation, segmentation, escaping, and
rendering behavior into a study-content helper shared by flashcards and quiz.
Do not create separate parsers that can drift. The extraction must preserve the
published flashcard contract and its tests.

### 4.3 What verification cannot prove

Programmatic verification proves that the JSON is strict, bounded, internally
referentially valid, and safe for the supported renderer. It cannot prove:

- factual correctness;
- that exactly one option is semantically correct;
- distractor plausibility;
- source coverage;
- difficulty appropriateness;
- absence of ambiguous wording;
- pedagogical value.

Those are generation-quality concerns. Phase 11 does not add an LLM judge or
vision review disguised as structural verification.

## 5. Programmatic verification

Add `verification/formats/quiz.py` with:

```python
parse_quiz(data: bytes) -> QuizV1
check_quiz_json(data: bytes) -> StructuralCheckResult
quiz_to_markdown(data: bytes) -> str
```

Register:

```python
FormatAdapter(
    name="quiz",
    suffix=".json",
    mime_type="application/json",
    convert_to_pdf=False,
    check=check_quiz_json,
    requires_visual_review=False,
    markdown_projection=quiz_to_markdown,
)
```

Add `"quiz"` to `VerifiableArtifactFormat`. Successful verification:

- runs no LibreOffice command;
- creates no PDF;
- rasterizes no pages;
- invokes no vision model;
- creates no preview;
- signs the exact primary SHA-256;
- records `visual="not_required"`;
- reports only bounded notes such as schema version and question count.

Use the standard-library JSON decoder with the existing duplicate-key and
non-standard-constant rejection pattern, then validate through closed Pydantic
models with strict types and `extra="forbid"`. Do not add a JSON Schema runtime
or quiz dependency.

The existing signed-receipt boundary remains authoritative:

1. verify reads and validates the JSON;
2. the receipt binds the exact accepted primary hash and `format="quiz"`;
3. save reads the file again;
4. save rejects post-verification mutation;
5. only the exact verified bytes become the primary artifact.

## 6. Trusted Markdown projection

`quiz_to_markdown` parses through the same validated model used by verification
and emits deterministic searchable Markdown:

```markdown
# HTTP fundamentals

## Question 1

Which HTTP method is commonly used to replace a resource?

### Options

A. GET
B. POST
C. PUT
D. TRACE

### Correct answer

C. PUT

### Explanation

PUT commonly replaces the state of the target resource.
```

The projection:

- includes every question, option, correct answer, and explanation;
- renders LaTeX using the existing preserved delimiter form;
- escapes ordinary text so it cannot become projection structure;
- uses stable option labels `A` through `D`;
- ends with one normalized final newline;
- is deterministic for identical parsed input;
- never contains a raw JSON dump.

For the quiz adapter, the public `save_artifact` contract omits
`markdown_representation`. `save_artifact` derives it from the receipt-bound
primary and rejects a caller-supplied competing value. The universal
adapter/save mechanism remains the only save path.

## 7. Generation skill and intent routing

Add `docker/sandbox/skills/quiz/SKILL.md` and advertise `"quiz"` through
`load_artifact_instructions`.

The skill teaches the agent to:

1. identify distinct concepts supported by the available source and user topic;
2. use the requested question count when it is within 5–30;
3. use exactly 10 questions when no count is requested;
4. stop on an out-of-range requested count instead of silently clamping;
5. plan distinct assessment targets before writing;
6. create one deliverable-named UTF-8 JSON file under `/workspace`;
7. use the exact closed version-one schema;
8. write one unambiguous correct answer and three plausible distractors per
   question;
9. distribute correct-option positions without an obvious pattern;
10. write a concise explanation that teaches why the answer is correct;
11. use only ordinary text and supported LaTeX;
12. call `verify_artifact(path=..., format="quiz")`;
13. repair all blocking structural findings in one pass and reverify once;
14. call the existing `save_artifact` with the verified path and title;
15. stop with an explanation after a persistent blocker.

Generation guidance prohibits:

- `All of the above` and `None of the above`;
- duplicate or trivially equivalent options;
- options whose grammar reveals the answer;
- repeated question targets;
- filler added to satisfy the minimum;
- trick wording and unnecessary negatives;
- an answer stated verbatim in the question;
- unsupported Markdown, HTML, links, or media;
- a separately authored Markdown representation.

Intent routing adds quiz ahead of HTML and PDF defaults:

- explicit quiz, multiple-choice quiz, MCQ, scored test, or “test me with
  multiple-choice questions” requests select `quiz`;
- flashcards, recall cards, and revision cards remain `flashcards`;
- questionnaires, surveys, polls, forms, and personality tests do not select
  `quiz`;
- explanations, summaries, and ordinary question lists remain documents unless
  the user explicitly asks for an interactive scored quiz.

Update:

- deliverables `system_prompt.md`;
- deliverables `description.md`;
- `tools/sandbox.py` format literal;
- installed-skill roster tests;
- routing tests covering explicit, synonymous, ambiguous, and negative intent;
- `load_artifact_for_revision` with quiz-specific revision instructions.

No new tool registration, activity kind, completion emitter, or frontend tool
card is introduced. Generation still completes through `save_artifact`.

## 8. Manifest contract

The authenticated manifest adds one format-scoped field only when
`format == "quiz"`:

```json
{
  "artifact_id": 123,
  "format": "quiz",
  "generation": 2,
  "markdown_representation": "# HTTP fundamentals\n...",
  "files": [
    {
      "role": "primary",
      "filename": "http-fundamentals.json",
      "mime_type": "application/json",
      "content_url": "/api/v1/workspaces/7/artifacts/123/files/456/content"
    }
  ],
  "quiz_state": {
    "generation": 2,
    "mode": "missed",
    "active_question_indices": [1, 4, 8],
    "answers": {
      "0": 2,
      "2": 1,
      "3": 0
    }
  }
}
```

`answers` contains the authenticated user's latest submitted option index for
each currently retained question. During `missed` mode, correct answers from
the preceding completed run remain present while answers for the active missed
scope are absent until resubmitted.

Do not expose raw `Artifact.metadata`. Build a sanitized response that:

- returns only `auth.user.id`;
- accepts only the current artifact generation;
- validates mode;
- validates a complete, unique, in-range active scope;
- validates integer-like question keys in range;
- validates strict option indexes from `0` through `3`;
- drops malformed or stale state;
- returns canonical empty `all` state on corruption.

Malformed metadata logs a bounded warning and does not make the verified quiz
unviewable.

The authenticated manifest ETag varies with a deterministic digest of the
sanitized current-user quiz state in addition to document content hash and
artifact generation. Answer or retake writes do not increment artifact
generation or change content timestamps.

## 9. Per-user persistence

Use the existing `Artifact.metadata` JSONB:

```json
{
  "quiz": {
    "progress_by_user": {
      "00000000-0000-0000-0000-000000000001": {
        "generation": 2,
        "mode": "all",
        "active_question_indices": [0, 1, 2, 3, 4],
        "answers": {
          "0": 1,
          "1": 3
        }
      }
    }
  }
}
```

User keys are canonical UUID strings derived from authenticated server context.
The client never sends or selects the metadata key.

The state is:

- private to one authenticated user;
- generation-scoped;
- bounded by at most 30 active indexes and 30 scalar answers;
- latest-answer state, not attempt history;
- removed when it is equivalent to canonical untouched state;
- removed for all users when artifact content is revised.

The backend computes correctness from verified primary JSON whenever it needs
to derive missed questions or a score-related decision. It does not persist
`correct`, `score`, `percentage`, or a duplicate answer key.

### 9.1 Answer mutation

Add:

```text
PUT /api/v1/workspaces/{workspace_id}/artifacts/{artifact_id}/quiz-answer
```

Request:

```json
{
  "generation": 2,
  "question_index": 4,
  "selected_option_index": 1
}
```

The request model is strict and closed. Booleans are not accepted as integers.

The route:

1. requires `ARTIFACTS_UPDATE`;
2. resolves the authenticated user from server auth context;
3. loads the workspace-scoped artifact and rejects non-quiz format with `404`;
4. compares generation and returns `409` when stale;
5. reads the bounded primary JSON and validates it through the shared quiz
   parser;
6. row-locks the artifact and rechecks format and generation;
7. sanitizes only the authenticated user's current state;
8. rejects a question outside the current active scope with `422`;
9. rejects an out-of-range selected option with `422`;
10. stores the selected option for the target question;
11. treats an identical retry as idempotent success;
12. rejects a different replacement for an already submitted answer with
    `409`, requiring a retake operation to clear it;
13. preserves every other user's state and unrelated metadata;
14. commits atomically and returns sanitized current-user state.

The UI does not advance until this route succeeds. A failed request retains the
current question and selected option and shows a retryable error.

### 9.2 Retake mutation

Add:

```text
POST /api/v1/workspaces/{workspace_id}/artifacts/{artifact_id}/quiz-retake
```

Request:

```json
{
  "generation": 2,
  "mode": "missed"
}
```

`mode` is exactly `"missed"` or `"all"`.

The route performs the same permission, workspace, format, generation, primary
parsing, row-lock, and metadata-isolation checks as answer submission.

Before either retake, it requires a complete current run. A run is complete
when every index in `active_question_indices` has a submitted answer.

For `mode="missed"`:

1. calculate correctness for all quiz questions from the user's current
   answers and the verified answer key;
2. reject the operation with `409` when there are no missed questions;
3. create an ascending canonical list of incorrect question indexes;
4. remove answers for exactly those indexes;
5. preserve all correct answers;
6. set `mode="missed"`;
7. set `active_question_indices` to the missed indexes.

For `mode="all"`:

1. clear every answer;
2. set `mode="all"`;
3. set `active_question_indices` to every canonical question index.

The operation returns sanitized state. It does not create an attempt row,
increment artifact generation, modify the primary, reindex, write Git, or
change the artifact's content timestamp.

### 9.3 Concurrency

Use the same short artifact-row lock precedent as flashcard progress. The lock
serializes bounded JSONB writes:

- concurrent writes by different users merge against the latest
  `progress_by_user` map;
- duplicate retries of the same answer are idempotent;
- two different answers for the same unanswered question cannot both replace
  each other silently;
- answer submission racing a retake resolves through lock order and completion
  checks;
- stale generation always fails closed.

Add a `ponytail:` comment documenting that this is appropriate for bounded
state and that user-owned rows are the upgrade path if workspace contention or
metadata growth becomes material.

### 9.4 Revision cleanup

Quiz progress belongs to an immutable generation and has no meaning after any
content revision.

On successful revision:

- replace primary JSON and derived Markdown atomically;
- increment artifact generation;
- remove the entire `metadata.quiz` namespace in the same transaction;
- preserve unrelated verification and media metadata according to existing
  service rules.

Generation-scoped interaction namespaces should be cleared on revision even
when a revision changes semantic format. Update revision cleanup so stale quiz
or flashcard state cannot survive a format switch. A failed or stale revision
preserves current content, generation, and user state.

## 10. Public access

Phase 10's token-scoped artifact routes expose the verified quiz primary and
derived Markdown through the existing allowlist and workspace/thread checks.
They do not expose `quiz_state` and do not add public answer or retake routes.

The public quiz viewer is fully interactive with visit-local state:

- it starts as a new `all` run;
- answers remain in component memory;
- score, review, retake missed, and retake all work locally;
- refresh or closing the public page discards progress;
- no authenticated user's state is read;
- no public visitor state is persisted.

The authenticated and public surfaces use the same quiz renderer with an
injected state mode:

- authenticated mode reads and mutates manifest-backed state;
- public mode uses the same pure state transitions in memory.

Do not fork the question, score, or review UI. Do not require authentication
when a valid share token is present. Public caches must remain token-scoped
under the phase 10 contract.

## 11. Frontend renderer

### 11.1 Semantic dispatch

Register `quiz` in the semantic renderer registry ahead of MIME dispatch:

```text
manifest.format == "quiz"
  -> QuizViewer
otherwise
  -> existing semantic/MIME/Markdown/fallback behavior
```

Add format metadata:

- icon: an existing list-check or circle-help icon from `lucide-react`;
- label: `Interactive`;
- detail label: `Quiz`;
- group: `Files`;
- viewing mode: `viewer`.

The renderer is:

```text
{ Viewer: QuizViewer, downloadable: false }
```

It has no header `Actions` component because retake controls belong to the
completed score state and there is no separate reset or download action.

### 11.2 Loading and validation

`QuizViewer` is a client-only dynamic import. Until all required data is ready,
render only the existing centered shared Spinner:

1. manifest and primary metadata are available;
2. primary bytes have been fetched;
3. pre-fetch and post-fetch size checks pass;
4. UTF-8 decoding and strict Zod validation pass;
5. authenticated state has been normalized or public local state initialized;
6. the first screen has been selected.

Do not mount a partial question, score card, option list, or measured layout
during loading. Fetch, decode, parse, or state failure replaces the Spinner
with the shared `UnviewableFile` state.

Frontend Zod mirrors the backend schema and all bounds as defense in depth. It
does not repair invalid decks, accept unknown versions, infer quiz semantics
from JSON MIME, or trust manifest interaction state without normalization.

### 11.3 Taking state

The taking screen shows:

- quiz title;
- `Question X of Y`, where `Y` is the active run scope;
- bounded progress indicator;
- question text rendered through shared study text/LaTeX;
- four options in a native accessible radio group;
- one primary `Submit answer` button;
- pending and retryable-error feedback.

Option labels use visible `A`, `B`, `C`, and `D`, but the radio value is the
zero-based option index. Labels and complete option text form one click/tap
target. Color is not the only selected-state signal.

The submit button is disabled until one option is selected and while a
mutation is pending. Submission:

- sends only generation, question index, and selected option index;
- does not send user ID, correctness, score, or active scope;
- advances on authoritative success;
- clears the local unsubmitted selection for the next question;
- stays on the current question on failure.

After the last active question succeeds, derive completion and render the score
section. Do not briefly render an unanswered next-question shell.

### 11.4 Score state

The score section appears only when every active-scope question has an answer.
It derives results from the validated quiz and sanitized current-user answers.

Show:

- `Your score`;
- `correct / total`;
- rounded integer percentage;
- a segmented or otherwise accessible correct/incorrect progress summary;
- explicit `Got it (N)` and `Missed it (N)` labels;
- a scroll-bounded missed-question list containing original question numbers
  and question text;
- `Review`;
- a `Retake quiz` menu or grouped control containing `Retake missed` and
  `Retake all`.

When the score is perfect:

- show `Got it (total)` and `Missed it (0)`;
- omit or disable `Retake missed`;
- keep `Review` and `Retake all`.

Do not add `Skipped`, because skipping is unsupported. Do not add “Generate
follow-up quiz,” social sharing, timers, leaderboards, or analytics in this
phase.

Authenticated retake controls wait for the authoritative mutation response
before leaving the score section. Public retake controls apply the same pure
transition locally.

### 11.5 Review state

The review screen uses the same option rendering as taking mode but does not
mount radio inputs or mutation controls.

For each option:

- show selected state when it matches the user's answer;
- show correct state when it matches `correct_option_index`;
- distinguish selected-incorrect from correct-unselected;
- include text or icons so green/red color is not the only signal.

Show the explanation after the options. Previous and next operate over all quiz
questions in canonical order. Exiting review returns to the unchanged score
section. Review never modifies answers or active retake scope.

### 11.6 Local state and derived values

Derive during rendering:

- current question object;
- active progress;
- completion;
- correctness per question;
- correct and missed counts;
- score percentage;
- missed question list.

Do not mirror these values into effects or persistent state. Persisted answers
and validated primary content are the sources of truth.

Use functional state updates where transitions depend on current local state.
Do not add a quiz state-machine dependency; the four UI modes
`loading | taking | score | review` are small and explicit.

### 11.7 Accessibility and mobile

- Use a semantic radio group with one accessible label per option.
- Keyboard arrow keys move radio selection through native behavior.
- `Enter` submits only when focus is not on another interactive action and a
  selection exists.
- Move focus to the next question heading after successful submission.
- Move focus to the score heading when the run completes.
- Announce submission failures and mode changes through bounded live regions.
- Expose progress text in addition to visual progress.
- Review correctness uses labels/icons in addition to color.
- Retake actions require clear names and do not rely on a compact icon alone.
- The missed-question list has a bounded scroll region without trapping
  keyboard focus.
- Respect reduced-motion preferences for screen transitions.
- Put `data-vaul-no-drag` on quiz controls and scroll regions in the mobile
  drawer.
- Use one viewer for desktop, mobile, authenticated, and public surfaces.

## 12. Revision

`load_artifact_for_revision(artifact_id)` restores:

- current `.json` primary;
- derived Markdown context;
- `.json` expected output path;
- artifact ID;
- expected generation.

Add quiz revision guidance:

> Edit the restored JSON quiz without changing schema version one. Preserve
> exactly four options and one correct option per question, write the complete
> quiz to the expected output path, verify it as `quiz`, and save with the
> returned artifact ID and generation. Do not edit the derived Markdown.

Revision follows the ordinary signed receipt and optimistic-generation
contract. A successful revision clears all users' quiz progress only after the
new generation commits. A failed or stale revision leaves the current quiz and
progress untouched.

## 13. Failure and operational behavior

- Invalid JSON/schema/text: verification returns bounded actionable findings
  and issues no receipt.
- Ambiguous or factually wrong content: outside structural verification; fix
  through generation/revision quality.
- Post-verification mutation: save rejects the primary hash mismatch.
- Projection failure: save fails before persistence.
- Indexing failure: retain the saved JSON and artifact under existing retryable
  document status.
- Viewer fetch/parse failure: show shared fallback; no quiz controls mount.
- Malformed authenticated metadata: return canonical empty user state and log a
  warning without question text or answers.
- Answer write failure: retain question and local selection; offer retry.
- Retake write failure: retain score section and previous state.
- Stale generation: return `409`, invalidate manifest, and load the revised
  quiz.
- Public access failure: follow phase 10's indistinguishable `404` policy.

Logs may include artifact ID, workspace ID, generation, user ID where existing
privacy policy permits, schema version, question count, active mode, operation,
duration, and failure category. Do not log question text, option text,
explanations, submitted answers, answer keys, or complete metadata maps.

## 14. Required checks

### 14.1 Schema and verification

- representative valid quizzes, Unicode, and supported LaTeX pass;
- 5, 10, and 30-question quizzes pass;
- 4 and 31-question quizzes fail;
- default-count behavior creates exactly 10 questions in generation guidance;
- invalid UTF-8, BOM, duplicate keys, non-standard constants, unknown fields,
  wrong types, nulls, unsupported schema versions, and control characters fail;
- every option array with length other than four fails;
- empty and duplicate options fail;
- non-integer and out-of-range correct indexes fail;
- duplicate normalized questions fail;
- malformed LaTeX delimiters and braces fail;
- valid verification records `visual="not_required"` and no rendered fields;
- no conversion, rasterization, preview, or vision call occurs;
- generic JSON and flashcard JSON never receive quiz behavior without explicit
  `format="quiz"`;
- post-verification byte changes cannot save.

### 14.2 Projection and persistence

- validated JSON projects to stable readable Markdown;
- projection contains all questions, options, correct answers, and explanations;
- ordinary text is escaped while supported LaTeX is preserved;
- caller-supplied Markdown cannot override the projection;
- save creates one document, one `Artifact(format="quiz")`, one JSON primary,
  and no preview;
- receipt hash, primary bytes, projection, and artifact format refer to the same
  accepted input;
- search, citations, Git projection, and revision context use the derived
  Markdown through the ordinary document path;
- revision replaces JSON and projection atomically, increments generation,
  clears quiz state, and purges the superseded blob.

### 14.3 Per-user state

- manifest exposes only the authenticated user's sanitized state;
- one user's answer and retake never change another user's state;
- client-supplied user identity is impossible;
- answer indexes and selected option indexes are bounded;
- an identical answer retry is idempotent;
- a different replacement before retake returns `409`;
- stale generation returns `409`;
- wrong format, workspace, artifact, permission, and active scope fail closed;
- answer writes preserve unrelated metadata and content timestamps;
- state digest varies authenticated ETag after valid mutation;
- malformed, stale, or cross-generation metadata degrades to canonical state;
- concurrent different-user writes merge under the row lock;
- content revision clears all quiz users only after commit;
- format-switch revision cannot retain stale quiz or flashcard interaction
  namespaces.

### 14.4 Retake semantics

- incomplete runs cannot retake;
- `Retake missed` is unavailable with a perfect score;
- backend, not client, computes missed indexes;
- `Retake missed` clears only incorrect answers and preserves correct answers;
- missed scope is canonical, unique, in range, and persisted;
- closing and reopening resumes at the first unanswered missed question;
- finishing a missed retake computes score across the complete quiz;
- repeated missed retakes use the latest answers;
- `Retake all` clears every answer and restores canonical full scope;
- retake writes do not revise content, reindex, write Git, or create history.

### 14.5 Frontend

- semantic quiz dispatch wins over generic `application/json`;
- shared Spinner is the complete pre-validation loading state;
- invalid or oversized primary shows shared fallback;
- exactly four radio options render;
- submit is disabled without selection and while pending;
- successful authenticated submission advances only after server success;
- failed submission retains selection and question;
- score is absent until every active question is answered;
- score counts and percentage derive correctly;
- missed list uses original question numbering;
- review traverses every question one by one and cannot mutate state;
- review identifies selected and correct options without color alone;
- perfect-score state omits or disables `Retake missed`;
- no shuffle, skip, separate reset, download, or follow-up-generation controls
  render;
- desktop and mobile use the same component;
- mobile controls do not drag-dismiss the drawer;
- public mode provides local taking, score, review, and retake without network
  mutations;
- public refresh clears local quiz progress.

### 14.6 Routing and regression

- explicit quiz, MCQ, and scored-test prompts load the quiz skill;
- unspecified count routes with default 10;
- requested counts 5–30 are preserved;
- out-of-range counts block rather than clamp;
- flashcard, survey, questionnaire, poll, form, summary, mind-map, and
  interactive-calculator intents retain their existing routes;
- roster and revision instructions advertise quiz;
- `save_artifact` remains the only save and completion-emission path;
- PDF, DOCX, PPTX, XLSX, HTML, mindmap, flashcards, Markdown, media, fallback,
  authenticated, and public behavior remain green.

## 15. Delivery order

1. Extract and regression-test shared text/LaTeX validation and rendering
   without changing the flashcard contract.
2. Add the closed Pydantic quiz model, strict decoder, duplicate guards,
   deterministic Markdown projection, and focused fixtures.
3. Register the quiz adapter, typed format, no-vision verification, and signed
   primary-hash receipt.
4. Add the quiz skill, intent routing, roster entry, revision instructions, and
   execute-to-verify-to-save coverage.
5. Add pure per-user quiz-state normalization, scoring, answer, and retake
   transitions with metadata isolation tests.
6. Add authenticated manifest state, ETag variation, row-locked answer and
   retake mutations, and revision cleanup.
7. Add lazy semantic viewer states for taking, score, review, and retake;
   connect authenticated persistence and phase 10 public local state.
8. Add desktop, mobile, public, accessibility, failure, and cross-format
   regression coverage.
9. Update the authoritative artifact architecture and phase status after the
   implementation satisfies exit criteria.

Each step leaves one artifact path. If implementation requires a quiz table,
new save tool, alternate panel, public mutation route, separate search leg,
duplicate Markdown source, or MIME-based JSON dispatch, stop and repair the
adapter or interaction-state boundary.

## 16. Exit criteria

1. Quiz intent generates one strict version-one JSON quiz through the existing
   execute, verify, and save flow.
2. An omitted count creates exactly 10 questions; valid artifacts contain
   5–30 questions.
3. Every question contains exactly four distinct normal-text/LaTeX options and
   exactly one correct option.
4. Verification is deterministic, signed, primary-hash-bound, programmatic,
   and never invokes conversion, preview generation, rasterization, or vision.
5. The exact verified JSON is the primary semantic source and produces the only
   trusted searchable Markdown.
6. The authenticated viewer persists submitted answers and retake scope only
   for the authenticated user.
7. Score appears only after the active run is complete and is derived across
   the full quiz without persisted score fields.
8. Review walks all questions one by one, shows submitted and correct answers
   with explanations, and performs no mutation.
9. `Retake missed` clears only currently incorrect answers; `Retake all` clears
   every answer; neither creates attempt history.
10. The viewer exposes no shuffle, skip, separate reset, download, partial
    credit, or multi-select behavior.
11. Public quiz interaction uses the same viewer with visit-local state and
    cannot read or mutate authenticated progress.
12. Revision increments generation and atomically removes every user's stale
    quiz state.
13. No Alembic migration, new persistence model, dedicated quiz save tool,
    second panel, public progress API, analytics system, or new rendering
    dependency exists.
14. Existing artifact formats, authenticated routes, phase 10 public access,
    indexing, search, citations, revision, deletion, and fallback behavior
    remain green.
