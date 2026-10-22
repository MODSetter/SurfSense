---
status: in-progress
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

> The user adds files, or a whole folder, as sources, makes outputs from them, and keeps editing those outputs, all on their own machine. Outputs are versions that only grow. A change to the user's own file arrives as a revised copy with tracked changes; the file itself is never written. Edits run on engines SurfSense ships: the model writes a plan as data, and the engine applies it, checks it and reports on every operation. There is one kind of workspace, and what it offers follows from the selected model's measured capability: a free 4B user gets grounded answers, Studio and step-by-step jobs, and a user with Claude on their own key also gets an agent that works on files. The redline's engines are the maintainer's improved document skills, shipped after a scoped clean-room fix in M1. Today's gaps are fixed first, in M0, without waiting for it, and the first job, the security questionnaire, does not wait for it either: it writes through the Excel revise engine shipped in 2.2.0.

This is the entry point of the file-agent proposal. It extends the [agent proposal](../agent/README.md) and changes some of its locked decisions. The six stream files carry the design and its verified facts; this page resolves where they disagree, orders their phases, and lists what is left to the maintainer. The stream files were reconciled with this page on 3 Oct 2026. Facts were checked against `dev_mod` at `0847e12f7` on 3 Oct 2026, and the 21 Oct 2026 revisions against `dev` at `746c5fd66`. The workspace question went to a design panel of three proposals, and both judges chose P1 (48 points, against 38 to 41 for P2 and 40 for P3).

**The first slice comes before the milestones.** [07, create and edit](07-create-and-edit-mvp.md) is built first, on `dev_mod`, which syncs with `dev` every few hours: the agent creates a Word or PDF file in chat and refines it turn by turn through a document script it keeps. During the slice, Studio's buttons stay as they are today. It pulls reduced parts of M3 (versions) and M5 (the agent) forward, and it follows [ADR 0039](../../adr/0039-document-scripts-run-without-approval.md): document scripts run without approval in SurfSense's script runner, and the agent has no shell. Studio's Word and PDF change after the slice, into two paths ([07](07-create-and-edit-mvp.md#after-the-slice)): strong models keep today's code-written documents, which are proven, and small models write Markdown that committed builders render. Each path has its own one-call Refine, and a rule decides which models count as strong. No reliable signal for that rule exists yet; [05](05-model-ladder-and-evals.md)'s measured capability is where it will come from. Where 07 disagrees with the milestones below or with [02](02-skills-and-engines.md)'s Studio builders, 07 holds, including its two paths for Studio's Office formats after the slice, and the milestones are revised once the slice ships. The slice shipped in 2.2.0 on 9 Oct 2026, together with revised copies, Office support, PDF tools and data analysis; the milestones below are not revised for it yet.

**First ladder results, 4 Oct 2026.** The slice's eight live cases pass on Claude Opus 5.5 and Sonnet 5.5. Haiku 4.5 passes five: in the other three it skipped the page previews the skill asks it to check. Through OpenRouter, Kimi K3 and Qwen3.8-27B pass all eight cases. Text-only GLM-5.3 and DeepSeek V4 Pro pass all but the case that needs image input. Smaller open models (Qwen3.6-35B-A3B, Gemma 4 31B, Ministral 14B, Qwen3.5-9B) fall short. The matrix, the causes and the columns still to run are in [08](08-model-ladder-results.md).

**Revised 21 Oct 2026: the questionnaire ships first.** The maintainer accepted the order in [08-b2b-artifact-jobs](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#the-headline) and the [strategy](../../../plans/community-local/file-agent-strategy.md#who-buys-first-and-which-job-ships-first): M7, the security questionnaire, now ships before M6's redline job and is the first buyer target. It writes through the Excel revise engine that shipped in 2.2.0, so it needs neither the new xlsx engine 02 phase 5a used to plan nor M1's clean-room fix. RFP and DDQ responses from the same library come next, then the extraction stack, about March 2027, and the playbook redline job after them. Insurance is dropped as a play. Milestone and job IDs are unchanged; M1, M7, M6 and M9 below say what moved. Revised copies only, no job page or claim before an eval row, and the free promise all stand. The paid side the research proposes, the beta's scope and the Show HN's timing are the maintainer's open questions ([08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer)); this page does not decide them. On 22 Oct 2026 the maintainer settled the paid side and the Show HN (below).

**Revised 22 Oct 2026: the B2B jobs are paid plugins.** The maintainer decided that SurfSense's B2B jobs ship as plugins that run on the user's machine and install and run only with an unexpired SurfSense license: Individual, Team, or the 30-day trial for its term ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)). That covers the security questionnaire, RFP, RFI and DDQ responses, the contract redline, bank statements into a ledger, medical chronologies, and contract and lease registers. The app, the general agent, every engine and the shared job infrastructure stay free under Apache-2.0, and the user's files never need a license to open or export. This replaces the page's earlier rule that every job and all its content stay free; the durations note, M7, M6, M10, the lawyer's row in Outside dependencies, the ADR 0047 row, What stays free and what is sold, the risks and open questions 2 and 12 say what changed. The job order, revised copies only and the milestone and job IDs are unchanged. The maintainer posts the Show HN the week of 22 Oct 2026.

## Why now

- **Google ships the agent, the skills and the Office outputs.** Since 8 Jun 2026 NotebookLM notebooks on paid tiers (Ultra and business plans first, then Pro) have had "a secure cloud computer" with "more than 100 curated software skills", and it writes DOCX, XLSX and PPTX ([Google](https://blog.google/innovation-and-ai/products/notebooklm/better-research-notebooklm/)). On 16 Jul 2026 NotebookLM was renamed Gemini Notebook, and Google said the cloud computer would reach AI Pro on the web in the coming weeks ([Google](https://blog.google/innovation-and-ai/products/gemini-notebook/notebooklm-gemini-notebook/)). It still has no local sources and no source folders, only labels ([Workspace Updates](https://workspaceupdates.googleblog.com/2026/07/notebooklm-now-gemini-notebook.html)). An agent alone no longer sets SurfSense apart; local, folders and editable outputs still can.
- **Local execution is disappearing elsewhere.** From 6 Oct 2026, new Claude Cowork tasks on Pro and Max run in Anthropic's cloud ([Anthropic](https://support.claude.com/en/articles/15520349-use-claude-cowork-on-web-desktop-and-mobile)).
- **Editing the customer's file is now expected.** Claude for Word writes native tracked changes ([Anthropic](https://claude.com/docs/office-agents/word)). Microsoft's Word, Excel and PowerPoint agents reached general availability ([Microsoft](https://www.microsoft.com/en-us/copilot/blog/2026/04/22/copilots-agentic-capabilities-in-word-excel-and-powerpoint-are-generally-available/)), and its Word legal agent redlines against a playbook ([ComplexDiscovery](https://complexdiscovery.com/microsoft-puts-legal-agent-inside-word-sharpening-contract-review-competition/)). In October, Copilot for Legal in Word ([MC1388706](https://mc.merill.net/message/MC1388706), 7 Oct 2026), Clio's Review Playbooks ([Clio](https://www.clio.com/enterprise/blog/clio-brings-firm-specific-judgment-into-ai-contract-review/), 1 Oct) and Anthropic's Apache-2.0 [Claude for Legal](https://github.com/anthropics/claude-for-legal) with Claude for Word all write native tracked changes against a playbook, so a playbook redline no longer sets SurfSense apart ([08-b2b-artifact-jobs](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#what-changed-since-29-september)). What does is a library the customer owns, filled into the requester's own file, on any model.
- **The jobs businesses pay for are cloud-only.** Questionnaire, RFP and redline vendors sell an answer library and approvals, not file editing ([08-b2b-artifact-jobs](../../../plans/community-local/seo/08-b2b-artifact-jobs.md)).
- **The engines already exist.** The Excel revise engine the questionnaire writes through shipped in 2.2.0: it edits the sheet XML and keeps charts, pivots and macros byte for byte ([`excel.py`](../../../surfsense_local/backend/modules/artifacts/revised_copies/engines/excel.py)). The improved docx skill scores 1.00 on its evals against 0.29 for Anthropic's original, and contract-redline scores 77.7% with the skill against 0% without it ([02](02-skills-and-engines.md#the-skills-project)).

## The answer to the workspace question

Preload the mode from the model, and add no workspace types. The model is app-wide, so a workspace type could not carry a capability; a type would freeze today's limits into user data and ask a question new users cannot answer. Every benefit a type offered (folder roles, pinned jobs, a local-only policy, a review state) fits one workspace. `capability_of()` reads a reviewed, measured profile and decides engines, job levels, formats, edit options and skills. The interface never says "mode": each item carries one of four verdicts (Best on this model, Tested, Not measured, Not on this model) with its reason. A verdict only ever reflects eval rows and live gates; nothing else, such as a pending legal review, is shown as one. When a model allows both engines, a new thread offers "Answer" or "Work on files", so a 4B user never sees a locked control. The full answer, with the grafts taken from the two losing proposals, is in [06](06-product-shape.md#the-answer-to-the-maintainers-question). What 2.2.0 shipped differs: the composer offers Basic (Q&A) and Agentic for each new chat, every model may pick Agentic unless a technical gate keeps it out, and a measured level sets only the default ([model capabilities](../../architecture/model-capabilities.md#the-modes)).

## Workstreams

| Stream | File | Owns | Starts from |
|---|---|---|---|
| **Sources and folders** | [`01-sources-and-folders.md`](01-sources-and-folders.md) | the source scope on the server, the database snapshot before migrations, Library folders and Trash, linked disk roots and their OneDrive state, per-thread agent folders, `resolve_original` and `copy_original` | the 50-source fix, which needs no folders |
| **Skills and engines** | [`02-skills-and-engines.md`](02-skills-and-engines.md) | the clean-room fix, `document_skills/`, engine tools, the engines queue, SKILL.md files and per-job opencode agents, the structured playbook format, workflows, Studio builders, opencode config, the model endpoint | since 21 Oct 2026, the questionnaire on the shipped Excel revise engine (phase 5a, M7); the clean-room fix (M1) waits for the contracts wave |
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
| When installers carry opencode | Once a model passes the agent test ([`enabled.mjs`](../../../surfsense_local/electron/scripts/opencode/enabled.mjs): `ENABLED_BY_DEFAULT = false`) | Since 7 Oct 2026 (`ENABLED_BY_DEFAULT = true`): the maintainer turned it on ahead of M5's `agent_smoke` and `free_agent_tasks` rows. v2.2.0, on 9 Oct 2026, is the first release that carries it, on all three platforms, notarized on macOS and signed on Windows | No agent test exists to flip the switch ([agent](../../architecture/agent.md)); 05's rows replace it |
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

**Shipping rule.** Something user-visible ships at least every 3–4 weeks. A milestone that runs longer ships its first finished part on its own: M7 its beta on frontier models before the row-by-row runner, M6 the revised copy and its download before the redline job (the copy and its download shipped in 2.2.0), M8 a linked folder that reconciles on demand (01 phase 4a) before live watching (4b), and M9 selection edits before the descent columns.

**Durations are rough**, for one maintainer working with agents, and are replaced by measured velocity after M1. Revised 21 Oct 2026: M7, the security questionnaire, now ships before M6's redline job ([08-b2b-artifact-jobs](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#the-next-90-days)). Its beta on frontier models is estimated at about mid-January 2027 for a minimum scope (08's items 1–5) or about mid-February for the full one (items 1–7); which one is the maintainer's choice ([08, open questions](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer)). Revised 22 Oct 2026: the beta ships as a paid plugin ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)), so both dates also wait on local paid bundles and the job-pack loader (08's item 11) and are re-dated once the harness lands. RFP responses and then the extraction stack, about March 2027, follow, and the redline job comes after them. The longest chain, M0 → M1 → M4 → M5 → M6, which put the redline about 14–20 weeks after M0 starts, no longer sets the first job's date. All dates are rough.

**Every milestone's exit also includes** one how-to page per new feature in [`content/docs/v2`](../../../surfsense_web/content/docs/v2/index.mdx), which today holds only a "Docs in progress" placeholder; a changelog entry and an announcement; and, at a milestone that adds a network destination, the [privacy page](../../../surfsense_web/app/\(home\)/privacy/page.tsx)'s list of destinations (section 3.2 lists three kinds today). The privacy page is also reviewed in M0.

| | Name | Depends on | Rough |
|---|---|---|---|
| M0 | Fix today's gaps (2.1.x, starts now) | nothing | 1–2 weeks |
| M1 | Clean engines and the eval harness | M0 | 3–4 weeks |
| M2 | Library folders | M0; in parallel with M1 and M3 | 2–3 weeks |
| M3 | Versions and Refine | M0; in parallel with M1 and M2 | 3–4 weeks |
| M4 | Claude measured, every model labelled | M1 | 3–4 weeks |
| M5 | The agent, on by default | M2, M3, M4 | 3–4 weeks |
| M7 | Spreadsheets and the security questionnaire (ships before M6 since 21 Oct 2026) | local paid bundles and the job-pack loader (08's item 11), since 22 Oct 2026; otherwise nothing outside it: it brings forward M1's job-gate harness (05 P0), 05 P3a's agent driver and 02 phase 3's job agents and job threads, and builds on the Excel revise engine and revised copies shipped in 2.2.0; not M1's clean-room fix, not M6 | roughly 8–16 weeks to the full beta; beta about mid-January 2027 (minimum) or mid-February (full), estimates, re-dated once the harness lands |
| M6 | Revised copies and the redline job | M1, M3, M5; after M7, the RFP job and the extraction stack | 4–6 weeks |
| M8 | Link a folder on disk | M2; in parallel with M5–M7 | 4–6 weeks |
| M9 | Down the ladder | M7 for the row-by-row runner; M6 for the redline workflow | 4–6 weeks |
| M10 | Job packs through plugins, enterprise, learning loop | the plugin installer and runtime; an Enterprise deployment answer | open |

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

Revised 21 Oct 2026: M1's clean-room fix leaves the critical path and stays scheduled for the contracts wave (M6). The questionnaire (M7) writes through the shipped Excel revise engine and does not wait for it. 05 P0's job-gate harness, `scripts/job_eval/`, moves ahead of the rest of M1 as M7's first item ([05](05-model-ladder-and-evals.md#phases), [08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#the-next-90-days)).

- **Goal:** finish the licensing work every engine waits on, and the harness every verdict comes from.
- **User sees:** Settings › About lists third-party notices. M1 is mostly under the surface; M2 and M3 carry the visible changes while it runs.
- **Contains:** 02 phase 0 (the clean-room fix) and 0L (the legal review of its records); 02 phase A (agent config and tool order, here because 01 phase 3a waits on it); 04 RT2 (the licence gate and notices); 05 P0 (the harness); the baseline re-run below.
- **Exit:**
  - On the clean tree at n=3, docx D01, D03 and D05 score 1.00 and contract-redline at least 77.7%. The Word-oracle results are committed, the similarity scan is near zero, and `check_provenance.py` passes in CI.
  - No `.dll` or `.pyd` falls outside the reviewed licence list.
  - The default Qwen3 4B has `grounded_qa` and `schema` rows from the RTX 3050 and the M2.
  - 0L has the provenance record, the scan report and the process record. Its answer gates selling to legal and security buyers, not this release. Whether it also gates the questionnaire, which ships no `docxkit` or `crlib` code, is a question for the lawyer (02's open question 1).
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
- **User sees:** "Answer / Work on files" on Claude; agent threads that read only the ticked sources; files the agent writes appear as artifact versions; the study-pack job; the agent in every installer, which 2.2.0 already shipped.
- **Contains:** 01 phases 3a and 3b; 03 phase 3 (the outputs sweep); 06 S3, J1 and J2; 05 P4b (rows for Claude, the `free_agent_tasks` family, and the OpenAI and Gemini columns). `ENABLED_BY_DEFAULT` was flipped to true earlier, on 7 Oct 2026.
- **Exit:**
  - Two agent threads keep separate views, and `create_artifact` refuses an unticked id; `agent_smoke` is 3 of 3 on Sonnet with per-thread folders; a file the agent writes in `outputs/` becomes a version.
  - `free_agent_tasks` (at least 10 cases) passes its gate on Sonnet. Each failed frontier case is labelled skill, tool, prompt or model, and fixed before lower rungs run it. Smoke and single-call columns for one OpenAI and one Gemini frontier model on the OpenAI-compatible wire are committed (05 P4b).
  - [agent.md](../../architecture/agent.md)'s "agent test" points to 05's `agent_smoke` and the capability rule. 04's size gate counts opencode and ripgrep (about +62 MB compressed, measured in 04), which installers carry since 7 Oct 2026.
  - Idle and busy private bytes per process are measured on a 16 GB Windows laptop with integrated graphics and recorded against the memory budget (Small things).
- **Depends on:** M2, M3 and M4.
- **Rough:** 3–4 weeks.

### M7: Spreadsheets and the security questionnaire

Revised 21 Oct 2026: M7 ships before M6's redline job and comes first in this list for that reason ([08-b2b-artifact-jobs](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#lead-the-security-and-due-diligence-questionnaire)).

Revised 22 Oct 2026: the questionnaire ships as SurfSense's first paid job plugin, which installs and runs only with a valid SurfSense license, the 30-day trial included ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)). The builds beneath it stay free in the app.

- **Goal:** the first buyer target.
- **User sees:** the security-questionnaire job in the job catalogue, with its 30-day trial, filling the customer's own workbook as a revised copy: each answer only from the values its cell's dropdown allows, locked and hidden cells untouched, a Source and a Confidence per answer, an Exceptions list, no "Yes" without a source, and reviewed answers written back to the answer library. Job setup recommends commercial terms (Team, Enterprise, the API) or a local model for NDA-bound evidence, since Claude's consumer plans, which the app reaches through the user's own Claude Code since 2.2.3, fall under consumer terms that allow training if the user opts in ([Anthropic](https://www.anthropic.com/news/updates-to-our-consumer-terms)).
- **Contains:** 02 phase 5a, revised: `surfsense-sheet-fill`, the questionnaire job skill, its mappings and its job agent, written on the Excel revise engine that shipped in 2.2.0. `revise_document`'s `set_cell` and `set_range` edit the sheet XML and keep charts, pivots and macros byte for byte ([`excel.py`](../../../surfsense_local/backend/modules/artifacts/revised_copies/engines/excel.py)). It no longer needs a new xlsx engine (XL) or M1's clean-room fix. It brings forward 02 phase 3's job agents and job threads, which its job agent needs. What is left is 08's items 1–8 ([08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#what-the-agent-needs-one-engine-for-many-jobs)):
  1. the job-gate eval harness (05 P0, brought forward from M1) and a synthetic corpus (M); `scripts/job_eval` does not exist yet;
  2. a baseline row of today's free-form Agentic fill (S), which brings 05 P3a's agent driver forward;
  3. workbook inspection and write-time validation: dropdowns (`dataValidation`), locked and hidden cells, merged ranges and scoping questions; `.xlsm` uploads; an `add_sheet` operation (M+S+S+S);
  4. provenance: a Source and a Confidence per answer, a check that the quoted passage exists in a ticked source, an Exceptions list, no unsupported "Yes" (M);
  5. answer library v1 in the existing `library` folder role, which no job uses yet, with import from past questionnaires and from Loopio or Responsive exports (M + S–M);
  6. per-row review (M);
  7. assurance basics: a no-script job profile that also turns off remote plugins, a per-workspace local-only lock, an SBOM and a data-flow statement (S–M + M);
  8. the row-by-row runner (L), 02 phase 5b, which generalizes `questionnaire_fill` into the shared per-row and per-file runner; it follows the beta unless it moves into it (Rough, below), and M9 runs smaller models on it.

  Also 06 J4 and 06 P1 (job plugins in the catalogue, with a paid job's license state on its card), and 08's item 11: local paid bundles from the deferred [bundles proposal](../plugins/bundles/README.md), the license server's route for paid bundles, and 02 phase 8's job-pack loader (`provides.skills`), brought forward from M10 and built beside items 1–5. The job's skill (`surfsense-security-questionnaire`), its job agent, mappings, eval cases and gold corpus, item 1's synthetic corpus included, are the plugin's, written outside the Apache-2.0 tree from their first commit. `surfsense-sheet-fill`, the harness, the engines, provenance and its checks, per-row review, the runner, the answer library with its import and export, and the assurance basics stay in the app under Apache-2.0 (What stays free and what is sold). No HECVAT, CAIQ or SIG question text ships until CSA and EDUCAUSE confirm terms in writing, and SIG is licensed: mappings read the user's own copy, and eval samples are synthetic. HECVAT 4 merged the Full, Lite and On-Prem forms into one file in February 2025, so the job models HECVAT 4.
- **Exit:** the questionnaire job passes the job gate on Sonnet; no delivered workbook carries an IronCalc value; the job states its supported document languages, and its family has a non-English case; the job installs and runs only with a valid SurfSense license, the 30-day trial included, and a lapsed license stops the job and nothing else, so the app, the answer library and every revised copy still open and export. Job pages wait for [08's quality check](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#kill-criteria): at least 90% correct on the gold set, no unsupported "Yes", and no broken dropdown or macro.
- **Depends on:** local paid bundles and the job-pack loader (08's item 11), which come forward from the deferred bundles proposal and M10's 02 phase 8; otherwise nothing outside it. Revised copies (03 phase 4) and the Excel engine shipped in 2.2.0, and the parts it needs from M1, M4, M5 and M6 come forward into it where they are not built yet: 05 P0 and P3a's agent driver, 05 P4a's capability levels, 06 J1's job entry points and 02 phase 3's job agents (Contains). Not M1's clean-room fix (its harness comes as item 1), not M6's redline, not the redline workflow.
- **Rough:** a beta on frontier models, as a paid plugin with its 30-day trial, about mid-January 2027 (items 1–5) or about mid-February (items 1–7). Both are estimates set before the job became a plugin; they now also wait on item 11 and are re-dated once the harness lands. The maintainer chooses the scope ([08, open questions](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer)). Item 8 follows the beta, or moves into it if the baseline row fails on context, cost or missed rows.
- **After it, the second wave.** RFP, RFI and DDQ responses from the same library start once the questionnaire passes its gate and a proposal manager joins as a design partner. They fill the issuer's own response workbook first, then the issuer's `.docx` Q&A table by cell address (M), then a compliance matrix once page citations ship ([08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#second-wave-first-in-line-rfp-and-ddq-responses-from-the-same-library)). The extraction stack follows, about March 2027: page-number citations (M), table-preserving PDF reading (M), `analyze_data` reading extracted PDF tables (S–M), a deterministic tie-out validator (M) and batch on the runner. It carries bank statements first, then medical chronologies, then contract and lease registers ([08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#second-wave-the-extraction-stack)). M6's redline job comes after it. Like the questionnaire, each of these jobs is a paid plugin, and the builds beneath them stay in the app.

### M6: Revised copies and the redline job

Revised 21 Oct 2026: the redline job moves behind M7, the RFP job and the extraction stack ([08-b2b-artifact-jobs](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#second-wave-the-extraction-stack)). A user-directed redline already ships on the revise tool, and revised copies, their report per operation and the download without internal comments shipped in 2.2.0. M1's clean-room fix leaves the critical path and stays scheduled for this contracts wave. The rules below for starter playbooks and the lawyer's review still hold when the redline ships.

Revised 22 Oct 2026: the redline job is a paid plugin ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)). The plugin carries the playbook review, the issues list, the starter playbooks, `crlib`, `review.py` and `playbook.py`. Asking the general agent to change one's own contract stays free: the [`surfsense-revisions`](../../../surfsense_local/backend/modules/agent/skills/surfsense-revisions/SKILL.md) skill and `surfsense_revise_document` return a revised copy with tracked changes today, and live case 9 ([`test_contract_redline.py`](../../../surfsense_local/backend/tests/live/test_contract_redline.py)) exercises that. A follow-up rewords that skill's contract and redline examples and renames the case.

- **Goal:** the playbook redline: a contract comes in, and a tracked-change redline in the customer's format comes out.
- **User sees:** "Make a revised copy" on a `.docx` source; engine edits with a report per operation; a download that leaves internal comments out by default and reports its leak scan, with "With changes (internal)" as an explicit second choice and the clean copy beside it; accept and reject in a side list; the redline job, a paid plugin with its 30-day trial, as a job thread on Claude, with "Run step by step" kept; the user's own playbook through "Make a playbook from this document"; "Mark as reviewed", which asks for the reviewer's name; a workspace export and import.
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
  - The redline job installs and runs only with a valid SurfSense license, and a lapsed license stops the job and nothing else: the user's own playbooks and revised copies still open and export.
  - The job-card and report-card Vitest tests pass axe checks, and a screen-reader pass over the revision side list is recorded.
  - Idle and busy private bytes per process are measured again on the 16 GB laptop, with an engine run and a local model turn at once.
- **Depends on:** M1 (the clean tree), M5 (01 phase 3a: per-thread registration and `copy_original`), M3 (03 phase 1) and the paid-bundle path M7 builds (08's item 11). The job is offered on a model once its row passes the job gate. The lawyer's review of the starter playbooks gates public redline pages, legal SEO pages and legal marketing; 0L gates selling to legal and security buyers.
- **Rough:** 4–6 weeks.

### M8: Link a folder on disk

- **Goal and user sees:** Link a folder on disk, indexed in place and watched, with root states (unavailable, permission denied, cloud-only, mass vanish), a root-level state when most of a root is OneDrive online-only files, and Office support for legacy formats.
- **Contains:** 01 phases 4a and 4b, with the OneDrive state; 04 RT3a, RT3b (shown as "Office support") and RT6. Creating the pack-hosting repository, its publisher App and its protected environment is an explicit RT3a task, owned by the maintainer as the GitHub organization's admin.
- **Exit:** 01's phase 4a platform tests pass from packaged apps on all three platforms, plus a packaged-app test on a Windows VM with OneDrive Known Folder Move; the dehydrated share of a real Documents folder is measured; an unavailable root keeps every document; a 600-file vanish is held; with Office support, `.doc`, `.xls` and `.ppt` are read, and without it the root header counts them; the privacy page lists `release-assets.githubusercontent.com` for packs.
- **Depends on:** M2. It runs in parallel with M5–M7. ADR 0041 waits on TDF's answer (outside dependencies below); the macOS packaged test needs a notarized build, which a dry run of the release workflow makes.
- **Rough:** 4–6 weeks.

### M9: Down the ladder

- **User sees:** job threads on 27–35B local models where rows pass; the questionnaire row by row and the redline as a workflow on smaller models where they pass; selection edits, with a keyboard path (select by paragraph in the outline or revision list).
- **Contains:** 05 P5a and P5b; smaller models on the row-by-row runner, which M7 builds (02 phase 5b, M7's item 8; revised 21 Oct 2026, [08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#what-the-agent-needs-one-engine-for-many-jobs) item 8); the redline workflow on smaller models where rows pass; 03 phase 5; local 27–35B rows when a machine exists. Nemotron 3.5 Bolt 74B-A9B, for 24 GB machines, and the 4 GB E4B are new local candidates (08 item 9).
- **Exit:** committed 4B and 8–14B rows, and 27–35B rows once a 24–32 GB machine exists; a selection edit can be made without a mouse.
- **Depends on:** M7 for the row-by-row runner; M6 for the redline workflow and 05 P5b, which needs P3b. The questionnaire's local rows need neither M6 nor P5b: they run through the runner once a 24–32 GB machine or a rented GPU is confirmed (08 item 9).
- **Rough:** 4–6 weeks.

### M10: Job packs through plugins, enterprise, learning loop

02 phase 8; 03 phase 7; 04 RT4 and RT5; 05 P6 (the self-test, after which "Test this model" joins the fixes); 06 P1 and E1. Revised 22 Oct 2026: SurfSense's B2B jobs are paid plugins ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)), so 02 phase 8's job-pack loader and `provides.skills`, with 06 P1, come forward to M7, which needs them for the questionnaire's plugin. M10 opens the mechanism to other publishers: their job packs install through the plugin system, are free or charge on their own service, and never use the SurfSense license ([ADR 0047](../../adr/0047-premium-plugins-are-source-available.md)). It depends on the plugin installer and runtime, and E1 on an Enterprise deployment answer. 02 phase 7 (a harness adapter or Goose spike) runs only on its trigger: 27–35B profiles failing through context overflow, or an end of opencode 1.x support. Duration: open.

### Outside dependencies

Chase dates are proposed; each owner confirms or moves theirs.

| Dependency | Blocks | Owner | Chase on |
|---|---|---|---|
| Haiku 4.5's retirement, "not sooner than" 2026-10-15 | the M1 gate's baseline | the maintainer, who runs the re-run | re-run committed by 2026-10-14 |
| A clean-room spec author, a separate implementer, and a reviewer who never opened `original_skills/` | M1's clean-room fix, off the critical path since 21 Oct 2026 | the maintainer | 2026-10-09 |
| A lawyer: first the provenance record and schema terms (02 phase 0L), then the starter playbooks; since 22 Oct 2026 also the license terms for local job plugins, a Business Source License with a narrower Additional Use Grant or a closed license ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)) | selling to legal and security buyers; public redline pages, legal SEO pages and legal marketing; the first job plugin's release, which waits on its terms. Whether 0L also gates the questionnaire, which ships no `docxkit` or `crlib` code, is asked first | the maintainer | engaged by 2026-10-16; that question and the terms question asked by 2026-10-31 ([08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#the-next-90-days)); records sent at M1's exit |
| CSA's and EDUCAUSE's written terms for CAIQ and HECVAT question text | shipping any of that text; M7 ships without it, reading the user's own copy | the maintainer | asked by 2026-10-31 ([08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#the-next-90-days)) |
| TDF's answer on a trimmed LibreOffice and its source mirror | ADR 0041's acceptance, RT3b (M8) | the maintainer | asked by 2026-10-16, chased 2026-11-06 |
| A 16 GB Windows laptop with integrated graphics | the memory budget at M5's and M6's exits | the maintainer | 2026-11-13 |
| A 24–32 GB machine | committed 27–35B rows (M9), and the questionnaire's local rows, which a rented GPU can also serve (08 item 9) | the maintainer, or community `matrix` submitters | 2026-12-01, unconfirmed |
| An Enterprise deployment answer | 06 E1 (M10) | the maintainer, at the first Enterprise conversation | when a customer asks |

## ADRs to write or amend

Numbers are proposed in this order from the current last ADR, [0039](../../adr/0039-document-scripts-run-without-approval.md), written for the create-and-edit slice. Whichever lands first takes the next free number.

| ADR | Records | From |
|---|---|---|
| **0040** Edits run shipped engines on model-written plans, make append-only versions, and never write the user's file | engine edits always tracked; all-or-nothing except workflows; head moves only on success; restore is a new version; no approval needed, since the engine path runs no model-written code (document scripts are ADR 0039's); bash allow-lists for skill scripts refused; a revised copy leaves the app without internal comments unless the user picks the internal download | 02 and 03 together |
| **0041** The running app may download pinned upstream runtime binaries after per-host consent | packs unaltered except for deleted files, pinned in the app, never SurfSense's own code; acceptance waits on TDF's answer (04's open questions) | 04 |
| **0042** Third-party skill material enters only through a provenance record | the licence gate binds contributors and packs | 02 |
| **0043** Claude goes through Anthropic's Messages API | amends ADR 0015: a connection's wire follows its host and `auth_kind` | 05 |
| **0044** What a model may do comes from a reviewed, measured capability manifest | extends ADR 0014. One workspace kind. The tier is prompt shape only. An unmeasured model keeps today's behaviour. A verdict reflects eval rows and live gates only, never a release policy such as a legal hold. The license never changes a verdict, and an organization policy may only lower one. What #2207 built differs: a measured level sets only the default mode ([#2220](https://github.com/MODSetter/SurfSense/issues/2220)) | 05 and 06, merged into one |
| **0045** Retrieval scope is resolved on the server and applied inside both legs | the KNN prefilter | 01 |
| **0046** SurfSense never loses a user's sources by surprise | Trash; read-only linked roots; no delete on unavailability; a mass vanish asks; placeholders never read; a database snapshot before every migration | 01 |
| **0047** Premium plugins are source-available and delivered by the license server | premium plugins, such as the scraper client, live under the Business Source License 1.1 in `surfsense_backend/app/proprietary/`; the license server hands them only to a valid license; the open-source installer never carries them; the app, the engines, the format skills and all job content (job skills, playbooks, questionnaire mappings, RFP templates, eval cases) stay Apache-2.0 in `surfsense_local/`, and job packs installed through the plugin system stay open source. Supersedes [ADR 0025](../../adr/0025-scraper-client-as-paid-plugin.md)'s "paid plugin code is Apache-2.0" premise and the [plugins proposal](../plugins/README.md)'s "every plugin is Apache-2.0" for paid plugins. Revised 22 Oct 2026: [ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md) supersedes its job-content clause for SurfSense's B2B jobs, which ship as paid plugins with their content; the app, the engines, the format skills and the shared job infrastructure stay Apache-2.0 in `surfsense_local/` | this page and the [strategy](../../../plans/community-local/file-agent-strategy.md) |

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

Revised 22 Oct 2026: SurfSense's B2B jobs are paid plugins ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)). This replaces the earlier rule that every catalogue job and all its content stay free, and the 21 Oct proposal of a paid side built around free jobs.

- **Free, in the app, under Apache-2.0:** everything the app does, on every model the capability allows. That covers Q&A, every Studio format, folders and linked folders, versions, revised copies and review, the general agent and its harness, the format skills, every engine (Word revisions as tracked changes, Excel and PowerPoint revisions, PDF tools, OCR, speech-to-text, data analysis; `docxkit` once it ships), the study pack, and the capability jobs: conversion, comparison, transcription, redaction and organizing as they are built. It also covers the shared job infrastructure: the job catalogue and its entry points, the eval harness, the row-by-row runner, provenance and its checks, per-row review, page citations, the tie-out validator, the `library` and `playbook` folder roles and the answer library with their import and export, the assurance basics and the bundle runtime. The line falls between an edit and a job: asking the general agent to change one's own file, a contract included, still returns a free revised copy with tracked changes (M6). The job is what is paid: the playbook, the review against it and the issues list, or a questionnaire's mappings and answer matching. Office support, the LibreOffice download, is also free. This keeps the pricing FAQ's "everything the app itself does stays free" ([`pricing-content.ts`](../../../surfsense_web/components/pricing/pricing-content.ts), line 150). The same FAQ answer says a paid licence is needed only for the scraper plugins and priority support; that stops being true when the first job plugin ships, so the pricing page, the README's plugin section and the Terms change in that release.
- **Paid license:**
  - SurfSense's B2B job plugins: the security questionnaire, RFP, RFI and DDQ responses, the contract redline (review against a playbook), bank statements into a ledger, medical chronologies, contract and lease registers, and B2B jobs added later. Each carries its job: its skill and agent, workflow steps, mappings, playbooks and starter playbooks, templates, eval cases and gold corpora. It runs on the user's machine, installs and runs only with an unexpired license (Individual, Team, or the 30-day trial for its term), and comes from the license server only to a valid license, never in the installer or the public plugin list;
  - premium plugins, such as the scraper client, and the public-data plugins [08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#how-surfsense-earns) plans as one experiment, capped at two weeks and built only if the questionnaire is on time;
  - priority support (maintainer question 10);
  - Enterprise controls, below.

  **The user's data is never locked.** Libraries, the user's own playbooks, outputs and revised copies are files that open and export without a license. When a license lapses the job plugin stops, and the app and the user's files keep working ([ADR 0019](../../adr/0019-offline-licenses.md)). Eval results of paid jobs stay public with their failures, and no page names a model as able to do a job before a committed row says so.

  **Where premium code lives.** `surfsense_backend` shrinks to the license server ([`app/license/`](../../../surfsense_backend/app/license/)) and the premium plugins, kept under the Business Source License 1.1 in [`app/proprietary/`](../../../surfsense_backend/app/proprietary/LICENSE), which the root [`LICENSE`](../../../LICENSE) already carves out. The license server delivers a premium plugin only to a valid license; the app downloads it after per-host consent ([ADR 0027](../../adr/0027-egress-consent-per-host.md)) and checks its sha256. A job plugin's content is written outside the Apache-2.0 tree from its first commit, in a folder with its own license file; nothing a plugin sells is committed to `surfsense_local/`. Local paid bundles are designed in the deferred [bundles proposal](../plugins/bundles/README.md); its runner ([`modules/plugins/bundles/runner/`](../../../surfsense_local/backend/modules/plugins/bundles/runner/)), SDK and author CLI are partly built, and with the job-pack loader they now come before the questionnaire's beta (M7). Everything else in this proposal is built in `surfsense_local/`; nothing new goes into the hosted backend's other code, which is archived at the [`archive/hosted-2026-09`](https://github.com/MODSetter/SurfSense/tree/archive/hosted-2026-09) tag.

  **Enforcement is delivery and terms, not the check in the app,** which any fork can strip (ADR 0019). The license server serves a job plugin and its updates only to a valid license. The Business Source License in [`plugins/remote/proprietary/LICENSE`](../../../plugins/remote/proprietary/LICENSE) grants production use to anyone who does not resell the work, which would let a business run a local job plugin without a license, so the local plugins' terms are open (question 12).
- **Enterprise:** an organization policy (agent off, local models only, or allow-lists per engine), local-only as the default, an audit log of the document scripts the agent ran, and later a sandbox. M7's assurance basics stay free as proof; Enterprise adds a third-party code audit, an org-wide local-only policy users cannot override, a local audit-log export, named support and invoicing. Enterprise is quoted; no validated price exists yet.
- **Later, once the jobs sell:** team features: a library shared across installs, roles, approval by a second person, a signed change log, and sealed per-client libraries. The test prices from before the decision, about $1,200 a year per team and $2,400 per MSP, stay hypotheses. The single-user library, its export and import, and per-row review stay free. Team features would need in-app extension points and a writable shared-library location, an exception to [01's decision 9](01-sources-and-folders.md#decisions) that linked roots are read-only. That exception is needed only then and stays a proposal ([01, open question 10](01-sources-and-folders.md#open-questions)).
- **Undecided:** the license terms for local job plugins and what a business pays for the jobs, the Individual license or a business license at a higher price (question 12).
- **Never sold:** a capability verdict. A license never raises one.
- **What users pay providers directly:** their own API usage. SurfSense shows estimates and enforces caps.

Pricing, positioning and channels belong to the [file-agent strategy](../../../plans/community-local/file-agent-strategy.md).

## Small things that are easy to forget

Each names the stream and phase that owns it.

- **Onboarding.** Curated rows show their capability line before download, with 06's note under the local list ([06](06-product-shape.md#how-the-capability-is-shown)). The first revised copy asks for the revision author. Linking a OneDrive-redirected folder explains "Always keep on this device" (01 phase 4a).
- **Sample files.** Each job ships a sample input under a licence that allows redistribution (a contract and a questionnaire), so a new user can try it without a confidential file (06 J3 and J4). The questionnaire's sample is synthetic and carries no HECVAT, CAIQ or SIG question text until CSA and EDUCAUSE confirm terms in writing; SIG is licensed, so mappings read the user's own copy ([08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#lead-the-security-and-due-diligence-questionnaire)).
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
| A lawyer finds `docxkit` or `crlib` too close to the originals, or a schema's terms forbid redistribution | provenance, scan and process record; review before B2B sales; a refused schema leaves the set. The questionnaire ships none of that code, and whether the review gates it is asked of the lawyer |
| CSA, EDUCAUSE or Shared Assessments object to question text in mappings or samples | no HECVAT, CAIQ or SIG question text ships until CSA and EDUCAUSE confirm terms in writing; SIG is licensed; mappings read the user's own copy, and eval samples are synthetic |
| The questionnaire misses its quality check, or a suite vendor ships a questionnaire skill with a persistent library that keeps dropdowns and macros intact | [08's kill criteria](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#kill-criteria): no job pages until the Sonnet row is at least 90% correct with no unsupported "Yes" and no broken dropdown or macro; on absorption the questionnaire drops to second wave |
| A fork strips the license check, or a job plugin's terms let a business run it without paying | delivery: the license server serves a job plugin and its updates only to a valid license ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)); the local plugins' terms are settled with the lawyer before the first one ships (question 12) |
| Businesses do not pay for the questionnaire once their trial ends | [08's kill criteria](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#kill-criteria): without 3 design partners committed in writing to buy about six weeks after the beta, the price and the job are re-checked before the next paid job; if fewer than 15% of business users who start the trial buy a license, or new annual revenue from all sources is under $15K, by 30 Jun 2027, no paid jobs are added beyond the questionnaire and the bets are re-ranked |
| NDA-bound evidence goes to a model on consumer terms | job setup recommends commercial terms (Team, Enterprise, the API) or a local model, and says why |
| A starter playbook is taken as legal advice | the "not reviewed by a lawyer; not legal advice" label on the job card, issues list and exported issues file; public redline pages, legal SEO pages and legal marketing wait for the review |
| Haiku 4.5 retires before the gate runs | re-run the baseline on Haiku and on Sonnet low by 2026-10-14, whatever M0's state |
| A migration cascade deletes chunks or threads, or an upgrade fails halfway | a snapshot before every migration, keeping the last two; plain `ALTER TABLE` only; count checks; tombstone-only directory sweeps |
| Below the frontier, almost nothing passes | the release rule keeps Q&A and Studio for the 4B; an unmeasured model loses nothing; a builder replaces `exec()` only where it scores at least the `exec()` baseline, so the product for free users is never worse than today |
| A job's skill drops out of a long run after opencode compacts | the skill is the per-job agent's own prompt, not a per-turn `system` string; a test forces compaction and checks the next request |
| Internal comments reach the counterparty | the external download is the default and removes them, with a leak scan in the report |
| The finished stack exhausts a 16 GB laptop | the memory budget at M5's and M6's exits; one place for the encoder; ingest yields to a streaming turn |
| Most of a linked Documents folder is OneDrive online-only | a root-level state with the fix; onboarding copy; SurfSense still never triggers a download |
| Apple's developer agreement lapses and notarization stops, as it did on 3 Oct 2026 | the account holder accepts it again, which needs no code; 04's RT0 runs the credentials check on dry runs and weekly, so a lapse shows before a release |
| opencode 1.x stops being maintained, or 2.x diverges | the pin; acceptance on 1.18.34; an adapter and a Goose spike on 02 phase 7's trigger |
| An injected document asks for a silent change or exfiltration | engines write tracked changes only; no network imports; the reminder strip; server tools refused; scripts sandboxed |
| A user's API bill surprises them | the ledger, estimates above $0.25, and a cap that answers 403 so it is never retried |
| Six streams for one maintainer | milestones that each ship alone; a user-visible point release at least every 3–4 weeks; M1, M2 and M3 in parallel, and M8 beside M5–M7; durations re-estimated from measured velocity after M1 |

## Open questions for the maintainer

1. **Who are the clean-room spec author and implementer?** *Recommended:* two agent sessions in fresh worktrees that hold neither `references/` nor the skills repository, with their file reads logged. A contributor who has never opened `original_skills/` signs off the pull request.
2. **When do you engage a lawyer, and for what?** *Recommended:* now, in parallel with M1's clean-room work, scoped to `provenance.json`, the scan report, the process record and the schema publishers' terms. Add the starter playbooks next. Revised 21 Oct 2026: with M1 off the critical path, ask first whether 0L gates selling the questionnaire, which ships no `docxkit` or `crlib` code; 08 plans that question by 31 Oct ([08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#the-next-90-days)). Revised 22 Oct 2026: ask by then also which license terms local job plugins carry (question 12).
3. **Does the redline job need the playbooks' lawyer review before release?** *Recommended:* no. The job is offered on a model once its eval row passes the job gate, and no verdict stands in for a legal hold. Until a lawyer reviews them, each starter playbook carries "Starter playbook — not reviewed by a lawyer; not legal advice" on the job card, in the issues list and in the exported issues file; a user's own playbook carries no label. Public redline pages, legal SEO pages and legal marketing wait for the review.
4. **What eval budget, and which account?** *Recommended:* a dedicated Anthropic workspace under the organization, about $650 per full sweep, a $300 monthly cap outside sweeps, and the `model-evals` environment reviewed by you.
5. **Who provides the reference machines?** *Recommended:* a 32 GB Apple-silicon Mac for the 27–35B rows, and a 16 GB Windows laptop with integrated graphics for the memory budget. Until then, 27–35B rows are screened only, and community `matrix` submissions are the other route. Since 21 Oct 2026 the questionnaire's local rows may also run on a rented GPU (08 item 9).
6. ~~**Who accepts the Apple Developer agreement, and when?**~~ Answered: the account holder accepted it by 4 Oct 2026, when the 2.1.0 dry run's re-run and v2.1.0's tag build were notarized; v2.2.0's was notarized with opencode inside.
7. **On routes that cache prompts, should a new thread default to Answer or to Work on files?** *Recommended:* default to Answer until M4 measures first-answer latency and cost on Sonnet. Switch to 05's rule only if Work on files is no slower for a one-line question.
8. **May the LibreOffice download be trimmed and re-hosted, and must its full source be mirrored?** *Recommended:* ask TDF now, well before RT3b in M8, mirror the exact source archive beside each pack, and name it "Office support (LibreOffice)".
9. **Should SurfSense ever trigger a cloud download of a placeholder?** *Recommended:* no. The user makes a file or a folder available offline in their sync client, guided by the root's online-only state, and the next reconcile picks it up.
10. **What does priority support mean, and who answers it?** *Recommended:* an email reply within two working days from the maintainer, covering installation, model setup and premium plugins, written on the pricing page before the first license is sold.
11. **What other small things do you remember wanting?** *Recommended:* list them against Small things above, so each gets an owning stream and a milestone.
12. **Which license terms do local job plugins carry, what does a business pay for the jobs, and is the beta the minimum or the full scope?** Not answered here: these are [08's open questions](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer) 1 to 3. The terms are a choice between a Business Source License with a narrower Additional Use Grant and a closed license, made with the lawyer before the first job plugin ships. The price is a choice between the Individual license and a business license at a higher one. Both beta dates also wait on local paid bundles and the job-pack loader. Revised 22 Oct 2026: the paid line and the Show HN are settled. The B2B jobs are paid plugins ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)), the maintainer posts the Show HN the week of 22 Oct 2026, and team features wait until the jobs sell (08's question 4).
