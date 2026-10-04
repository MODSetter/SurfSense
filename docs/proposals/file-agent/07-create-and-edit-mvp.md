# Create and edit: the first slice

> A user asks the agent in chat for a Word or PDF document, sees it appear in Studio, and refines it turn by turn: each turn makes a new version, and the user can switch between versions. The agent writes the document as a Python script, SurfSense runs it without asking and keeps it, and the next edit changes the script. Documents carry images from the user's sources and charts. Studio's own Word and PDF buttons stay as they are today. The first file is never the user's own source, and nothing promises to keep a source's styles. Giving Studio a script path for strong models and a Markdown path for small ones, each with a one-call Refine, comes [after the slice](#after-the-slice).

This slice is built first, on `dev_mod`, which is synced with `dev` every few hours and merged into `dev` when the slice is ready, ahead of the milestones in the [README](README.md). It follows [ADR 0039](../../adr/0039-document-scripts-run-without-approval.md). Facts were checked against `dev_mod` at `0847e12f7` on 3 Oct 2026.

## What the user sees

**With an agent-capable model (Claude on the user's key), in one chat thread:**

1. "Draft a two-page client proposal from these sources as a Word document, with a pricing table." The agent searches the sources, writes a script and runs it. A "Created *Client proposal* v1" step appears in the chat, and the document opens in Studio.
2. "Make the executive summary shorter, add a timeline table and a bar chart of the yearly costs, and put our logo on the cover." The agent reads its script, finds the logo among the sources' images, changes the script and runs it again: v2 opens, and the chat says in a line what changed.
3. "Now a PDF version for the client." The agent writes a PDF script: a new artifact, v1 of its own.

If a script fails three times in a row, the agent stops and tells the user what failed instead of trying again.

**In Studio:** the Word and PDF buttons work as they do today. Their two paths and a Refine box under the document ("shorter, more formal") come [after the slice](#after-the-slice).

**On every versioned artifact:** a version switcher (v1, v2, v3) in the viewer. This is the whole "what changed" view in this slice; a redline between versions is later work.

## Today

- The agent runs only behind developer switches: opencode is staged only when `SURFSENSE_LOCAL_OPENCODE_ENABLED=1` is set, and a model off the empty tested list gets it only with `SURFSENSE_LOCAL_AGENT_UNTESTED_MODELS=1` ([agent](../../architecture/agent.md)).
- The agent's tools are `surfsense_search_sources` and `surfsense_create_artifact`, which starts a Studio job and returns at once with no artifact id ([`tool_endpoint/`](../../../surfsense_local/backend/modules/agent/tool_endpoint/)). A tool's `run` executes inside a database transaction, and a test pins the tool list and its flat schemas.
- `bash` is `ask` and `skill` is `deny` ([`opencode_config.py`](../../../surfsense_local/backend/modules/agent/opencode_config.py)).
- Studio's Word, PowerPoint, Excel and PDF formats ask the model for a Python script and run it with `exec()` on a thread in the worker, under a 120-second `thread.join` that cannot stop it ([`office/runner.py`](../../../surfsense_local/backend/worker/studio/office/runner.py)). The script is thrown away.
- Studio's Summary is Markdown already: the model's reply is the artifact's body ([`summary/pipeline.py`](../../../surfsense_local/backend/worker/studio/content/summary/pipeline.py)).
- Regenerate overwrites an artifact's files and body, and `artifact_files` holds one file per role (`primary`, `preview`) ([studio](../../architecture/studio.md)).
- [`worker.py`](../../../surfsense_local/backend/worker.py) already takes one non-queue flag, `--check-vision-runtime`.
- The worker binary contains python-docx, python-pptx, xlsxwriter, ReportLab and lxml ([`worker.spec`](../../../surfsense_local/backend/bundling/worker.spec)). `markdown-it-py` is in the lock through `rich`, and numpy and Pillow are in it too. matplotlib is not.
- Ingestion keeps only the text Docling extracts. [`parsing.py`](../../../surfsense_local/backend/worker/ingestion/parsing.py) converts with OCR and table structure on and returns `export_to_markdown()`, so every figure becomes a placeholder and its image is dropped. Image files (`.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp`) are accepted as sources, and every source's original file is kept ([`storage.py`](../../../surfsense_local/backend/modules/documents/storage.py), [documents](../../architecture/documents.md)).

## Decisions

1. **Two specs, one artifact model.** An artifact made in this slice keeps its source in `artifact_metadata["spec"]` as `{"kind": "python", "text": ...}`, the document script. After the slice, Studio's Markdown path keeps `{"kind": "markdown", "text": ...}` under the same key (decision 7). Every edit produces a new spec and renders it. *Reason:* the source is what an edit changes. Without it, an edit means patching the produced file, which is what makes Office edits fragile.
2. **Versions are linked artifacts; there is no migration.** Each version is a new artifact. Its `artifact_metadata["version"]` holds `{"root": <first artifact id>, "number": n, "parent": <artifact id>}`. The Studio list shows each root once, with its newest version, and the viewer switches between versions. *Reason:* `dev_mod` syncs with `dev` every few hours, and a schema change there would collide with migrations landing on `dev`. The `artifact_versions` table in [03](03-editable-artifacts.md) replaces this later, and its backfill can read these keys.
3. **Document scripts run in a separate process, through the worker.** The worker gains `--run-document-script <folder>`. The folder holds `script.py` and an `images/` folder with copies of the images the call names (decision 10). The process runs the script with `OUTPUT_PATH` set to a file in that folder, `IMAGES_DIR` set to `images/`, matplotlib on its non-interactive `Agg` backend with its cache folder in a temporary directory, and the folder as its working directory. When packaged, the worker launches its own binary in that mode; in development, the backend's Python. The parent kills the process at 120 seconds and reads back the file, the exit status and the last lines of any traceback. *Reason:* a process can be killed where a thread cannot, and the frozen worker already holds the libraries, so no new runtime ships in this slice.
4. **The agent gets three tools and loses the shell.**
   - `surfsense_render_document` takes `title`, `format` (`docx` or `pdf`), `script`, an optional `artifact_id` to make the next version of, and an optional `images` list naming images from `surfsense_list_images`. It runs the script and returns the new artifact's id and version, the page or paragraph count, and the first lines of the text, or the error and traceback to fix.
   - `surfsense_read_document` takes an `artifact_id` and returns the newest version's spec and number.
   - `surfsense_list_images` takes `source_ids` and returns each usable image's name, its source and its size in pixels (decision 10).

   `bash` becomes `deny` (ADR 0039).
5. **The tool waits for the result, outside any transaction.** `surfsense_render_document` creates the pending artifact in one short transaction and enqueues a Studio job that runs the script. It then waits up to 150 seconds, polling the artifact's status without holding a transaction. The workspace's tool server registers with a 180-second timeout. *Reason:* the agent needs the error to fix its script, and a long transaction blocks every other write (SQLite `BEGIN IMMEDIATE`, 5-second busy timeout).
6. **One SurfSense skill teaches the agent the script contract.** `surfsense-documents` is SurfSense's own text, not Anthropic's. It covers the `OUTPUT_PATH` and `IMAGES_DIR` contract, which libraries exist (python-docx, ReportLab, matplotlib), the habits that keep documents clean (built-in heading styles, real tables, no literal bullets, page size, a chart saved as a PNG and then placed), and how to edit: read the script, change what the instruction asks, run it again. It also holds the stop rule (decision 13). It loads through `skills.paths`, with `skill` set to `{"*": "deny", "surfsense-documents": "allow"}` and an `external_directory` allow for the skills folder. The agent prompt names the two tools in a few lines and stays under its 4,000-character test.
7. **After the slice, Studio's Word and PDF take two paths.** In this slice they keep today's code path. After it:
   - **Strong models** keep writing the Python script they write today. It runs through the script runner instead of `exec()` and is kept as a `python` spec, so the next version can change it.
   - **Small models** write Markdown, as Summary does, and committed builders render it. `markdown-it-py` parses it into headings, paragraphs, lists, tables, emphasis, links, images (decision 10) and chart blocks (decision 11). A python-docx builder writes the Word file and a ReportLab builder writes the PDF, each in its library's default look (decision 12).
   - **Which models count as strong** is a rule with no reliable signal yet. It will come from the measured capability in [05](05-model-ladder-and-evals.md#4-the-capability-profile).
   - PowerPoint and Excel take the same two paths: a script on the runner for strong models, and for small models a builder from a flat spec once it scores at least the script path's baseline on that model.

   *Reason:* code-written Word and PDF is proven today, and strong models write that code well. Writing Markdown is a single call that small models do well, and the builders return ADR 0010's rule to that path.
8. **After the slice, Refine is one call on either path.** `POST /artifacts/{id}/refine` takes `{instruction}`, creates the next version as a pending artifact, and runs a Studio job. On the Markdown path, the job sends the current Markdown and the instruction, gets the whole revised Markdown back, and renders it. On the code path, it sends the current script and the instruction, gets the whole revised script back, and runs it through the runner. Nothing is patched or diffed. A spec longer than the selected model's window is refused with a reason. In this slice, the agent's documents are refined in chat.
9. **The video runs from a development build.** Stage opencode with `SURFSENSE_LOCAL_OPENCODE_ENABLED=1`, start the API with `SURFSENSE_LOCAL_AGENT_UNTESTED_MODELS=1`, and connect Claude with the user's Anthropic key as an OpenAI-compatible connection. Shipping the agent to users waits for the milestones.
10. **Ingestion keeps each source's figures.** Docling's layout model already finds the figures on a PDF page, drawn charts and figures in scans included, with their captions. Its Word and PowerPoint readers return the pictures those files embed.
    - **Turning it on:** `parsing.py` turns on `generate_picture_images` at an `images_scale` of 2. After converting, it saves each figure as a PNG with its caption, page and size, before exporting the Markdown.
    - **Where figures live:** beside the source's original, in `figures/<n>.png` with a `figures.json` index, inside the document's own folder. Deleting the source deletes them, and no table or migration is needed.
    - **Image files:** a source that is itself an image (a logo, a photo) is its own single figure.
    - **Sources ingested before this change** have no `figures.json`. The first `surfsense_list_images` call on one queues a figures-only pass on the ingest queue and answers that its figures are being extracted.
    - **Using them:** each figure is named `<source id>-<n>` and converted to PNG with Pillow, since python-docx and ReportLab do not both read WebP or every TIFF. The agent finds figures through `surfsense_list_images`, which returns each one's name, caption, page and size, and the runner copies the ones a call names into `images/`.
    - **In a Markdown spec**, after the slice (decision 7), a figure is an ordinary Markdown image whose target is `image:<source id>-<n>` and whose alt text is its caption. Studio's Markdown prompt lists the selected sources' figures with their captions so the model can place them. The builders resolve each one and scale it to the page width, and one they cannot resolve becomes its caption in italics.
    - **Cost:** rendering figures makes ingest slower and uses more memory. The first build measures both on a 50-page report with charts and on a scanned PDF before this lands.
11. **Charts are matplotlib.** matplotlib becomes a backend dependency and is frozen into the worker with its data files. A document script draws a chart, saves it as a PNG beside `OUTPUT_PATH` and places it. After the slice, a Markdown spec carries a fenced `chart` block holding a small JSON object: `type` (`bar`, `line` or `pie`), `title`, `labels`, and `series` as a list of `{name, values}`. The builders draw it with matplotlib and place the PNG. A chart block that does not parse or match becomes a table of its data, with a note, so the document still renders.
12. **The builders use their libraries' default look.** They come after the slice (decision 7). The Word builder starts from python-docx's default template and its built-in Heading, List and Table Grid styles. The PDF builder uses ReportLab's sample stylesheet on A4 with 2 cm margins. *Reason:* the easiest theme to add is none; one visual theme comes later.
13. **Three failed runs stop the agent.** After a third failed run of `surfsense_render_document` for the same request, the agent stops, tells the user what failed in a sentence, and waits for their next message. The rule is in the skill, and every failed tool result repeats it: "If this is your third failed run for this request, stop and tell the user what failed."
14. **The agent looks at what it made.** After a successful run, `surfsense_render_document` renders up to four pages of the new version to PNG at 1,000 pixels wide, writes them to `outputs/previews/<artifact id>-v<n>/`, and returns their paths. The skill tells the agent to open them with opencode's `read`, which passes an image to the model as an attachment. It should check v1, and any version whose layout changed, against what the user asked: overflowing tables, images out of place, empty pages, unreadable charts.
    - **PDF:** pypdfium2, already in the worker, renders the pages.
    - **Word:** the app has no converter, so Electron renders the file in a hidden window with docx-preview, the library the in-app viewer uses, prints it to PDF with `webContents.printToPDF`, and pypdfium2 renders that. The API queues a render request, Electron polls for it as it polls for the image runtime today, and posts the PDF back. The check therefore shows the document as the app's viewer shows it, not as Microsoft Word lays it out. The Docker stack has no Electron, so it offers no Word preview.
    - **Only models that read images get previews.** Studio does no self-check in this slice.

## The pieces

Every piece here serves the video; S4 and S5 are [after the slice](#after-the-slice).

| # | Piece | Where | Agent time, rough |
|---|---|---|---|
| S1 | Script runner: worker flag, process, timeout, output read-back; `bash: deny` | `worker.py`; new `worker/document_script/`; `modules/agent/opencode_config.py` | 2–3 h |
| S2 | Agent tools, Studio job for script specs, version keys, registration timeout, skill and prompt lines | new `modules/agent/tool_endpoint/render_document.py` and `read_document.py`; `offered_tools.py`; `registration.py`; new `modules/agent/skills/surfsense-documents/SKILL.md`; `opencode_config.py`; `prompts/agent.md`; `worker/studio/job.py`; `bundling/api.spec` | 3–4 h |
| S3 | Version switcher and lineage in the Studio list; chat step lines that open the artifact | `frontend/src/features/studio/`; `frontend/src/features/agent/` | 3–4 h |
| S6 | Development setup and the demo script | a short how-to beside this file | 1 h |
| S7 | Source figures: kept at ingest with captions, the figures-only pass for older sources, listing, PNG conversion, copying into the runner folder | `worker/ingestion/parsing.py`; new `worker/ingestion/figures/`; new `modules/documents/source_figures/`; new `modules/agent/tool_endpoint/list_images.py`; the runner | 5–7 h |
| S8 | Charts: matplotlib dependency and freezing, the skill's chart guidance | `pyproject.toml`; `bundling/worker.spec`; the skill | 2–3 h |
| S9 | Self-check previews: PDF pages through pypdfium2; Word through a render request the API queues and Electron serves in a hidden window with docx-preview and `printToPDF`; preview paths in the tool result; the skill's checking guidance | the runner; new `modules/agent/previews/`; new `electron/src/main/docx-snapshot/`; a snapshot page in `frontend/`; the skill | 5–7 h |

Order: S1, S2, S3 and S6 make the video and come first. S7, S8 and S9 follow, because the video's second turn uses a logo and a chart and the agent checks its pages. In total, roughly two and a half days of agent work. These estimates are rough.

The first thing to test is whether an image the agent opens with `read` reaches Claude through SurfSense's model endpoint and Anthropic's OpenAI-compatible API. Self-checking depends on it, and nothing has run that path yet.

matplotlib adds its own packages (contourpy, kiwisolver, fonttools, cycler, pyparsing, python-dateutil) to an installer that already carries numpy and Pillow. Their size is measured in the first packaged build against the installer's size gate ([04](04-runtime-and-packs.md)).

## Tests

- **Runner:**
  - A script that writes `OUTPUT_PATH` returns its bytes.
  - A script that raises returns its traceback.
  - A script that sleeps past the limit is killed, and the process is gone.
  - A script that rewrites or deletes its own `script.py` does not change the spec SurfSense stored before the run.
- **Tools:**
  - `render_document` with a valid python-docx script makes a ready v1 whose spec is the script.
  - With `artifact_id`, it makes v2 with the same root.
  - A failing script returns the error and makes no ready artifact.
  - `read_document` returns the newest spec.
  - Ingesting a PDF with a drawn chart and a caption saves that chart as a figure with its caption and page; a scanned PDF's figure is saved too; a `.docx` with a pasted picture yields it; an image source is its own figure.
  - `list_images` on a source ingested before this change queues the figures-only pass and says so; on a newer source it lists every figure with its caption, and a script given one finds it in `IMAGES_DIR`.
  - Deleting a source removes its figures.
  - A script that draws a matplotlib chart and places it in a Word file renders with no display attached.
  - Every failed result carries the stop sentence.
  - A successful PDF run returns up to four page images that open with `read`; a Word run does the same through the Electron snapshot, and without Electron it returns no previews and says why.
  - The tool list test is updated for the three new tools and stays flat.
- **Config:** `bash` is `deny`; only `surfsense-documents` is allowed as a skill; the skills folder is readable.
- **Packaging:** the frozen worker imports matplotlib and draws a chart on a clean machine.
- **Frontend:** the switcher lists a root's versions and opens each; a new version selects itself.

## After the slice

Studio's Word and PDF get the two paths of decisions 7 and 8 once the slice has merged. Until then they work as they do today.

- **S4, Markdown builders** (7–9 h): python-docx and ReportLab builders for Markdown; Studio's `docx` and `pdf` pipelines given the Markdown path; `image:` references in the builders and the figure list in Studio's prompt (decision 10); the `chart` block with its table fallback (decision 11). In new `worker/studio/office/markdown/`, the `worker/studio/office/` pipelines and `pyproject.toml` (`markdown-it-py` named directly).
- **S5, Refine** (3–4 h): the route, the job and the box, with the Markdown rewrite. In `modules/artifacts/`, `worker/studio/` and `frontend/src/features/studio/`.
- **The code path and its Refine:** Studio's script for strong models runs through the runner and is kept as a `python` spec, and Refine rewrites that script in one call. [ADR 0039](../../adr/0039-document-scripts-run-without-approval.md) already moves Studio's Office formats onto the runner. Not estimated yet.
- **The strength rule:** which models take the code path. No reliable signal exists yet; it will come from the measured capability in [05](05-model-ladder-and-evals.md#4-the-capability-profile).

Their tests:

- **Builders:**
  - Markdown with headings, nested lists, a table and emphasis renders to a Word file and a PDF whose extracted text holds every heading and cell.
  - An `image:` reference places the picture; an unknown one becomes its caption.
  - A valid `chart` block places a chart; an invalid one becomes a table of its data.
- **Refine:**
  - A scripted model reply produces v2 with the revised Markdown, and v1 is unchanged.
  - A scripted model reply with a revised script produces v2 through the runner, and v1 is unchanged.
  - A too-long spec is refused with its reason.
- **Frontend:** the Refine box is shown on Studio's Word and PDF artifacts.

## What this changes

- [ADR 0028](../../adr/0028-model-written-code-runs-with-approval.md) is superseded in part by ADR 0039.
- In the [agent proposal](../agent/README.md), shells are no longer approved per command: the agent has none.
- Studio's four Office formats stay on the `exec()` path in this slice. After it, Studio's Word and PDF leave it, for the runner on strong models and the Markdown builders on small ones (decision 7); PowerPoint and Excel move onto the runner too, and to builders on small models once a builder matches the script path there.
- The README's milestones absorb this slice afterwards: [03](03-editable-artifacts.md)'s `artifact_versions` replaces the linked-artifact versions, and [02](02-skills-and-engines.md)'s engines stay the path for editing a user's own file.

## Open questions

- Should chat answers and search also use figure captions, so "the revenue chart on page 4" finds its figure? This slice keeps captions only for the agent.
