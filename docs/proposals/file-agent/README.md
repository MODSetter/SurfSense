---
status: proposed
code:
  - document_skills/
  - surfsense_local/backend/shared/migrations.py
  - surfsense_local/backend/modules/folders/
  - surfsense_local/backend/modules/source_roots/
  - surfsense_local/backend/modules/source_scope/
  - surfsense_local/backend/modules/artifacts/
  - surfsense_local/backend/modules/engine_runs/
  - surfsense_local/backend/modules/workflows/
  - surfsense_local/backend/modules/jobs/
  - surfsense_local/backend/modules/llm/capability/
  - surfsense_local/backend/modules/llm/providers/anthropic_messages/
  - surfsense_local/backend/modules/llm/spend/
  - surfsense_local/backend/modules/runtime_packs/
  - surfsense_local/backend/modules/agent/
  - surfsense_local/backend/modules/workspaces/
  - surfsense_local/backend/worker/engines/
  - surfsense_local/backend/worker/workflows/
  - surfsense_local/backend/worker/studio/
  - surfsense_local/backend/scripts/job_eval/
  - surfsense_local/backend/bundling/
  - surfsense_local/electron/
  - surfsense_local/frontend/src/features/
  - surfsense_local/scripts/licenses/
  - surfsense_web/content/docs/v2/
  - surfsense_backend/app/license/
  - surfsense_backend/app/proprietary/
  - docs/contracts/03-export-bundle.md
  - .github/workflows/
---

# The file agent

> The user adds files, or a whole folder, as sources, makes outputs from them, and keeps editing those outputs, all on their own machine. Outputs are versions that only grow. A change to the user's own file arrives as a revised copy with tracked changes; the file itself is never written. Edits run on engines SurfSense ships: the model writes a plan as data, and the engine applies it, checks it and reports on every operation. There is one kind of workspace, and what it offers follows from the selected model's measured capability: a free 4B user gets grounded answers, Studio and step-by-step jobs, and a user with Claude on their own key also gets an agent that works on files. The engines are the maintainer's improved document skills, shipped after a scoped clean-room fix in M1. Today's gaps are fixed first, in M0, without waiting for it.

This is the entry point of the file-agent proposal. It extends the [agent proposal](../agent/README.md) and changes some of its locked decisions. The six stream files carry the design and its verified facts; this page resolves where they disagree, orders their phases, and lists what is left to the maintainer. The stream files were reconciled with this page on 3 Oct 2026. Facts were checked against `dev_mod` at `0847e12f7` on 3 Oct 2026. The workspace question went to a design panel of three proposals, and both judges chose P1 (48 points, against 38 to 41 for P2 and 40 for P3).

**The first slice comes before the milestones.** [07, create and edit](07-create-and-edit-mvp.md) is built first, on `dev_mod`, which syncs with `dev` every few hours: the agent creates a Word or PDF file in chat and refines it turn by turn through a document script it keeps. During the slice, Studio's buttons stay as they are today. It pulls reduced parts of M3 (versions) and M5 (the agent) forward, and it follows [ADR 0039](../../adr/0039-document-scripts-run-without-approval.md): document scripts run without approval in SurfSense's script runner, and the agent has no shell. Studio's Word and PDF change after the slice, into two paths ([07](07-create-and-edit-mvp.md#after-the-slice)): strong models keep today's code-written documents, which are proven, and small models write Markdown that committed builders render. Each path has its own one-call Refine, and a rule decides which models count as strong. No reliable signal for that rule exists yet; [05](05-model-ladder-and-evals.md)'s measured capability is where it will come from. Where 07 disagrees with the milestones below or with [02](02-skills-and-engines.md)'s Studio builders, 07 holds, including its two paths for Studio's Office formats after the slice, and the milestones are revised once the slice ships.

**First ladder results, 4 Oct 2026.** The slice's eight live cases pass on Claude Opus 5.5 and Sonnet 5.5. Haiku 4.5 passes five: in the other three it skipped the page previews the skill asks it to check. Through OpenRouter, Kimi K3 and Qwen3.8-27B pass all eight cases. Text-only GLM-5.3 and DeepSeek V4 Pro pass all but the case that needs image input. Smaller open models (Qwen3.6-35B-A3B, Gemma 4 31B, Ministral 14B, Qwen3.5-9B) fall short. The matrix, the causes and the columns still to run are in [08](08-model-ladder-results.md).

## Why now

- **Google ships the agent, the skills and the Office outputs.** Since 8 Jun 2026 NotebookLM notebooks on paid tiers (Ultra and business plans first, then Pro) have had "a secure cloud computer" with "more than 100 curated software skills", and it writes DOCX, XLSX and PPTX ([Google](https://blog.google/innovation-and-ai/products/notebooklm/better-research-notebooklm/)). On 16 Jul 2026 NotebookLM was renamed Gemini Notebook, and Google said the cloud computer would reach AI Pro on the web in the coming weeks ([Google](https://blog.google/innovation-and-ai/products/gemini-notebook/notebooklm-gemini-notebook/)). It still has no local sources and no source folders, only labels ([Workspace Updates](https://workspaceupdates.googleblog.com/2026/07/notebooklm-now-gemini-notebook.html)). An agent alone no longer sets SurfSense apart; local, folders and editable outputs still can.
- **Local execution is disappearing elsewhere.** From 6 Oct 2026, new Claude Cowork tasks on Pro and Max run in Anthropic's cloud ([Anthropic](https://support.claude.com/en/articles/15520349-use-claude-cowork-on-web-desktop-and-mobile)).
- **Editing the customer's file is now expected.** Claude for Word writes native tracked changes ([Anthropic](https://claude.com/docs/office-agents/word)). Microsoft's Word, Excel and PowerPoint agents reached general availability ([Microsoft](https://www.microsoft.com/en-us/copilot/blog/2026/04/22/copilots-agentic-capabilities-in-word-excel-and-powerpoint-are-generally-available/)), and its Word legal agent redlines against a playbook ([ComplexDiscovery](https://complexdiscovery.com/microsoft-puts-legal-agent-inside-word-sharpening-contract-review-competition/)). Nobody credible does that locally and privately.
- **The jobs businesses pay for are cloud-only.** Questionnaire, RFP and redline vendors sell an answer library and approvals, not file editing ([08-b2b-artifact-jobs](../../../plans/community-local/seo/08-b2b-artifact-jobs.md)).
- **The engines already exist.** The improved docx skill scores 1.00 on its evals against 0.29 for Anthropic's original, and contract-redline scores 77.7% with the skill against 0% without it ([02](02-skills-and-engines.md#the-skills-project)).

## The answer to the workspace question

Preload the mode from the model, and add no workspace types. The model is app-wide, so a workspace type could not carry a capability; a type would freeze today's limits into user data and ask a question new users cannot answer. Every benefit a type offered (folder roles, pinned jobs, a local-only policy, a review state) fits one workspace. `capability_of()` reads a reviewed, measured profile and decides engines, job levels, formats, edit options and skills. The interface never says "mode": each item carries one of four verdicts (Best on this model, Tested, Not measured, Not on this model) with its reason. A verdict only ever reflects eval rows and live gates; nothing else, such as a pending legal review, is shown as one. When a model allows both engines, a new thread offers "Answer" or "Work on files", so a 4B user never sees a locked control. The full answer, with the grafts taken from the two losing proposals, is in [06](06-product-shape.md#the-answer-to-the-maintainers-question).

## Workstreams

| Stream | File | Owns | Starts from |
|---|---|---|---|
| **Sources and folders** | [`01-sources-and-folders.md`](01-sources-and-folders.md) | the source scope on the server, the database snapshot before migrations, Library folders and Trash, linked disk roots and their OneDrive state, per-thread agent folders, `resolve_original` and `copy_original` | the 50-source fix, which needs no folders |
| **Skills and engines** | [`02-skills-and-engines.md`](02-skills-and-engines.md) | the clean-room fix, `document_skills/`, engine tools, the engines queue, SKILL.md files and per-job opencode agents, the structured playbook format, workflows, Studio builders, opencode config, the model endpoint | the clean-room fix (M1) |
| **Editable artifacts** | [`03-editable-artifacts.md`](03-editable-artifacts.md) | `artifact_versions`, `start_version` and the version jobs, Refine, selection edits, revised copies, apply reports, the sweep of agent outputs, export | versions, which depend on nothing |
| **Runtime and packs** | [`04-runtime-and-packs.md`](04-runtime-and-packs.md) | the frozen worker's libraries, the size budget, the licence gate and notices, fonts, the optional Office support download (LibreOffice), the plugin interpreter, Electron fuses | hygiene and the size gate, which depend on nothing |
| **Model ladder and evals** | [`05-model-ladder-and-evals.md`](05-model-ladder-and-evals.md) | the native Anthropic provider and passthrough, spend, `capability_of()` and `profiles.json`, the job × model matrix, including the free agent's tasks and one OpenAI and one Gemini column | the eval harness on local single calls |
| **Product shape** | [`06-product-shape.md`](06-product-shape.md) | verdicts and reasons, the Answer / Work on files switch, the job catalogue and roles, workspace settings, handoff, the self-attested review state, organization policy | a surface on 05's seam, with no rows yet |
| **Create and edit (first slice)** | [`07-create-and-edit-mvp.md`](07-create-and-edit-mvp.md) | the script runner, the agent's document tools and skill, source figures, charts, self-check previews, version lineage and the version switcher; after the slice, Studio's two Word and PDF paths, their Refines and the rule for which models count as strong | nothing; built first, on its own branch |
| **Model ladder results** | [`08-model-ladder-results.md`](08-model-ladder-results.md) | the slice's live cases run per model: the matrix so far, each failure's cause, what to change next and the columns still to run | the slice's live tests, on any model through `SURFSENSE_LIVE_MODEL` |

## Locked decisions of the agent proposal this changes

| Decision | Old | New | Why |
|---|---|---|---|
| Engines | Two: opencode for a model on a tested list, fixed workflows for every other model | Answers use the one-call chat engine on every model; a job runs as a job thread (opencode running a per-job agent that carries the job's skill) or a workflow; free-form file work runs on the free agent; the capability sets each level | Small models do single schema steps well and fail as agents ([05](05-model-ladder-and-evals.md#7-the-small-model-tier)) |
| Who gets opencode | Models on the tested list, which starts empty | Models whose measured capability grants it, plus unmeasured models the user confirms once, behind live gates | A boolean list cannot say how each job runs ([05](05-model-ladder-and-evals.md#4-the-capability-profile)) |
| When installers carry opencode | Once a model passes the agent test ([`enabled.mjs`](../../../surfsense_local/electron/scripts/opencode/enabled.mjs): `ENABLED_BY_DEFAULT = false`) | Since 7 Oct 2026 (`ENABLED_BY_DEFAULT = true`): the maintainer turned it on ahead of M5's `agent_smoke` and `free_agent_tasks` rows. A notarized macOS build carrying opencode is a macOS release gate; if notarization is still blocked, the agent ships on Windows and Linux first and the docs say so | No agent test exists to flip the switch ([agent](../../architecture/agent.md)); 05's rows replace it |
| Where the agent appears | The thread gets its engine from the selected model; "a quick question also goes through the agent" | The model decides which engines a thread may use; when both are allowed, the user picks Answer or Work on files at creation. A thread keeps its engine | Without prompt caching, every quick question would bill opencode's fixed prompt and tool definitions: an estimated 3–5K tokens in SurfSense's config (6–8K for stock opencode), to be measured from `usage.input_tokens` in M4 ([06](06-product-shape.md#threads-answer-and-work-on-files)) |
| Models | One SurfSense endpoint for every model | It stands, with two wires: chat completions, and an Anthropic Messages passthrough that refuses server tools | The compatibility layer drops caching, schemas and thinking ([05](05-model-ladder-and-evals.md#2-serving-claude-to-opencode)) |
| Model-written code | The agent asks before every shell command | Decided in [ADR 0039](../../adr/0039-document-scripts-run-without-approval.md): the agent's shell is denied for every model, and model-written document scripts run without approval in SurfSense's script runner, kept with the version they made. Studio's Office formats move onto the runner after [07](07-create-and-edit-mvp.md)'s slice. Studio's Word and PDF then take two paths ([07](07-create-and-edit-mvp.md#after-the-slice)): strong models keep code-written documents, and small models write Markdown that committed builders render | Approval dialogs for every command stop document work, and a bash allow-list is no boundary ([02](02-skills-and-engines.md#10-security)); code-written documents are proven on strong models; free users must not lose a format they have today |
| Undo | Not in this phase | Artifacts keep append-only versions, a restore makes a new version, and the user's file is never written | Competitors lost work to restores that rewrote history ([03](03-editable-artifacts.md#decisions)) |
| Out of scope | Editing sources or artifacts | In scope. A source is edited only into a revised copy, and every engine edit is tracked | The jobs that sell are edits to the customer's format ([08-b2b-artifact-jobs](../../../plans/community-local/seo/08-b2b-artifact-jobs.md)) |
| Sources on disk | A linked folder is indexed in place and watched | Library folders with a Trash, and read-only linked roots that never delete on unavailability, ask on a mass vanish and never read placeholders | Unplugged drives and sync clients look like deletion ([01](01-sources-and-folders.md#decisions)) |
| Installer and network | The installer downloads nothing; later fetches need consent | Stands; ADR 0041 adds pinned runtime packs after per-host consent, under one GitHub consent | Executable downloads are a new class and need a record ([04](04-runtime-and-packs.md#decisions)) |

"Shipping opencode" (1.18.x, pinned), "opencode and the network" and "The agent's conversation" stand. Working folders become per thread ([01](01-sources-and-folders.md#the-agent)).

## Milestones in order

Each milestone ships on its own as a 2.x point release; exit criteria use the eval matrix where they can. Scope and sizes are in the stream files.

**Shipping rule.** Something user-visible ships at least every 3–4 weeks. A milestone that runs longer ships its first finished part on its own: M6 the revised copy and its download before the redline job, M8 a linked folder that reconciles on demand (01 phase 4a) before live watching (4b), and M9 selection edits before the descent columns.

**Durations are rough**, for one maintainer working with agents, and are replaced by measured velocity after M1. Along the longest chain, M0 → M1 → M4 → M5 → M6, the redline job lands about 14–20 weeks after M0 starts, between mid-January and late February 2027. The questionnaire (M7) follows within about eight weeks of M6, so between February and April 2027. Both dates are rough.

**Every milestone's exit also includes** one how-to page per new feature in [`content/docs/v2`](../../../surfsense_web/content/docs/v2/index.mdx), which today holds only a "Docs in progress" placeholder; a changelog entry and an announcement; the macOS status on [/downloads](../../../surfsense_web/app/\(home\)/downloads/page.tsx); and, at a milestone that adds a network destination, the [privacy page](../../../surfsense_web/app/\(home\)/privacy/page.tsx)'s list of destinations (section 3.2 lists three kinds today). The privacy page is also reviewed in M0.

| | Name | Depends on | Rough |
|---|---|---|---|
| M0 | Fix today's gaps (2.1.x, starts now) | nothing | 1–2 weeks |
| M1 | Clean engines and the eval harness | M0 | 3–4 weeks |
| M2 | Library folders | M0; in parallel with M1 and M3 | 2–3 weeks |
| M3 | Versions and Refine | M0; in parallel with M1 and M2 | 3–4 weeks |
| M4 | Claude measured, every model labelled | M1 | 3–4 weeks |
| M5 | The agent, on by default | M2, M3, M4 | 3–4 weeks |
| M6 | Revised copies and the redline job | M1, M3, M5 | 4–6 weeks |
| M7 | Spreadsheets and the security questionnaire | M1; 02 phase 1 and 03 phase 4 from M6 | 4–8 weeks |
| M8 | Link a folder on disk | M2; in parallel with M5–M7 | 4–6 weeks |
| M9 | Down the ladder | M6, and M7 for the questionnaire | 4–6 weeks |
| M10 | Open-source job packs through plugins, enterprise, learning loop | the plugin installer and runtime; an Enterprise deployment answer | open |

### M0: Fix today's gaps

- **Goal:** fix what is wrong today as a 2.1.x point release, without waiting for the clean-room gate.
- **User sees:** chat and Studio use every source, not the newest 50 (verified: `list_documents` defaults to `limit = 50` in [`documents/router.py`](../../../surfsense_local/backend/modules/documents/router.py), and chat sends only the loaded ids). Studio says "Grounded on 14 of 212 sources". HTML artifacts stop running scripts (today `sandbox="allow-scripts allow-popups"` in [`html-viewer.tsx`](../../../surfsense_local/frontend/src/features/studio/viewers/html-viewer.tsx)). An upgrade keeps a copy of the database from before it migrated.
- **Contains:** 01 phase 0 (the 50-source fix, the server-side scope, Studio's grounding regime) and the database snapshot before migrations; 03 phase 0 (the HTML and markdown hardening); 04 RT0 (build hygiene, the installer size gate).
- **Exit:**
  - With 60 sources, `{all: true}` cites the oldest; a one-document scope among 2,000 nearby chunks finds a paraphrase.
  - An HTML artifact's script does not run in the viewer, and neither an HTML artifact nor a Studio markdown viewer loads a remote image.
  - An upgrade with a pending revision writes `<data>/backups/<from>-<to>.db` before [`upgrade_to_head`](../../../surfsense_local/backend/shared/migrations.py) migrates, keeps the last two, and the restore steps are in the user docs. Today `upgrade_to_head` calls `command.upgrade` with no copy.
  - The installer size gate runs in CI.
- **Depends on:** nothing.
- **Rough:** 1–2 weeks.

### M1: Clean engines and the eval harness

- **Goal:** finish the licensing work every engine waits on, and the harness every verdict comes from.
- **User sees:** Settings › About lists third-party notices. M1 is mostly under the surface; M2 and M3 carry the visible changes while it runs.
- **Contains:** 02 phase 0 (the clean-room fix) and 0L (the legal review of its records); 02 phase A (agent config and tool order, here because 01 phase 3a waits on it); 04 RT2 (the licence gate and notices); 05 P0 (the harness); the baseline re-run below.
- **Exit:**
  - On the clean tree at n=3, docx D01, D03 and D05 score 1.00 and contract-redline at least 77.7%. The Word-oracle results are committed, the similarity scan is near zero, and `check_provenance.py` passes in CI.
  - No `.dll` or `.pyd` falls outside the reviewed licence list.
  - The default Qwen3 4B has `grounded_qa` and `schema` rows from the RTX 3050 and the M2.
  - 0L has the provenance record, the scan report and the process record. Its answer gates selling to legal and security buyers, not this release.
- **Depends on:** M0; a spec author and a separate implementer; Windows with Word. **Before 2026-10-15**, whatever M0's state, re-run iteration 3's baseline at n=3 on Haiku 4.5, which retires "not sooner than" that date, and on Sonnet 5.5 at low effort, so the gate keeps a baseline either way.
- **Rough:** 3–4 weeks.

### M2: Library folders

- **Goal:** the maintainer's first ask, folders in sources, shipped without waiting for the agent.
- **User sees:** Library folders with Trash and Undo; adding a whole folder by picker or drop; tri-state ticks over 5,000 files in one click; a name filter in the tree.
- **Contains:** 01 phases 1 and 2.
- **Exit:** the folder migration keeps the chunk count and is a no-op the second time; a note write succeeds during a 5,000-document purge; the tree's Vitest tests pass axe checks, and the tree works from the keyboard (arrow keys, Space to tick).
- **Depends on:** M0 only. It runs in parallel with M1 and M3.
- **Rough:** 2–3 weeks.

### M3: Versions and Refine

- **Goal and user sees:** outputs that can be edited again and again with no lost work: a version switcher, regenerate with an instruction, restore as a new version, a failed run that never hides the last good output, Refine on spec-backed formats (labelled "Not measured" until rows exist), artifacts filed into folders as sources.
- **Contains:** 03 phases 1, 2 and 6; 01 phase 5, which waits for M2's folders; 06 R1.
- **Exit:** the evidence backfill passes every case in 03's table and inserts nothing the second time; a queued pre-upgrade job runs to ready; the upgrade writes its snapshot first.
- **Depends on:** M0. It runs in parallel with M1 and M2.
- **Rough:** 3–4 weeks.

### M4: Claude measured, every model labelled

- **Goal:** a frontier baseline taken on Claude itself, and honest labels on every model.
- **User sees:** Claude on their own key with prompt caching and enforced schemas; a Spending panel with a $5 per-job cap; a capability line on each model ("Answers · Studio · Jobs step by step · Not measured"); a warning before sending in place of today's 409; a local-only workspace setting; Studio's Word, PowerPoint, Excel and PDF built from specs wherever the builder scores at least today's `exec()` path on that model. No surface offers "Test this model" until 05's self-test ships in M10.
- **Contains:** 05 P1, P2, P3a, P4a and P7; 06 S1 and S2; 02 phases B and 2.
- **Exit:**
  - Committed `agent_smoke`, `grounded_qa` and `schema` rows for Opus 5.5, Sonnet 5.5 and Haiku 4.5 on the native route, and one Sonnet column through the compatibility layer.
  - A second identical request reads from cache; a capped request ends an opencode turn after one reply; `capability_of()` makes no network call and loads no model; the fixed prompt is measured from `usage.input_tokens`.
  - Before `runner.py` is deleted, the `exec()` path is measured on the default 4B with the builder cases. A builder replaces `exec()` on a model only where it scores at least that baseline; builders reach validity ≥ 0.98 after one repair on Sonnet.
  - The privacy page lists `api.anthropic.com`, including the `count_tokens` calls that send text.
- **Depends on:** M1 (the harness, 02 phase A).
- **Rough:** 3–4 weeks.

### M5: The agent, on by default

- **Goal:** an agent scoped like chat, whose files become versions, in the installers.
- **User sees:** "Answer / Work on files" on Claude; agent threads that read only the ticked sources; files the agent writes appear as artifact versions; the study-pack job; the agent in the Windows and Linux installers, and on macOS once a notarized build carries it.
- **Contains:** 01 phases 3a and 3b; 03 phase 3 (the outputs sweep); 06 S3, J1 and J2; 05 P4b (rows for Claude, the `free_agent_tasks` family, and the OpenAI and Gemini columns). `ENABLED_BY_DEFAULT` was flipped to true earlier, on 7 Oct 2026.
- **Exit:**
  - Two agent threads keep separate views, and `create_artifact` refuses an unticked id; `agent_smoke` is 3 of 3 on Sonnet with per-thread folders; a file the agent writes in `outputs/` becomes a version.
  - `free_agent_tasks` (at least 10 cases) passes its gate on Sonnet. Each failed frontier case is labelled skill, tool, prompt or model, and fixed before lower rungs run it. Smoke and single-call columns for one OpenAI and one Gemini frontier model on the OpenAI-compatible wire are committed (05 P4b).
  - [agent.md](../../architecture/agent.md)'s "agent test" points to 05's `agent_smoke` and the capability rule. 04's size gate counts opencode and ripgrep (about +62 MB compressed, measured in 04), which installers carry since 7 Oct 2026.
  - Idle and busy private bytes per process are measured on a 16 GB Windows laptop with integrated graphics and recorded against the memory budget (Small things).
- **Depends on:** M2, M3 and M4. A notarized macOS build carrying opencode gates the macOS release, not this milestone.
- **Rough:** 3–4 weeks.

### M6: Revised copies and the redline job

- **Goal:** the B2B value: a contract comes in, and a tracked-change redline in the customer's format comes out.
- **User sees:** "Make a revised copy" on a `.docx` source; engine edits with a report per operation; a download that leaves internal comments out by default and reports its leak scan, with "With changes (internal)" as an explicit second choice and the clean copy beside it; accept and reject in a side list; the redline job as a job thread on Claude, with "Run step by step" kept; the user's own playbook through "Make a playbook from this document"; "Mark as reviewed", which asks for the reviewer's name; a workspace export and import.
- **Contains:** 02 phases 1, 1b (`docx.external`), 3, 4 and 6; 03 phase 4; 04 RT1; 05 P3b; 06 J3; the playbook path; the workspace export/import bundle.
- **Exit:**
  - Through a job thread on Sonnet, contract-redline passes the job gate (every case at 2 of 3 runs or better, a mean of case rates ≥ 0.75 and a cluster-bootstrap lower bound ≥ 0.60 over at least 7 cases, [05 section 4](05-model-ladder-and-evals.md#4-the-capability-profile)); D01, D03 and D05 score 1.00 through `edit_document`.
  - The original's bytes and modification time are unchanged; the injection fixtures, one asking for untracked changes, change nothing silently; `worker --engine-op` never imports `worker.consumer`.
  - A revised copy with an internal comment downloads without it.
  - In a job thread, the job's skill text is in the next model request after a forced compaction.
  - An invalid playbook stops the job before any edit, with `playbook_invalid` on the job card. Each starter playbook carries "Starter playbook — not reviewed by a lawyer; not legal advice" on the job card, in the issues list and in the exported issues file; a user's own playbook carries no label.
  - A workspace bundle round-trips folders, versions and settings; a playbook and a library folder export to a file a colleague can import.
  - `folder_qa` meets the `grounded_qa` bar on Sonnet and the default 4B. `refine_spec` rows set Refine's labels, and Refine stays only where they reach 0.80 over at least 8 cases.
  - The redline job states its supported document languages, and its family has a non-English case.
  - The job-card and report-card Vitest tests pass axe checks, and a screen-reader pass over the revision side list is recorded.
  - Idle and busy private bytes per process are measured again on the 16 GB laptop, with an engine run and a local model turn at once.
- **Depends on:** M1 (the clean tree), M5 (01 phase 3a: per-thread registration and `copy_original`) and M3 (03 phase 1). The job is offered on a model once its row passes the job gate. The lawyer's review of the starter playbooks gates public job pages, SEO pages and legal marketing; 0L gates selling to legal and security buyers.
- **Rough:** 4–6 weeks.

### M7: Spreadsheets and the security questionnaire

- **Goal:** the first buyer target.
- **User sees:** the security-questionnaire job, free, filling the customer's own workbook as a revised copy.
- **Contains:** the xlsx engine, `surfsense-sheet-fill` and the questionnaire job skill and agent from 02 phase 5a, whose package work starts right after M1 and runs in parallel; 06 J4. The job's mappings and eval cases are Apache-2.0 and ship in the app (What stays free and what is sold).
- **Exit:** the questionnaire job passes the job gate on Sonnet; no delivered workbook carries an IronCalc value; the job states its supported document languages, and its family has a non-English case; the job and its mappings work without a license.
- **Depends on:** M1, 02 phase 1 and 03 phase 4 (revised copies). Not the redline workflow.
- **Rough:** 4–8 weeks; the xlsx engine is mostly unbuilt.

### M8: Link a folder on disk

- **Goal and user sees:** Link a folder on disk, indexed in place and watched, with root states (unavailable, permission denied, cloud-only, mass vanish), a root-level state when most of a root is OneDrive online-only files, and Office support for legacy formats.
- **Contains:** 01 phases 4a and 4b, with the OneDrive state; 04 RT3a, RT3b (shown as "Office support") and RT6. Creating the pack-hosting repository, its publisher App and its protected environment is an explicit RT3a task, owned by the maintainer as the GitHub organization's admin.
- **Exit:** 01's phase 4a platform tests pass from packaged apps on all three platforms, plus a packaged-app test on a Windows VM with OneDrive Known Folder Move; the dehydrated share of a real Documents folder is measured; an unavailable root keeps every document; a 600-file vanish is held; with Office support, `.doc`, `.xls` and `.ppt` are read, and without it the root header counts them; the privacy page lists `release-assets.githubusercontent.com` for packs.
- **Depends on:** M2. It runs in parallel with M5–M7. ADR 0041 waits on TDF's answer, and the macOS packaged test needs a notarized build (outside dependencies below).
- **Rough:** 4–6 weeks.

### M9: Down the ladder

- **User sees:** job threads on 27–35B local models where rows pass; the redline and the questionnaire as workflows on smaller models where they pass; selection edits, with a keyboard path (select by paragraph in the outline or revision list).
- **Contains:** 05 P5a and P5b; 02 phase 5b (`questionnaire_fill`), and the redline workflow on smaller models where rows pass; 03 phase 5; local 27–35B rows when a machine exists.
- **Exit:** committed 4B and 8–14B rows, and 27–35B rows once a 24–32 GB machine exists; a selection edit can be made without a mouse.
- **Depends on:** M6, and M7 for the questionnaire workflow.
- **Rough:** 4–6 weeks.

### M10: Open-source job packs through plugins, enterprise, learning loop

02 phase 8; 03 phase 7; 04 RT4 and RT5; 05 P6 (the self-test, after which "Test this model" joins the fixes); 06 P1 and E1. Job packs installed through the plugin system are an open-source extension mechanism under Apache-2.0, never paywalled. It depends on the plugin installer and runtime, and E1 on an Enterprise deployment answer. 02 phase 7 (a harness adapter or Goose spike) runs only on its trigger: 27–35B profiles failing through context overflow, or an end of opencode 1.x support. Duration: open.

### Outside dependencies

Chase dates are proposed; each owner confirms or moves theirs.

| Dependency | Blocks | Owner | Chase on |
|---|---|---|---|
| Haiku 4.5's retirement, "not sooner than" 2026-10-15 | the M1 gate's baseline | the maintainer, who runs the re-run | re-run committed by 2026-10-14 |
| A clean-room spec author, a separate implementer, and a reviewer who never opened `original_skills/` | M1 | the maintainer | 2026-10-09 |
| The Apple Developer agreement | every macOS release, the agent on macOS (M5), 01's packaged macOS test (M8) | the Apple account holder | 2026-10-09 |
| A lawyer: first the provenance record and schema terms (02 phase 0L), then the starter playbooks | selling to legal and security buyers; public job pages, SEO pages and legal marketing | the maintainer | engaged by 2026-10-16; records sent at M1's exit |
| TDF's answer on a trimmed LibreOffice and its source mirror | ADR 0041's acceptance, RT3b (M8) | the maintainer | asked by 2026-10-16, chased 2026-11-06 |
| A 16 GB Windows laptop with integrated graphics | the memory budget at M5's and M6's exits | the maintainer | 2026-11-13 |
| A 24–32 GB machine | committed 27–35B rows (M9) | the maintainer, or community `matrix` submitters | 2026-12-01 |
| An Enterprise deployment answer | 06 E1 (M10) | the maintainer, at the first Enterprise conversation | when a customer asks |

## ADRs to write or amend

Numbers are proposed in this order from the current last ADR, [0039](../../adr/0039-document-scripts-run-without-approval.md), written for the create-and-edit slice. Whichever lands first takes the next free number.

| ADR | Records | From |
|---|---|---|
| **0040** Edits run shipped engines on model-written plans, make append-only versions, and never write the user's file | engine edits always tracked; all-or-nothing except workflows; head moves only on success; restore is a new version; no approval needed, since the engine path runs no model-written code (document scripts are ADR 0039's); bash allow-lists for skill scripts refused; a revised copy leaves the app without internal comments unless the user picks the internal download | 02 and 03 together |
| **0041** The running app may download pinned upstream runtime binaries after per-host consent | packs unaltered except for deleted files, pinned in the app, never SurfSense's own code; acceptance waits on TDF's answer (04's open questions) | 04 |
| **0042** Third-party skill material enters only through a provenance record | the licence gate binds contributors and packs | 02 |
| **0043** Claude goes through Anthropic's Messages API | amends ADR 0015: a connection's wire follows its host and `auth_kind` | 05 |
| **0044** What a model may do comes from a reviewed, measured capability manifest | extends ADR 0014. One workspace kind. The tier is prompt shape only. An unmeasured model keeps today's behaviour. A verdict reflects eval rows and live gates only, never a release policy such as a legal hold. The license never changes a verdict, and an organization policy may only lower one | 05 and 06, merged into one |
| **0045** Retrieval scope is resolved on the server and applied inside both legs | the KNN prefilter | 01 |
| **0046** SurfSense never loses a user's sources by surprise | Trash; read-only linked roots; no delete on unavailability; a mass vanish asks; placeholders never read; a database snapshot before every migration | 01 |
| **0047** Premium plugins are source-available and delivered by the license server | premium plugins, such as the scraper client, live under the Business Source License 1.1 in `surfsense_backend/app/proprietary/`; the license server hands them only to a valid license; the open-source installer never carries them; the app, the engines, the format skills and all job content (job skills, playbooks, questionnaire mappings, RFP templates, eval cases) stay Apache-2.0 in `surfsense_local/`, and job packs installed through the plugin system stay open source. Supersedes [ADR 0025](../../adr/0025-scraper-client-as-paid-plugin.md)'s "paid plugin code is Apache-2.0" premise and the [plugins proposal](../plugins/README.md)'s "every plugin is Apache-2.0" for paid plugins | this page and the [strategy](../../../plans/community-local/file-agent-strategy.md) |

Amend:

- [0003](../../adr/0003-artifacts-as-documents.md): versions, the head-only index, filing.
- [0005](../../adr/0005-hand-written-migrations.md): `documents` gains columns only by plain `ALTER TABLE`, the stale count is fixed, and `upgrade_to_head` snapshots first.
- [0006](../../adr/0006-hybrid-retrieval.md): the KNN prefilter.
- [0008](../../adr/0008-two-job-queues.md): ingest priorities, and the engines queue.
- [0010](../../adr/0010-studio-builders-not-sandboxes.md): the Office bullet goes per format as each builder reaches the `exec()` baseline.
- [0027](../../adr/0027-egress-consent-per-host.md): one GitHub consent.
- [0028](../../adr/0028-model-written-code-runs-with-approval.md): "no agent exists yet" goes, and the Studio consequence narrows to formats that keep `exec()` on local models.

Unchanged: 0016, 0017, 0019, 0033 (unless 01 phase 6 lands) and 0035, though see the engines worker under Small things. [Contract 3](../../contracts/03-export-bundle.md), today a hosted-to-local import of markdown and chats, gains folders, versions and settings for the workspace bundle (M6).

## What stays free and what is sold

- **Free, in the app:** everything the app does, on every model the capability allows. That covers Q&A, every Studio format, folders and linked folders, versions, revised copies and review, the agent harness, the format skills, and every catalogue job with all its content: job skills, playbooks, questionnaire mappings, RFP templates and eval cases, open source under Apache-2.0. A user's own playbook works on the same terms. Job packs installed through the plugin system (M10) are an open-source way to extend the catalogue, never paywalled. Office support, the LibreOffice download, is also free. This keeps the pricing FAQ's "everything the app itself does stays free" ([`pricing-content.ts`](../../../surfsense_web/components/pricing/pricing-content.ts), line 163).
- **Paid license:**
  - premium plugins, such as the scraper client;
  - priority support (maintainer question 10);
  - Enterprise controls, below.

  **Where premium code lives.** `surfsense_backend` shrinks to the license server ([`app/license/`](../../../surfsense_backend/app/license/)) and the premium plugins, kept under the Business Source License 1.1 in [`app/proprietary/`](../../../surfsense_backend/app/proprietary/LICENSE), which the root [`LICENSE`](../../../LICENSE) already carves out. The license server delivers a premium plugin only to a valid license; the app downloads it after per-host consent ([ADR 0027](../../adr/0027-egress-consent-per-host.md)) and checks its sha256. Everything else in this proposal, job content included, is built in `surfsense_local/`; nothing new goes into the hosted backend's other code, which is archived at the [`archive/hosted-2026-09`](https://github.com/MODSetter/SurfSense/tree/archive/hosted-2026-09) tag.
- **Enterprise:** an organization policy (agent off, local models only, or allow-lists per engine), local-only as the default, an audit log of the document scripts the agent ran, and later a sandbox.
- **Undecided:** anything sold beyond premium plugins, priority support and Enterprise. The paid side is thin today. It is revisited after the [create-and-edit slice](07-create-and-edit-mvp.md)'s video and real user feedback, and the [strategy](../../../plans/community-local/file-agent-strategy.md) lists the candidates.
- **Never sold:** a capability verdict. A license never raises one.
- **What users pay providers directly:** their own API usage. SurfSense shows estimates and enforces caps.

Pricing, positioning and channels belong to the [file-agent strategy](../../../plans/community-local/file-agent-strategy.md).

## Small things that are easy to forget

Each names the stream and phase that owns it.

- **Onboarding.** Curated rows show their capability line before download, with 06's note under the local list ([06](06-product-shape.md#how-the-capability-is-shown)). The first revised copy asks for the revision author. Linking a OneDrive-redirected folder explains "Always keep on this device" (01 phase 4a).
- **Sample files.** Each job ships a sample input under a licence that allows redistribution (a contract and a questionnaire), so a new user can try it without a confidential file (06 J3 and J4).
- **What's new.** Upgraded users see a short list of what changed on first launch after an upgrade, linked to the changelog (06, from M2).
- **Finding things.** The source tree gets a name filter, since a linked root can hold 20,000 files (01 phase 1). Artifacts become searchable sources by filing or ticking (01 decision 16). Studio's list also needs a filter on head title and body; it goes to 03 phase 7.
- **Disk use.** A Settings view adds up versions, the Trash (30 days), the engines' view cache (500 MB), the agent's text cache and packs (06 with S2 in M4; packs join in M8).
- **Notifications.** An OS notification when a long job finishes or a linked-root scan completes, if the window is not focused (06 J3; 01 phase 4a).
- **Citations inside outputs.** Builder specs need a source reference per block, rendered as a Sources list and resolved through the version's `inputs.sources`, or Office outputs lose chat's citations. It goes to 02 phase B. Redline comments cite playbook rule ids.
- **Review.** "Mark as reviewed" asks for the reviewer's name each time. The interface and the docs call it self-attested, and it may be written into the downloaded file's custom document properties (06 J3, 03 phase 4).
- **Export names.** Use `<title> v<n>.<ext>` and `<stem> (redline v<n>).docx` ([03](03-editable-artifacts.md#storage)), with the suffix localized. Strip Windows-reserved characters and device names, cap the length at 255 bytes, and refuse to save into a linked root.
- **Export, import and sharing.** A workspace bundle carries folders, versions and settings to a new laptop; a playbook and a library folder export as files a colleague imports (01, 02, 03 and 06, M6). Sharing beyond files is out of scope for v1: the app is single-user and local, so the bundle is the sharing path. Legacy `.doc`, `.xls` and `.ppt` stay unreadable until RT6 (M8), and the root header counts them. `.msg` and `.eml` are not supported in v1 and are a follow-up.
- **Internationalization.** Every new string goes through the ICU catalogs ([ADR 0029](../../adr/0029-icu-translation-catalogs.md), [0030](../../adr/0030-formatjs-renders-interface-text.md)). That includes reason codes, verdict labels, localized role-folder names ("Received", "Policies"), plurals in Trash and scope counts, and dates in purge notices. Engines emit `{code, values}` per operation and per `must_tell_user` line, rendered through the catalogs with English as the fallback (02 phase 1). Each job states the document languages it supports, and each job family gets at least one non-English eval case (05 P3b). A revision author is user data and is never translated.
- **Accessibility.**
  - The source tree needs ARIA `tree` roles, arrow-key navigation, and Space to tick a tri-state box.
  - Drag and drop always has the Move to… picker as its keyboard path.
  - Diffs never rely on colour alone, so insertions are underlined and deletions struck through.
  - Report cards and inline confirmations take focus and are announced.
  - Selection edits have a keyboard path: select by paragraph in the outline or revision list (03 phase 5).
  - The tree, job-card and report-card Vitest tests run axe checks; M6's exit includes a screen-reader pass over the revision side list.
- **Offline.** When the selected remote model is unreachable, the composer says so and offers "Run step by step" on the local model where the job allows it (06 S1). An engine version in flight fails cleanly and keeps the head (03 phase 1). Entering a local-only workspace suggests the last local model used (06 S2).
- **Memory and CPU.** The stack gains an engines worker, an opencode instance per thread folder, LibreOffice peaks and long linked-folder scans beside llama.cpp. Budget: idle and busy private bytes per process, measured on a 16 GB Windows laptop with integrated graphics, added as a reference machine, at M5's and M6's exits. The engines worker stays lean: chunks and vectors for engine and agent versions are computed by the Studio worker (03's `index_version` and `version_job`), never the engines worker. Bulk ingest yields while a local model turn streams (01 phase 2's priorities). Chat shows "Waiting for the running job" when the one llama-server slot is busy (05 P5a).
- **Windows.**
  - Long paths go through `\\?\` (01).
  - opencode's wildcard ignores case only on Windows (02).
  - Purges and pack removal meet files that Docling or `soffice` hold open.
  - Hard links fall back to copies on exFAT and FAT32.
  - Call `soffice.com`, not `soffice.exe`.
  - Smart App Control may block unsigned DLLs (04's open questions).
  - Storage Sense dehydrates indexed files, and Known Folder Move puts Documents and Desktop in OneDrive (01 phase 4a).
  - Mirrored names avoid `CON` and `NUL` and trailing dots.
- **The Docker stack.** ADR 0035's supervisor runs the workers in the container too, so the engines worker must join the shared supervisor, not only Electron. Linked roots there use standing grants and poll mode (01).
- **Upgrades.** 01 phase 1 and 03 phase 1 each rewrite users' only database: a `VACUUM INTO` snapshot before every migration (01 phase 0, M0), count checks in `test_migrations.py`, and a timed run on a large fixture. Release history answers 06's question about migration 0005: v2.0.0 is the first desktop release, and both 0005 and 0011, the one revision that rebuilds `documents`, were already in it (`git tag --contains`), so no released desktop upgrade ran them on an existing database.
- **Living docs.** [ROADMAP](../../ROADMAP.md)'s Agent and Studio entries, `AGENTS.md`'s new tree, [agent.md](../../architecture/agent.md)'s tested-list text when M5 flips the default, and each architecture page as its phase lands.

## Risks

| Risk | Mitigation |
|---|---|
| A lawyer finds `docxkit` or `crlib` too close to the originals, or a schema's terms forbid redistribution | provenance, scan and process record; review before B2B sales; a refused schema leaves the set |
| A starter playbook is taken as legal advice | the "not reviewed by a lawyer; not legal advice" label on the job card, issues list and exported issues file; public job pages, SEO pages and legal marketing wait for the review |
| Haiku 4.5 retires before the gate runs | re-run the baseline on Haiku and on Sonnet low by 2026-10-14, whatever M0's state |
| A migration cascade deletes chunks or threads, or an upgrade fails halfway | a snapshot before every migration, keeping the last two; plain `ALTER TABLE` only; count checks; tombstone-only directory sweeps |
| Below the frontier, almost nothing passes | the release rule keeps Q&A and Studio for the 4B; an unmeasured model loses nothing; a builder replaces `exec()` only where it scores at least the `exec()` baseline, so the product for free users is never worse than today |
| A job's skill drops out of a long run after opencode compacts | the skill is the per-job agent's own prompt, not a per-turn `system` string; a test forces compaction and checks the next request |
| Internal comments reach the counterparty | the external download is the default and removes them, with a leak scan in the report |
| The finished stack exhausts a 16 GB laptop | the memory budget at M5's and M6's exits; one place for the encoder; ingest yields to a streaming turn |
| Most of a linked Documents folder is OneDrive online-only | a root-level state with the fix; onboarding copy; SurfSense still never triggers a download |
| macOS cannot carry the agent | Windows and Linux first, said on /downloads; a notarized build with opencode gates macOS |
| opencode 1.x stops being maintained, or 2.x diverges | the pin; acceptance on 1.18.34; an adapter and a Goose spike on 02 phase 7's trigger |
| An injected document asks for a silent change or exfiltration | engines write tracked changes only; no network imports; the reminder strip; server tools refused; scripts sandboxed |
| A user's API bill surprises them | the ledger, estimates above $0.25, and a cap that answers 403 so it is never retried |
| Six streams for one maintainer | milestones that each ship alone; a user-visible point release at least every 3–4 weeks; M1, M2 and M3 in parallel, and M8 beside M5–M7; durations re-estimated from measured velocity after M1 |

## Open questions for the maintainer

1. **Who are the clean-room spec author and implementer?** *Recommended:* two agent sessions in fresh worktrees that hold neither `references/` nor the skills repository, with their file reads logged. A contributor who has never opened `original_skills/` signs off the pull request.
2. **When do you engage a lawyer, and for what?** *Recommended:* now, in parallel with M1's clean-room work, scoped to `provenance.json`, the scan report, the process record and the schema publishers' terms. Add the starter playbooks next.
3. **Does the redline job need the playbooks' lawyer review before release?** *Recommended:* no. The job is offered on a model once its eval row passes the job gate, and no verdict stands in for a legal hold. Until a lawyer reviews them, each starter playbook carries "Starter playbook — not reviewed by a lawyer; not legal advice" on the job card, in the issues list and in the exported issues file; a user's own playbook carries no label. Public job pages, SEO pages and legal marketing wait for the review.
4. **What eval budget, and which account?** *Recommended:* a dedicated Anthropic workspace under the organization, about $650 per full sweep, a $300 monthly cap outside sweeps, and the `model-evals` environment reviewed by you.
5. **Who provides the reference machines?** *Recommended:* a 32 GB Apple-silicon Mac for the 27–35B rows, once the Apple agreement is current, and a 16 GB Windows laptop with integrated graphics for the memory budget. Until then, 27–35B rows are screened only, and community `matrix` submissions are the other route.
6. **Who accepts the Apple Developer agreement, and when?** *Recommended:* the account holder, by 2026-10-09. It blocks every macOS release, the agent on macOS and 01's packaged privacy test.
7. **On routes that cache prompts, should a new thread default to Answer or to Work on files?** *Recommended:* default to Answer until M4 measures first-answer latency and cost on Sonnet. Switch to 05's rule only if Work on files is no slower for a one-line question.
8. **May the LibreOffice download be trimmed and re-hosted, and must its full source be mirrored?** *Recommended:* ask TDF now, well before RT3b in M8, mirror the exact source archive beside each pack, and name it "Office support (LibreOffice)".
9. **Should SurfSense ever trigger a cloud download of a placeholder?** *Recommended:* no. The user makes a file or a folder available offline in their sync client, guided by the root's online-only state, and the next reconcile picks it up.
10. **What does priority support mean, and who answers it?** *Recommended:* an email reply within two working days from the maintainer, covering installation, model setup and premium plugins, written on the pricing page before the first license is sold.
11. **What other small things do you remember wanting?** *Recommended:* list them against Small things above, so each gets an owning stream and a milestone.
