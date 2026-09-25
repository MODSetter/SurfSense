# Studio

Studio turns a selection of sources into a deliverable: a summary, a Word document, slides, a spreadsheet, a web page, a PDF, a mind map, flashcards, a quiz, a podcast, an image or an infographic. The user picks a format and sources and may add a prompt; a background job has the selected model write the content, and the app renders it, as a file for ten of the twelve formats. DOCX, PPTX, XLSX and PDF are rendered by model-written code instead (Known gaps). Each result is an ordinary `ARTIFACT` document, searchable and citable like any source, with a sidecar row for the format and the bytes.

**Code:** [`modules/artifacts/`](../../surfsense_local/backend/modules/artifacts/), [`worker/studio/`](../../surfsense_local/backend/worker/studio/), [`frontend/src/features/studio/`](../../surfsense_local/frontend/src/features/studio/)
**Decisions:** [ADR 0003](../adr/0003-artifacts-as-documents.md), [ADR 0008](../adr/0008-two-job-queues.md), [ADR 0010](../adr/0010-studio-builders-not-sandboxes.md), [ADR 0028](../adr/0028-model-written-code-runs-with-approval.md)

The tables, `artifacts` and `artifact_files`, are in [`data-model.md`](data-model.md#artifacts-and-artifact_files).

## The job seam

[`service.py`](../../surfsense_local/backend/modules/artifacts/service.py)`::create_artifact_job(session, workspace, payload, *, tool_call_id=None)` is the one entry for every trigger. The REST route passes no `tool_call_id`; a chat tool would pass its own, and nothing else would differ. Explicit now, agentic later, same code. No chat tool calls it yet.

1. Look the format up in the catalog (`422` if unknown) and check that it is available (`409` with the reason if not).
2. Resolve the sources: at least one (`422`), all in this workspace (`422`) and all `ready` (`409`).
3. Validate the options with the format's `validate_options` hook. Only podcast has one; a bad brief is a `422`.
4. Create the `ARTIFACT` document, `pending` and titled with the format's label, and its `artifacts` sidecar with `generation` 1, `created_by_tool_call_id`, and the source ids, prompt and options in `artifact_metadata`.
5. Commit, then enqueue `studio_job(artifact_id)`.

Status lives on the document, not the sidecar, because ADR 0003 keeps indexing state on the `Document`. The worker moves it from `pending` to `processing` and then to `ready` or `failed`; a cancel makes it `cancelled`.

## Formats

The catalog is a tuple of twelve `Format` rows in [`formats.py`](../../surfsense_local/backend/modules/artifacts/formats.py), computed into availability on each request and never stored.

| Key | Label | Needs | Worker path | Stored file |
|---|---|---|---|---|
| `summary` | Summary | text_gen | `content/summary/` | none; the markdown is the artifact |
| `docx` | Word | text_gen | `office/` | `.docx` |
| `pptx` | Slides | text_gen | `office/` | `.pptx` |
| `xlsx` | Spreadsheet | text_gen | `office/` | `.xlsx` |
| `html` | Web page | text_gen | `web/html/` | `.html` |
| `pdf` | PDF | text_gen | `office/` | `.pdf` |
| `mindmap` | Mind map | text_gen | `content/mindmap/` | none; the outline is the body |
| `flashcards` | Flashcards | text_gen | `content/flashcards/` | deck JSON |
| `quiz` | Quiz | text_gen | `content/quiz/` | quiz JSON |
| `podcast` | Podcast | text_gen, audio_gen | `media/audio/podcast/` | WAV audio |
| `image` | Image | image_gen, text_gen | `media/visual/image/` | the image |
| `infographic` | Infographic | image_gen, text_gen | `media/visual/infographic/` | the image |

- `requires_model_types` is a tuple in the order the pipeline's `render()` takes its models. A format is available when every required model type has a selection; otherwise the reason names every missing one in a fixed reading order: "Needs a chat model", "Needs an image model", "Needs an audio model", or two of them joined, as "Needs a chat model and an audio model". Naming only the first missing type made selecting it look like the gate moving to the other.
- `podcast` needs its `audio_gen` model on this computer: an audio model chosen from a server is refused with "Needs an audio model on this computer", because nothing calls a remote speech endpoint yet. Opening a podcast brief without an audio model answers `409` with "Needs an audio model". The app ships Kokoro and chooses it at startup when no audio model is chosen, so that answer needs the choice cleared since the last start, or a build without audio.cpp ([`local-models/selection.md`](local-models/selection.md)).
- Which formats are available is the server's answer to what is selected, so the panel asks again whenever the chat selection changes or the settings dialog closes, since the image model is chosen inside settings and nothing else reports it.
- An image selection can resolve to the bundled sd-server as well as to a remote connection, so needing an image model does not mean needing a key or a network.
- [`tests/unit/worker/test_studio_job_router.py`](../../surfsense_local/backend/tests/unit/worker/test_studio_job_router.py) asserts that `job_router.py` names every catalog key and nothing else, that each key has a pipeline, and that each pipeline takes its models, the sources, the prompt and, for a format with options, the options.

## The builder rule, and where it is broken

The rule ([ADR 0010](../adr/0010-studio-builders-not-sandboxes.md)): the model writes structured content, and a committed builder for that format renders it. Nothing the model wrote executes on the user's machine, so a bad reply is malformed JSON rather than arbitrary code, and there is no sandbox, no Docker and no receipt to verify. That is what lets Studio fit an offline app with weak local models. [ADR 0028](../adr/0028-model-written-code-runs-with-approval.md) has since allowed model-written code to run on the user's machine without a sandbox; the builder rule still describes the eight formats below.

Eight formats follow it:

- **summary**: the model's markdown is the body, titled by its first `# ` heading.
- **mindmap**: JSON nodes, at most 10 branches, become a markdown outline, an H1 over nested bullets, which Markmap draws on the client and which stays readable as text.
- **flashcards**: JSON cards, at most 20, become a deck JSON file and a markdown body.
- **quiz**: JSON questions, at most 10, each kept only with exactly four options and an answer among them, become a quiz JSON file and a markdown body.
- **html**: a JSON title and sections, at most 10. Every value is HTML-escaped into a fixed template, so the page cannot carry a script.
- **podcast**: the model outlines the episode from the brief, then drafts it segment by segment; the chosen audio model voices every line through audio.cpp's server, and the transcript is the body.
- **image**: the model writes a title and an image prompt, and the image model paints the prompt.
- **infographic**: the model writes a factual brief (a title, a summary and up to 8 sections of label, value and detail), and the image model paints a prompt built from it in a fixed sketchnote style.

Four formats break it. DOCX, PPTX, XLSX and PDF go through `office/`: the tier prompt asks the model to "write one standalone Python script" for the format's library (python-docx, python-pptx, xlsxwriter or ReportLab), with a `SKILL.md` of authoring guidance beside each format, and [`office/runner.py`](../../surfsense_local/backend/worker/studio/office/runner.py) runs the reply with `exec()` on a thread in the worker process. The script must leave the file's bytes in `output_bytes` and may set `title` and `summary`. A failing script goes back to the model with its error, for up to three attempts. The 120-second limit is a `thread.join`: it bounds how long the job waits, but it cannot stop a thread that ignores it, and the code runs with the worker's privileges. The module says so and names an out-of-process sandbox runner as the way up.

There is no Electron `printToPDF` and no ffmpeg in `surfsense_local`. A PDF is ReportLab through that path, and a podcast is one `audio/wav` joined from audio.cpp's WAV for each turn.

## Voicing a podcast

[`providers/audiocpp/`](../../surfsense_local/backend/modules/llm/providers/audiocpp/) voices a podcast with the `audio_gen` model, an audio.cpp build installed in the audio folder ([`local-models/catalog.md`](local-models/catalog.md)):

- **The voices are the model's roster**, from its manifest entry: each voice with the languages it speaks, one for a Kokoro or Kitten voice and all 31 for a Supertonic voice. The brief's language list and each speaker's voice picker come from it, the picker grouped into female and male voices. The brief opens in American English where a voice speaks it, else in any English, else in the roster's first language, and a remembered brief the chosen model cannot voice falls back to that.
- **Memory is checked before anything loads, twice.** The worker compares the operating system's available memory (`MemAvailable` on Linux, free plus inactive pages on macOS, `GlobalMemoryStatusEx` on Windows) with the model's peak measured while voicing with every chunk of text full, from its entry, plus 1 GiB, and refuses short of it: "Voicing needs about 3.5 GB free; this computer has 1.8 GB. Supertonic 3 needs about 1.6 GB." The second sentence names the first other curated audio model, in the manifest's order, that would fit, and is left out when none would. It checks first, before the chat model drafts anything, so a machine that cannot voice the episode does not spend minutes writing it. It checks again at voicing, because the chat model's own memory may have changed the answer. audio.cpp's own guard counts only the file it reads.
- **One speech request per turn**, with the turn's voice. The brief's language goes in the request only for a voice that speaks several; a Kokoro voice's name already fixes its language. The turns are joined with 0.35 s between them.
- **A turn the server fails ends the episode with the server's own words**: "audio.cpp could not voice turn 3 of 40: unknown Kokoro voice id: nobody". The server was reached, so this is not "The model could not be reached", which stays for a server that does not answer.
- **The model is unloaded when voicing ends**, with `POST /v1/tasks/unload_all_models`, success or failure, so its memory is back before the chat model's next job. The server's five-minute idle unload is the backstop.

## Grounding

Studio does not call `retrieve()`. [`shared/gather.py`](../../surfsense_local/backend/worker/studio/shared/gather.py) loads the selected documents' markdown in selection order, up to 24,000 characters in total, and [`shared/generate.py`](../../surfsense_local/backend/worker/studio/shared/generate.py) sends it as one user message, each document under its title as a heading, after the format's system prompt. The code marks the flat cap as a ceiling, fine for summarising a handful of local documents, with retrieval scoped to the selection as the way up.

Each format keeps its prompts as markdown beside its code, one file per model tier, loaded for the selected model's tier ([`local-models/selection.md`](local-models/selection.md)). The user's prompt joins the system prompt as a "Focus on:" line.

## Layout of `worker/studio/`

```text
worker/studio/
├── job.py            one job: status, sources, models, render, persist
├── job_router.py     a format key to its render()
├── shared/           gather, generate, persist, artifact (Source, Built), text parsing
├── content/          summary, mindmap, flashcards, quiz
├── office/           docx, pptx, xlsx, pdf: a spec and SKILL.md each, plus prompt and runner
├── web/html/
└── media/
    ├── audio/podcast/    outline, draft, roster
    └── visual/           image, infographic
```

Every pipeline returns a `Built`: a `title`, the `markdown` that is always the indexed body, and an optional `primary` (and `preview`) with its MIME type and filename. Adding a format is a folder with a `render`, a `case` in `job_router.py` and a row in `formats.py`, plus the frontend entries below.

## Jobs

- `studio_job` runs on the `studio` Huey queue in `huey.db` with `retries=1`. `worker-studio` drains it with four threads, because the work mostly waits on a model ([ADR 0008](../adr/0008-two-job-queues.md)).
- A job ([`job.py`](../../surfsense_local/backend/worker/studio/job.py)) marks the document `processing` unless it was cancelled, gathers the sources, resolves one model per required model type, and commits before rendering, so no write lock is held across a generation that can take minutes. It checks for a cancel before and after rendering.
- [`persist.py`](../../surfsense_local/backend/worker/studio/shared/persist.py) sets the document's title and markdown, then chunks, embeds and indexes that body with the ingest code, so the artifact is searchable and citable. If the format has a file, it clears the artifact's folder and file rows and writes the file named by its role, recording its size and SHA-256. No pipeline writes a `preview` yet.
- The document is created without a `dedup_key`, so it is never deduplicated against another document.
- A failure rolls back and writes `failed` with a reason cut to 500 characters: the error's first line, or for an HTTP error its whole message after "The model could not be reached: ". The job is then re-raised for Huey's one retry, except an image error, since the endpoint may already have generated, and billed, an image, and a podcast refused for memory, since a retry would draft the episode again and refuse again.
- **Cancel** marks the document `cancelled` and revokes a queued copy. A running job stops at its next check. During a model call it checks every second, while tokens stream and while the model is still reading the prompt, and hangs up; closing the request stops llama-server within 1.5 seconds, measured through the router ([`generate.py`](../../surfsense_local/backend/worker/studio/shared/generate.py)).
- Every Studio model call turns thinking off. Measured on Qwen3 1.7B: with it on, a mindmap over a 12,000-token prompt thought past 15,000 tokens without answering, holding the runtime's only slot so chat queued behind it.
- **Regenerate** refuses a job still `pending` or `processing`, rechecks availability, resets the document to `pending`, clears the error, increments `generation` and re-enqueues with the same sources, prompt and options. The new run replaces the files and the indexed body; the artifact and its document keep their ids.
- Each transition the Studio worker makes sends an `artifacts` event keyed by artifact id; the API's own changes, to `pending` and `cancelled`, send none. The frontend does not listen yet; the artifact list refetches every 1.5 seconds while one is running ([`overview.md`](overview.md#freshness)).

## Routes

| Method | Path | Does |
|---|---|---|
| `GET` | `/workspaces/{workspace_id}/studio/formats` | the catalog, each format with `available` and `unavailable_reason` |
| `POST` | `/workspaces/{workspace_id}/studio/jobs` | `{format, document_ids, prompt?, options?}`; `201` with the artifact |
| `GET` | `/workspaces/{workspace_id}/studio/podcast/brief` | the podcast brief and voices to review before submitting |
| `GET` | `/workspaces/{workspace_id}/artifacts` | the workspace's artifacts, newest first |
| `GET` | `/artifacts/{artifact_id}` | detail: the body, the files, quiz or flashcard progress |
| `POST` | `/artifacts/{artifact_id}/regenerate` | run the job again; `202` |
| `POST` | `/artifacts/{artifact_id}/cancel` | stop a queued or running job; `409` if nothing is running |
| `GET` | `/artifacts/{artifact_id}/files/{role}` | stream the `primary` or `preview` file |
| `PUT` | `/artifacts/{artifact_id}/quiz-state/{answer\|skip\|retake}` | quiz progress |
| `PUT` | `/artifacts/{artifact_id}/flashcard-state/{mark\|reset\|order}` | flashcard progress |
| `DELETE` | `/artifacts/{artifact_id}` | delete the artifact, its rows and its files |

- The artifact routes are keyed on the artifact alone, since a local install has one user. An artifact's `status`, `title` and `error_message` are its document's.
- A prompt is at most 2,000 characters. A podcast brief holds a `language`, a `style`, a `duration` and one or more `speakers`, each with a name, a role and a voice.
- Files are served inline so a viewer can render or stream them, except `text/html` and `image/svg+xml`, which are forced to download so a generated page never runs on the API's origin.
- Quiz and flashcard progress is stored in `artifact_metadata`, scoped to the artifact's `generation`, so a regenerate starts a clean run.
- There is no manifest route; the viewer reads `GET /artifacts/{id}` and the file stream.
- `DELETE /artifacts/{id}` deletes the document, which cascades the sidecar, its file rows and its chunks, then removes `artifacts/<id>/` after the commit. This is ADR 0003's blob-purge obligation, on this route.

## Viewers

[`viewers/registry.tsx`](../../surfsense_local/frontend/src/features/studio/viewers/registry.tsx) maps every format key to a viewer, and a key without an entry falls back to the plain `DocumentViewer`, so a new format renders as raw content instead of breaking the panel.

| Format | Viewer |
|---|---|
| `summary` | the markdown, rendered with Streamdown |
| `docx` | rendered in the app with docx-preview |
| `pptx` | rendered in the app with `@aiden0z/pptx-renderer` |
| `xlsx` | parsed with ExcelJS |
| `pdf` | pdf.js |
| `html` | the file's text in an `<iframe sandbox="allow-scripts allow-popups">`, through `srcDoc` |
| `mindmap` | Markmap, with a fit control |
| `flashcards` | one card at a time, marks saved through `flashcard-state` |
| `quiz` | interactive, answers saved through `quiz-state` |
| `podcast` | an audio player over `files/primary`, with the transcript as markdown |
| `image`, `infographic` | a shared media viewer |

- The flashcard and quiz viewers are keyed on `id:generation`, so a regenerate remounts them with a clean run.
- The artifact panel offers a download for each file, except the JSON behind flashcards and quizzes.

## The Studio panel

- Studio lives in the right rail: pick a format, pick sources, add an optional prompt, generate. The source picker is the same included set as the sources panel, so chat and Studio share one selection. An unavailable format shows the API's reason.
- A podcast waits for its brief: the panel loads `GET .../studio/podcast/brief` and renders a form for style, duration and speakers before the job can be submitted.
- The artifact list shows each artifact with its status, and each row can be opened, regenerated, cancelled or deleted.

## The image path

- `image` and `infographic` resolve the `image_gen` selection. A remote selection loads its connection, which runs the egress check and decrypts the key. An `sdcpp` selection points the same client at the bundled sd-server's loopback URL, with no key and no egress decision, which is what makes an image possible on an offline machine.
- sd-server runs only while Studio needs it, because it keeps a model's weights in memory until it exits. The API answers Electron's poll from the jobs ([`local_image_demand.py`](../../surfsense_local/backend/modules/artifacts/local_image_demand.py)): the chosen model of the image type the oldest processing job needs; else, for 5 minutes after the last such job ended, the same one, so a second image does not reload it; else nothing, and Electron stops it. A cancel ends the window at once, since sd-server cannot stop a generation. The job waits up to 2 minutes for `/sdapi/v1/sd-models` to name its weights before it posts, and fails with a reason if sd-server never comes up.
- sd-server is launched with each file of the build on its flag and the model's reviewed `image` defaults as its own (`-W`, `-H`, `--steps`, `--cfg-scale`, `--sampling-method`, `--flow-shift`), since a request that carries none of them starts from the launch settings ([`local-models/catalog.md`](local-models/catalog.md)).
- The client posts `{model, prompt}` to `/images/generations`, falls back once to `/images` only on `404` or `405`, and remembers the route that worked for the life of the process. It accepts `b64_json`, a data URL or a URL, caps the sizes, and checks the bytes against the claimed MIME type ([`connections.md`](connections.md)).
- The `text_gen` model writes first in both formats. The markdown body is the image prompt or the brief, so an image can be found by what it shows.

## Known gaps

- A cancel reaches only the model call. Voicing a podcast, running office code and ingest's parsing and embedding run to the end of their step first, because jobs are threads that cannot be killed; stopping everything means running each job in a process the worker can kill.
- DOCX, PPTX, XLSX and PDF run model-written Python with `exec()` in the worker process, unsandboxed and without asking the user; the 120-second limit cannot stop a runaway thread.
- Grounding is the first 24,000 characters of the selected documents in selection order, not retrieval over them, so a large selection is cut off.
- A podcast is WAV. The design encodes MP3 with a bundled ffmpeg, which is not built.
- Deleting an artifact through `DELETE /workspaces/{id}/documents/{doc}` removes its rows but leaves `artifacts/<id>/` on disk; only `DELETE /artifacts/{id}` removes the folder.
- The format picker's list of keys is hard-coded in `studio-formats.ts`. The API's catalog fills in each listed format's details and availability, so a format added to `formats.py` is not offered until the frontend lists it too.
