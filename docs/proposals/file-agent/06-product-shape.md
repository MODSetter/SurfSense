---
status: in-progress
code:
  - surfsense_local/backend/alembic/versions/<next>_thread_artifact.py
  - surfsense_local/backend/alembic/versions/<next>_workspace_settings_and_thread_jobs.py
  - surfsense_local/backend/modules/workspaces/settings.py
  - surfsense_local/backend/modules/workspaces/policy.py
  - surfsense_local/backend/modules/workspaces/schemas.py
  - surfsense_local/backend/modules/jobs/
  - surfsense_local/backend/modules/chat/models.py
  - surfsense_local/backend/modules/chat/schemas.py
  - surfsense_local/backend/modules/chat/router.py
  - surfsense_local/backend/modules/chat/handoff.py
  - surfsense_local/backend/modules/agent/engine_choice.py
  - surfsense_local/backend/modules/agent/agent_threads/turn.py
  - surfsense_local/backend/modules/llm/capability/org_policy.py
  - surfsense_local/backend/modules/resource_usage/disk.py
  - surfsense_local/backend/modules/artifacts/service.py
  - surfsense_local/backend/modules/artifacts/version_router.py
  - surfsense_local/backend/worker/studio/job.py
  - surfsense_local/backend/worker/workflows/run.py
  - surfsense_local/frontend/src/features/chat/
  - surfsense_local/frontend/src/features/studio/
  - surfsense_local/frontend/src/features/workspaces/
  - surfsense_local/frontend/src/features/sources/
  - surfsense_local/frontend/src/features/models/
  - surfsense_local/frontend/src/features/resources/
  - surfsense_local/frontend/src/features/updates/
  - surfsense_local/frontend/src/features/onboarding/model-step/
  - docs/adr/0044-a-score-sets-the-default-mode-never-whether-agentic-is-allowed.md
---

# Product shape

> SurfSense has one kind of workspace. The user never picks a mode. They pick a model, and what the app offers inside every workspace follows from that model's measured capability profile ([05](05-model-ladder-and-evals.md)): every model answers questions and makes Studio outputs, models that pass the job tests run jobs step by step or as a job thread, and models that pass the agent tests can also work on files freely. Jobs (study pack, security questionnaire, RFP response, contract redline) are listed on every model, and each one says how it will run on the selected model, or what it needs and the cheapest way to get it. Folders can carry job roles, a workspace can be marked local only, and a job's output can be marked reviewed. None of that is a workspace type. The general agent, the study pack, the engines and the shared job infrastructure are open source and ship in the app; the B2B jobs (security questionnaire, RFP response, contract redline) are paid plugins that run on the user's machine and unlock with a SurfSense license, the 30-day trial included ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)). A license adds those job plugins, the other premium plugins, support and Enterprise controls, and never changes what a model may do.

**Status, 11 Oct 2026:** a cut of S3 shipped in 2.2.0 ([#2207](https://github.com/MODSetter/SurfSense/pull/2207)), and it departs from this page. The composer offers Basic (Q&A) and Agentic for each new chat, so the interface does say "mode". Every model may pick Agentic unless a technical gate keeps it out: a stated no on tool calls, a window under 32,768 tokens, or no opencode. A measured level sets only the default, a user's pick is remembered per model, and a chat keeps its mode. `ThreadCreate` takes `mode` and `remember`; a gated request is refused with `409` and its code, and one whose agent does not start with `503` ([model capabilities](../../architecture/model-capabilities.md#the-modes), [agent](../../architecture/agent.md#which-threads-get-it)). Verdict labels, jobs, workspace settings, handoff and review are not built.

**Revised 21 Oct 2026:** the security questionnaire (J4, M7) now ships first and is the first buyer target, so M7 ships before M6's redline job. It runs on the shipped Excel revise engine and no longer waits for a new xlsx engine or M1's clean-room fix. RFP responses from the same library come next, then the extraction stack; the redline job (J3) moves behind it, and insurance is not a job. The parts that changed are the summary's job order, "How jobs are offered", the comparison table's questionnaire row, the organization policy, "Free, premium plugins and Enterprise", the J3 and J4 phases, the note to 02 and the open questions; the rest stands, decision 13 included. Sources: [08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#the-headline) and the [strategy](../../../plans/community-local/file-agent-strategy.md#who-buys-first-and-which-job-ships-first), checked against `dev` at `746c5fd66`.

**Revised 22 Oct 2026:** SurfSense's B2B jobs are paid plugins ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)). The security questionnaire, RFP responses and the contract redline each ship as a `paid` bundle that runs on the user's machine and installs and runs only with an unexpired SurfSense license: Individual, Team, or the 30-day trial for its term. The study pack, the general agent, the engines and the shared job infrastructure stay free in the app, and the user's files are never locked. This replaces the rule that all job content ships free in the app. The parts that changed are the summary, decision 11, "How jobs are offered", the playbooks' sharing, the comparison table's note, "Free, premium plugins and Enterprise", the J3, J4 and P1 phases, the offers test, the note to 02 and the open questions. Job order, decision 13 and the milestone and phase IDs stand; P1 comes forward from M10 to M7. Sources: ADR 0067 and [08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#how-surfsense-earns).

Stream 06 of the file-agent proposal. It turns [05](05-model-ladder-and-evals.md)'s `Capability` into what the user sees and owns the job catalogue that [02](02-skills-and-engines.md) and [03](03-editable-artifacts.md) wait on. Facts were checked against `dev_mod` at `0847e12f7` on 2026-10-03. Milestone numbers (M0 to M10) are the [README](README.md#milestones-in-order)'s. Both design-panel judges chose P1 (48) over workspace types (P2, 38–41) and user-picked modes (P3, 40); the grafts taken are under Options considered.

## The answer to the maintainer's question

"Do we provide users ability to create different types of workspaces or just preload a mode that works with that LLM model?"

**Preload the mode from the model. Do not add workspace types.** Three refinements make that honest:

1. **The mode comes from measurement**, not from parameter count or the prompt tier. The tier puts Claude Sonnet on an Anthropic key in `capable` and gpt-5-nano in `frontier` ([`classify.py`](../../../surfsense_local/backend/modules/llm/profile/classify.py); research I6).
2. **The word "mode" never appears.** The app shows what the selected model can do, item by item, with the reason when it cannot.
3. **Capabilities nest.** Work on files ⊇ jobs ⊇ answers and Studio. A stronger model never takes anything away, and an unmeasured model keeps everything it has today.

Why:

- **The variable is the model, and the model is app-wide.** `selected_models` is keyed by `model_type` ([`llm/models.py`](../../../surfsense_local/backend/modules/llm/models.py)), and the local runtime holds one resident model. A workspace type cannot carry a model, so it cannot carry a capability.
- **Types freeze today's limits into user data.** A derived mode changes with a reviewed pull request to `profiles.json`; a "simple" workspace made in October would need migrating when the user's model improves.
- **A new user cannot answer the question** of "simple" or "agent", Notebook or Matter, on day one.
- **Every benefit a type offered works without one:** folder roles, pinned jobs, a local-only policy and a review state all fit one workspace (Data model).
- **A type cannot be tested.** With no telemetry ([ADR 0016](../../adr/0016-no-telemetry.md)) its value is unknowable, while every capability verdict traces to an eval row.

## Today

All verified in the repo.

- `Workspace` has `id`, `name`, `cloud_id` and timestamps, and creation takes only a name ([`workspaces/models.py`](../../../surfsense_local/backend/modules/workspaces/models.py), `WorkspaceNameDialog` in [`workspace-rail.tsx`](../../../surfsense_local/frontend/src/features/workspaces/workspace-rail.tsx)).
- `create_thread` gives a thread to opencode when `selected_model_can_run_agent()` passes, "Chosen here and kept" ([`chat/router.py`](../../../surfsense_local/backend/modules/chat/router.py)). `ThreadCreate` holds only a title ([`chat/schemas.py`](../../../surfsense_local/backend/modules/chat/schemas.py)). The frontend creates the thread on the first send ([`use-chat-runtime.ts`](../../../surfsense_local/frontend/src/features/chat/use-chat-runtime.ts)), so a choice made in an empty composer can ride on `ThreadCreate`.
- `selected_model_can_run_agent()` passes only names in `TESTED_MODELS`, an empty frozenset, or anything under the developer switch ([`engine_choice.py`](../../../surfsense_local/backend/modules/agent/engine_choice.py)). It checks neither the window nor `auth_kind`, which may be `chatgpt`.
- Installers do not stage opencode: `ENABLED_BY_DEFAULT = false` in [`enabled.mjs`](../../../surfsense_local/electron/scripts/opencode/enabled.mjs), "Off until a model passes the agent test", unless `SURFSENSE_LOCAL_OPENCODE_ENABLED=1`. *Since 7 Oct 2026* it is `true`, and every installer stages opencode.
- An agent turn on a model that may not run the agent fails after sending, with a 409 ([`turn.py`](../../../surfsense_local/backend/modules/agent/agent_threads/turn.py)).
- `list_formats(session)` gates a format only on filled model slots and ignores the workspace its route receives ([`artifacts/service.py`](../../../surfsense_local/backend/modules/artifacts/service.py)). `SelectionRead.tier` is read by no frontend code ([`llm/schemas.py`](../../../surfsense_local/backend/modules/llm/schemas.py)).
- opencode runs one agent, `surfsense`, with `"skill": "deny"`; rewriting its config restarts it and ends any running turn ([`opencode_config.py`](../../../surfsense_local/backend/modules/agent/opencode_config.py)).
- The locked decision reads "the engine is the model's to decide, not the user's", and "a quick question also goes through the agent" ([`01-which-engine.md`](../agent/01-which-engine.md)).
- The pricing FAQ says "everything the app itself does stays free" and "The licence does not lock any of the app's own features" ([`pricing-content.ts`](../../../surfsense_web/components/pricing/pricing-content.ts), lines 150 and 155).
- Migration [`0005_workspace_cloud_id.py`](../../../surfsense_local/backend/alembic/versions/0005_workspace_cloud_id.py) added a column to `workspaces` with `batch_alter_table`, while `PRAGMA foreign_keys = ON` was already set for every connection ([`shared/db.py`](../../../surfsense_local/backend/shared/db.py), since 2026-09-03) and `documents.workspace_id` cascades on delete. Any new `workspaces` column must be a plain `ADD COLUMN`.
- That rebuild, and 0011's rebuild of `documents` ([`0011_document_cancelled_status.py`](../../../surfsense_local/backend/alembic/versions/0011_document_cancelled_status.py)), never ran on a database with documents in it. Both are in v2.0.0's tree (revisions 0001 to 0011), and v2.0.0 (18 Sep 2026) is the desktop app's first release: v0.0.40's installers were built from `surfsense_desktop` by `desktop-release.yml`, and no `local-v*` tag, which `release-local.yml` builds from, exists (`git tag --contains`, `git ls-tree`). Every install therefore ran them inside its first upgrade, on an empty database. No later revision through 0023 rebuilds `workspaces` or `documents` in its upgrade. Nobody needs telling.

## Decisions

1. **One workspace kind.** No `kind` or `template` column, no per-workspace model. *Reason:* the model is app-wide, and one workspace often serves several jobs (a policy library feeds questionnaires and RFPs, I8).
2. **The capability decides; the user never picks a mode.** Threads, formats, job levels, edit entry points and skills all read [05](05-model-ladder-and-evals.md)'s `capability_of()`. *Reason:* every verdict then traces to an eval row.
3. **Show capability, never the word "mode".** Each item carries one of 05's four verdicts and a one-line reason where it appears. *Reason:* otherwise jobs vanish unexplained.
4. **When the capability allows both engines, a new thread offers "Answer" or "Work on files".** The switch defaults to `capability.default_engine` and is never shown when the agent is unavailable, so no user sees a locked control. A thread keeps the engine it was created with. *Reason:* a quick question should not be an opencode loop by obligation; P3's cost point, narrowed to two states. This amends [`01-which-engine.md`](../agent/01-which-engine.md): the model decides which engines a thread may use, and the user chooses between them only when there are two.
5. **Jobs are catalogue entries listed on every model.** A job runs at the highest level the capability grants and can always run lower ("Run step by step"), never higher. *Reason:* nesting, and a frontier user may want the cheaper path.
6. **Folder roles persist; templates only create folders and pin jobs.** Roles live on 01's `folders.role`; pinned jobs in `workspaces.settings`. *Reason:* P2's graft; a rename must not erase meaning.
7. **A workspace may be local only.** `workspaces.settings.egress.local_only` refuses every remote model for that workspace's runs, with the reason, before any request leaves. *Reason:* legal and security buyers ask this first, and it is policy, not a mode.
8. **Untested is offered after one inline confirmation per model.** *Reason:* the reviewed profile always lags provider releases; a Settings toggle would hide the path.
9. **A model change never strands work.** The composer says before sending that a thread cannot continue, and offers a handoff that copies the scope, links the artifacts and quotes the last turns, with no model summary.
10. **Job outputs that leave the app carry a self-attested review state** that informs and never blocks. *Reason:* buyers need a record of who approved what, and on a single-user app with no identity that record can only be the reviewer's own word, so the interface and the docs say "self-attested".
11. **The license never changes a capability verdict; an organization policy may lower one.** For a job, a license decides only whether its paid plugin installs and runs ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)). *Reason:* the pricing FAQ, [ADR 0019](../../adr/0019-offline-licenses.md), and P3's enterprise policy.
12. **Reasons cross the wire as codes with values, rendered by the ICU catalogs.** *Reason:* [ADR 0030](../../adr/0030-formatjs-renders-interface-text.md); 05's `Reason(code, values)` carries them, and the frontend renders each through the catalogs.
13. **The redline job has one release gate: its eval row.** It is offered on a model once that model's row passes the job gate. Without a passing row its card shows what the row says ("Not measured" or "Not on this model") and no run action; it has no unmeasured default. The playbooks' lawyer review gates labels and marketing, never a verdict: until it happens, each starter playbook says "Starter playbook — not reviewed by a lawyer; not legal advice" on the job card, in the issues list and in the exported issues file. *Reason:* a verdict only ever reflects eval rows (or an organization's own policy, decision 11), so "Not on this model" cannot stand for a legal hold.

## Design

### What the user sees, by capability

05's `Capability` has `engines`, `default_engine`, `jobs`, `formats`, `edit_rungs`, `skills`, `bash`, `source` and `min_window`. Each item's verdict is `recommended`, `available`, `untested` or `unavailable`.

| Capability | Composer | Studio formats | Jobs | Artifacts |
|---|---|---|---|---|
| `engines = {chat}`, agent unavailable | no switch; every thread answers | as today; a tile shows a verdict only when it is `unavailable` | each job card shows its level: "Runs step by step", or "Needs a model tested for this job" with the fix | Refine where `edit_rungs` has rung 1; otherwise "Regenerate with an instruction" only |
| agent `untested`, live gates pass | switch shown; "Work on files" marked "Not measured", confirmation on first use | as above | job threads offered as "Not measured" after the same confirmation, except the redline, which waits for its row | as above, plus rung 3 under a confirmed agent |
| agent granted | switch shown, default from `default_engine` | all offered formats | "Runs with the agent" (recommended), "Run step by step" kept | rungs per format, including multi-step edits |

The 4B user's screen therefore never shows an agent control, and the frontier user's screen never hides the cheaper path. 05 grants the free agent only on passing `agent_smoke` and `free_agent_tasks` rows (multi-source briefs, multi-turn revisions, CSV summaries without a system Python, find-and-cite across a large folder), so "Work on files" is measured on the general file work it is offered for, not only on the redline and docx jobs.

### How the capability is shown

**Words.** Defined once in `frontend/src/features/models/capability-copy.ts`, through the ICU catalogs ([ADR 0029](../../adr/0029-icu-translation-catalogs.md)):

| Verdict | Label | Detail line |
|---|---|---|
| `recommended` | Best on this model | the evidence: "Passed 7 of 7 redline cases · Sonnet 5.5 · 2 Nov 2026" |
| `available` | Tested | the same evidence line |
| `untested` | Not measured | "SurfSense has not measured this on {model}." |
| `unavailable` | Not on this model | the reason code's text, then the cheapest fix |

**Where.**

- **Model rows** in the composer's [`ModelPicker`](../../../surfsense_local/frontend/src/features/chat/model-picker.tsx), Settings › Models and the onboarding text step ([`step-copy.ts`](../../../surfsense_local/frontend/src/features/onboarding/model-step/step-copy.ts)) gain one line, such as "Answers · Studio · Jobs step by step · Not measured" or "Answers · Work on files · Redline with the agent · Tested". Curated local rows show it before download.
- **Under the local list in onboarding:** "Redlines and working on files need a model tested for them: a larger local model, or Claude with your own API key." It leads into the existing server path, with today's consent.
- **Job cards** carry the level, the evidence line and, on remote paths, 05's per-run estimate.
- **The thread header** names engine and model ("Answer · Qwen3 4B", "Working on files · Sonnet 5.5") and, on remote paths, the thread's spend from 05's ledger, labelled an estimate.

**Reasons** become `Reason(code, values)` in 05's `modules/llm/capability/schema.py`: `window_below_floor` (`{needed, has}`), `tool_calls_unconfirmed`, `chatgpt_plan_no_tools`, `measured_failure` (`{family, score, bar}`), `measured_on_build` (`{tag}`), `not_measured`, `org_policy`, `workspace_local_only` (`{host}`), `model_unreachable` (`{host}`), `agent_unavailable`, `missing_role` (`{role}`), `playbook_invalid` (`{rule, problem}`). No code stands for a hold SurfSense places itself, such as a pending legal review. The frontend maps each to a message and the cheapest fix: "Choose another model", "Add your own API key", "Free about {gb} GB", "Fix the playbook". "Test this model" joins the fixes only when 05's self-test (P6, M10) ships; until then no surface offers it.

### Threads: Answer and Work on files

- `frontend/src/features/chat/engine-switch.tsx` (new) is a two-state control in an empty thread's composer. It renders only when `"agent"` is in `capability.engines` or the agent verdict is `untested` with every live gate passing.
- Release builds carry opencode since `ENABLED_BY_DEFAULT` turned true on 7 Oct 2026, ahead of 05's `agent_smoke` and `free_agent_tasks` rows and 03 phase 3. v2.2.0 (9 Oct 2026) is the first release that carries it, on all three platforms, notarized on macOS.
- The default is `capability.default_engine`, which 05 sets to `agent` only on paths that cache prompts (`anthropic-native`, `llamacpp`) and to `chat` elsewhere. Whether a cached route should default to Work on files is the README's [maintainer question 7](README.md#open-questions-for-the-maintainer): new threads default to Answer until M4 measures first-answer latency and cost on Sonnet, and move to 05's rule only if Work on files is no slower for a one-line question. The last choice per workspace is remembered in `localStorage` (`surfsense:new-thread-engine:v1`, failures ignored), and only when the capability still allows it.
- The first send carries `ThreadCreate.engine`. After that the control becomes the header label: a thread keeps its engine ([agent README](../agent/README.md), Locked decisions).
- Choosing "Work on files" on an unconfirmed untested model shows an inline notice: "SurfSense has not measured working on files with {model}. Results may be wrong or incomplete, and on an API key each step costs tokens." Confirming calls `POST /llm/capability/confirmations` (05); Settings › Models can revoke it.
- A message naming a Studio format by its label (a word match against `FORMATS`, no model call) gets a chip under the answer, "Make this a Slides deck". It never acts on its own.
- While a job holds the one llama-server slot, an Answer thread on the local model shows "Waiting for the running job" instead of a silent stall (the README's whole-stack budget).

### How jobs are offered

**The catalogue.** `modules/jobs/catalog.py` holds frozen `Job` entries, shaped like Studio's `Format`:

```python
@dataclass(frozen=True)
class Job:
    key: str                         # "contract-redline"
    roles: tuple[RoleNeed, ...]      # what the form asks for, and from which role folder
    skill: str | None                # 02's job skill: the prompt of agent surfsense-job-<key>
    workflow: str | None             # 02's workflow for the step-by-step run
    formats: tuple[str, ...] = ()    # Studio formats a format bundle runs
    target_suffixes: tuple[str, ...] = ()  # originals it can revise
    review: bool = False             # whether its outputs carry a review state
    needs_passing_row: bool = False  # offered on a model only once its row passes the job gate
    languages: tuple[str, ...] = ("en",)  # document languages the job supports, shown on its card
```

| Job | Roles (required; optional) | Job thread (agent, skill) | Step by step | Output | Ships |
|---|---|---|---|---|---|
| `study-pack` | evidence | none | summary, flashcards, quiz and mind map over the scope, on the Studio queue | Studio artifacts | M5 (J2), free in the app; today's Studio suffices |
| `security-questionnaire` | target (.xlsx, .xlsm), evidence; library | `surfsense-job-security-questionnaire`, `surfsense-security-questionnaire` | 08's row-by-row runner, which generalizes 02's `questionnaire_fill` | a revised copy of the customer's workbook, with a Source and Confidence per answer and an Exceptions list on a new sheet or in a companion workbook | M7 (J4), before M6's redline job, as a paid plugin: a beta on frontier models, design partners on the 30-day trial, about mid-January 2027 (minimum scope) or mid-February (full scope), both estimates that now also wait on local paid bundles and the job-pack loader (08's item 11) and are re-dated once the harness lands; on the shipped Excel revise engine, with no wait for a new xlsx engine, M1's clean-room fix or the redline workflow |
| `rfp-response` | target (the issuer's response workbook; later its `.docx`), evidence; library | `surfsense-job-rfp-response`, `surfsense-rfp-response` | later | a revised copy of the issuer's own response workbook first; then the issuer's `.docx` Q&A table filled by cell address; a compliance matrix only after page citations | a paid plugin; second wave: after the questionnaire passes its gate and a proposal manager joins as a design partner |
| `contract-redline` | target (.docx), playbook; evidence | `surfsense-job-contract-redline`, `surfsense-contract-redline` | 02's `contract_redline` workflow | a revised copy (03) | M6 (J3), as a paid plugin, behind the extraction stack; after 02 phases 0, 1, 1b, 3 and 4 and 03 phase 4; on each model once its row passes the job gate (decision 13) |

**Order.** The questionnaire fills a revised copy of the customer's own workbook from the company's policies and an approved answer library, through `revise_document`'s `set_cell` and `set_range` operations ([`excel.py`](../../../surfsense_local/backend/modules/artifacts/revised_copies/engines/excel.py)), which edit sheet XML and keep charts, pivots and macros byte for byte. Its remaining work is 08's [items 1 to 8](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#what-the-agent-needs-one-engine-for-many-jobs): the eval harness and corpus, a baseline row, workbook inspection and validation, provenance and the answer library (in the `library` folder role, importing past questionnaires and Loopio or Responsive exports) for a minimum beta; per-row review and the assurance basics for the full one; then the row-by-row runner. As a paid plugin it also needs item 11, local paid bundles and the job-pack loader, beside items 1 to 5. Which beta scope ships is the maintainer's open decision ([08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer)).

RFP, RFI and DDQ responses from the same library (`rfp-response`) follow, once the questionnaire passes its gate and a proposal manager joins as a design partner. Then comes the extraction stack, about March 2027 (an estimate): page-number citations, table-preserving PDF reading, `analyze_data` reading extracted PDF tables, a deterministic tie-out validator and batch on the runner, carrying bank statements, then medical chronologies, then contract and lease registers ([08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#second-wave-the-extraction-stack)). The playbook redline comes after it, and decision 13's rules hold when it ships; a user-directed redline already ships on the revise tool. The reason is October's market: Copilot for Legal in Word, Clio's Review Playbooks and Anthropic's Claude for Legal with Claude for Word all write native tracked changes against a playbook, so what stays distinct is a library the customer owns, filled into the requester's own file, on any model ([08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#what-changed-since-29-september)). Insurance is not a job ([08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#skip-insurance)).

The questionnaire's step-by-step run is 08's row-by-row runner (item 8): the app retrieves per row, the model answers under a schema and the engine writes. It generalizes 02 phase 5b's `questionnaire_fill` into the shared per-row and per-file runner, and arrives after the beta, or earlier if the baseline row fails on context, cost or missed rows. Until then the job runs only as a job thread, on a model whose row passes or after the "Not measured" confirmation.

`study-pack` has no measured job level of its own: it is offered when its formats are, and its verdict is the weakest of theirs. The other jobs take their level from `capability.jobs[key]`: `job_thread`, `workflow` or `off` (05 section 4). A job with `needs_passing_row` (`contract-redline`) gets no unmeasured default: on a model without a row its card says "Not measured" with `not_measured` and offers no run, and on a failed row it says "Not on this model" with `measured_failure`. Each card lists the job's document languages; 05 adds at least one non-English case per job family.

**Paid jobs.** `security-questionnaire`, `rfp-response` and `contract-redline` are paid plugins, and so is each later B2B job ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)). Their catalogue entries stay in the app, so their cards are listed on every model for every user. Each plugin brings its job's skill and agent, workflow steps, mappings, playbooks, templates and eval cases; 02 phase 8's job-pack loader (`provides.skills`) adds its skill and job agent. Without a license, a paid job's card offers the 30-day trial. With a license or the trial, the license server delivers the plugin and the card runs it at the level the model earns. With a lapsed license, the card is locked and says why; the job's outputs and revised copies stay in Studio, and the user's libraries and playbooks stay in their folders, opening and exporting as before. The license state sits beside the verdict and never changes it (decision 11).

**Roles.** `modules/jobs/roles.py` holds `Role`, a `StrEnum` of `evidence` (what answers come from), `target` (the file the job revises or fills), `playbook` (the rules it applies) and `library` (past answers and proposals to reuse). 01's `folders.role` is validated against it in code, with no CHECK, so a new role never needs a rebuild. A target role marks a folder; the job form picks one file from it, newest first.

**Templates.** "Set up for a job" exists in two places: an optional step in `WorkspaceNameDialog` ("Start from a job") and a button on any job card. It calls `POST /workspaces/{ws}/jobs/{key}/setup`, served by `modules/jobs/setup.py::set_up_job()`, which:

1. creates any missing role folder in the Library through 01's `ensure_folder_path`, with a localized name ("Policies", "Past answers", "Received", "Playbook") and its `role`;
2. reuses a folder that already holds the role, so a questionnaire and an RFP share one evidence folder;
3. adds the key to `workspaces.settings.jobs.pinned`;
4. for `security-questionnaire` and `contract-redline`, asks once whether the workspace's files may go to a cloud model, and sets `egress.local_only` on a no. When the selected model runs on a Claude Pro or Max plan, which falls under consumer terms that allow training if the user opts in, it recommends commercial terms (a Team or Enterprise plan, or the API) or a local model for NDA-bound evidence ([08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#lead-the-security-and-due-diligence-questionnaire)).

It never removes or renames anything. A role can also be set on any folder, linked roots' root folders included, from the folder's menu (01's `PATCH /folders/{id}`).

**Playbooks.** The redline needs crlib's structured playbook, whose rule ids the workflow's schema enumerates, not a folder of prose. [02](02-skills-and-engines.md) defines the format and keeps each playbook as a typed file in the `playbook` role folder: a SurfSense-owned JSON beside the document it came from. This stream adds the user's side, in M6 (phase J3b):

- **"Make a playbook from this document"** on a positions document in the playbook folder runs 02's drafting workflow. The drafted rules open in `studio/playbook-form.tsx`, a form where the user reviews and edits each rule; nothing is used until they save it.
- **Validation before a run.** `start_job_run()` asks 02 to validate the chosen playbook first. An empty playbook folder disables the action with `missing_role`; a playbook that fails validation disables it with `playbook_invalid`, naming the rule and the problem, and "Fix the playbook" opens the form.
- **Labels.** The starter label (decision 13) belongs to the shipped starter playbooks only. A user's own playbook carries none.
- **Sharing.** A playbook, like a library folder, exports as one file a colleague can import. Sharing beyond files is out of scope for v1, since the app is single-user and local; the workspace export bundle ([README](README.md), M6) is the sharing path. A user's own playbook is their data: it opens, exports and imports without a license ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)). A run against it, and drafting one with "Make a playbook from this document", need the redline's plugin, which carries `crlib` and the drafting workflow ([02](02-skills-and-engines.md) section 7); how an import is validated without `crlib` is 02's open question 9.

**Where jobs appear.**

- **Studio** gains a Jobs group above the formats. Pinned jobs come first; the rest sit under "More jobs". Each card shows the level, the evidence line, the missing roles and the action.
- **A job card's action** stays disabled until its required roles are filled, and names the missing one: "Add the questionnaire you received to Received."
- **The source row** of a `.docx` or `.xlsx` original ([`sources-panel.tsx`](../../../surfsense_local/frontend/src/features/sources/sources-panel.tsx), and the source preview) gains "Make a revised copy", listing the jobs whose `target_suffixes` match, each with its level.
- **A sample input** ships with the questionnaire and the redline (a synthetic questionnaire; a contract under a licence that allows redistribution), so a new user can try the job without a confidential file. No CAIQ or HECVAT question text ships until CSA and EDUCAUSE confirm terms in writing, and none from SIG, which is licensed; the questionnaire's mappings read the user's own copy, and its eval samples are synthetic.
- **The composer's `/`** lists the jobs. In an Answer thread it opens the job's short form (target file, evidence folder) rather than taking free text: small models choose skills less reliably (0.845 for Gemma-3-4B against 0.995 for Qwen3-30B, research E3), so the harness picks. In a Work-on-files thread, `/` lists the same jobs and opens a job thread for the chosen one.

**Running a job.** `POST /workspaces/{ws}/jobs/{key}/runs {target_document_id?, source_scope?, instructions?, run_as?}`, served by `modules/jobs/start.py::start_job_run()`, first calls `require_model_allowed()`. `run_as` defaults to the recommended level; a lower one is accepted, a higher one is a coded 409.

- **`job_thread`**: an agent thread with `job_key`, a `source_scope` from the role folders (`modules/jobs/inputs.py::job_scope()`) and a first turn written from the form. Each turn, 02's `send_turn(agent="surfsense-job-<key>")` selects the job's predefined opencode agent, written into the config once with the skill body as its `prompt`. The skill so survives opencode's auto-compaction, which a per-turn `system` string does not ([02](02-skills-and-engines.md)), and no turn rewrites the config.
- **`workflow`** with a target: 03's `start_revised_copy(job=key, instructions=…)`, which calls 02's `start_workflow()`.
- **A format bundle** (`study-pack`): one Studio artifact per format over the job's scope, queued in order.

`GET /workspaces/{ws}/jobs` (`modules/jobs/availability.py::job_offers()`) returns each job's level, verdict, reason, evidence, `missing_roles`, `pinned` and estimate. Like `capability_of()`, it never loads a model. A long job that finishes while the window is unfocused raises an OS notification.

### Artifacts: Refine and review

- **Refine.** An artifact card shows "Refine" when `capability.edit_rungs[format]` includes rung 1 or higher. Until 05 P4a supplies `edit_rungs` in M4, R1 (M3) shows it on the five spec-backed formats (summary, mind map, flashcards, quiz, html) as "Not measured", 05's unmeasured default. It opens the artifact's refine thread, created the first time with `chat_threads.artifact_id` set, the artifact attached and 03's Edit as the primary send action. Each Edit turn is 03's `MessageCreate.edit` against the head and makes one version. The new-thread switch applies, so an agent-capable model can refine with the agent (rung 3). On a revised copy, which is file-backed, Refine means 03's workflow edit or the agent.
- **Without an edit rung** (03's question on a model without edit capability), the card offers "Regenerate with an instruction" only.
- **Review.** For jobs with `review=True`, "Mark as reviewed" (`POST /artifacts/{id}/versions/{n}/approve {reviewer, write_properties?}`) asks for the reviewer's name, prefilled from the workspace's `revision_author`, and records `approved_at` and `approved_by`. The tag reads "Reviewed by {name} (self-attested)", and the docs use the same word. Until then the head is tagged "Not reviewed", and its download says so with "Download anyway". Each new version starts unreviewed. In the Mark as reviewed dialog the user may tick "Record the review in the file" (03's `write_properties`); downloads of that version then carry the name and date in the copy's custom document properties, never in the stored version.
- **Downloads of a revised copy.** The default is 02's external copy (`docx.external`): internal comments removed and the leak scan in the report. "With changes (internal)" is the explicit second choice ([03](03-editable-artifacts.md)).

### When the model changes, and unmeasured models

The model is read per turn and per job, so a change takes effect at the next one.

| What is open | New capability | What happens |
|---|---|---|
| Answer thread | any | Continues on the new model, as today. If Work on files becomes available, one line offers a new thread. |
| Work-on-files thread | agent granted or confirmed | Continues; opencode takes the model per prompt. Skills and bash follow the capability on the restart a model change already causes (05). |
| Work-on-files thread | agent untested, unconfirmed | The inline confirmation appears before the next send. |
| Work-on-files thread | agent unavailable | The composer is disabled before sending, with the reason, and offers "Continue in a new chat". |
| Job thread | the job's level is `job_thread` | Continues. |
| Job thread | `workflow` | "Continue this job step by step" runs the job's workflow on the head of the thread's revised copy, as its next version. |
| Job thread | `off` | The reason and the fix; the thread's artifacts stay in Studio. |
| A running Studio, workflow or engine version | any | The picker asks first: "Switching models stops {job}. Its last good version stays." Confirming cancels it through 03's cancel. |
| Anything in a local-only workspace | a remote model | Refused before sending: "This workspace is local only. {model} runs on {host}." with "Choose a local model". Entering the workspace with a remote model selected suggests the last local model used. |
| Any thread or job on a remote model | the host cannot be reached | The composer says "{model} cannot be reached right now" (`model_unreachable`) and, where the job has a workflow, offers "Run step by step" on the last local model. An engine version in flight fails cleanly and the head stays where it was (03). Capability lines keep their verdicts, since reachability is not capability. |

**The handoff.** `POST /chat/threads/{id}/handoff {engine}`, served by `modules/chat/handoff.py::hand_off()`, creates a thread with the same `source_scope`, `job_key` and `artifact_id`. Its first message is stored as `content = {handoff: {from_thread_id, artifact_ids, quoted: [last 3 turns as stored]}}`. 03's `as_history()` renders it as quoted text; no model summarizes anything. The 409 in `turn.py` stays as the server's backstop, now with `{code: "agent_unavailable", values}` and `handoff: true`.

**Unmeasured models** get 05's default: answers, today's formats, workflow jobs as "Not measured", the agent and job threads after confirmation when the live gates pass. A job with `needs_passing_row` is the exception: it waits for its row. A format tile shows its verdict only when it is not `untested`; the model row carries one "Not measured". From M10 it also carries "Test this model", 05's self-test (section 9, phase P6), which never grants the agent.

### A free user on Qwen3 4B and a user on frontier Claude

Expected behaviour pending the matrix; no cell below is measured yet (05, Today). The questionnaire and redline rows assume a license or the 30-day trial, since both jobs are paid plugins; without one, their cards offer the trial.

| | Free user: Qwen3 4B, local | Claude Sonnet 5.5 on their own key, native Messages route |
|---|---|---|
| Window | 8K or 16K on common hardware (`plan_load`, [fit](../../architecture/local-models/fit.md)) | the catalogue's window |
| Composer | no switch; every thread answers in one call | "Answer" or "Work on files"; default Answer until M4's measurement settles maintainer question 7 |
| Q&A | grounded, cited; chat prompts were tuned only on 1.7B so far | the same, plus agent search and reading in Work threads |
| Studio | today's formats. After the create-and-edit slice, Word and PDF take the Markdown path for small models: the model writes Markdown and committed builders render it ([07](07-create-and-edit-mvp.md#after-the-slice)). Another Office format moves to 02's spec builder only where the builder scores at least today's `exec()` path on the 4B, measured before `runner.py` goes, and otherwise keeps `exec()` | all formats, schemas enforced through `output_config.format`. After the slice, Word and PDF keep the code path for strong models: a Python script SurfSense runs and keeps ([07](07-create-and-edit-mvp.md#after-the-slice)) |
| Study pack | step by step | step by step |
| Questionnaire | step by step once built (08's row-by-row runner, which generalizes 02 phase 5b): the app retrieves, the model writes one answer per question under a schema, the engine writes the cell | job thread over the whole workbook; step by step kept |
| Redline | step by step per clause group once the 4B row passes the job gate; until then "Not measured" with no run, and "Not on this model" if it fails | job thread on `surfsense-job-contract-redline`, native tracked changes |
| Refine | one located edit per turn on spec-backed formats, once `refine_spec` passes | multi-step edits, agent edits on revised copies |
| Free-form file work | not offered | Work on files with up to three skills; document scripts run in SurfSense's script runner, and there is no shell ([ADR 0039](../../adr/0039-document-scripts-run-without-approval.md)) |
| Leaves the machine | nothing | each request's contents, `count_tokens` calls included, to `api.anthropic.com`, after per-host consent ([ADR 0027](../../adr/0027-egress-consent-per-host.md)) |
| Cost | none | the user's API bill: per-thread estimate, a pre-job estimate above $0.25, a $5 per-job cap (05) |

A 27–35B local model on a 24–32 GB machine sits between: job threads where its rows pass, no shell (05 measures local rows with bash denied).

### Workspace policy

`modules/workspaces/settings.py` defines the JSON column's shape, keyed by the slice that owns each entry, as `SelectedModel.settings` is:

```python
class WorkspaceSettings(BaseModel):
    """Per-workspace choices; keys a newer build wrote are kept, not dropped."""

    model_config = ConfigDict(extra="allow")

    egress: EgressPolicy = EgressPolicy()   # local_only: bool = False
    jobs: JobSettings = JobSettings()       # pinned: list[str] = []
    revision_author: str | None = None      # 02 passes it to every engine write
```

`modules/workspaces/policy.py::require_model_allowed(session, workspace_id, model_types)` raises `LocalOnlyRefused(host)` when `local_only` is set and any slot the run uses resolves to a remote connection. It runs before chat turns, Studio creates and regenerates, job runs, thread creation and every agent turn, and again in `worker/studio/job.py` and `worker/workflows/run.py` before the first model call, since a queued job may meet a different model. The agent's model endpoint cannot tell the workspace and need not: a model change restarts opencode and ends the turn, so every agent turn passes the check in `turn.py` first.

### Organization policy (Enterprise)

`modules/llm/capability/org_policy.py::apply_org_policy(capability) -> Capability` runs last in `capability_of()`. It reads a machine-wide, administrator-written file (location in Open questions) with three controls: `agent: off | local_only | on`, an allow-list of models per engine, and `local_only_default` for new workspaces. It can only lower verdicts, each with the `org_policy` reason. It never reads the license. The per-workspace local-only lock (decision 7) stays free and is one of the questionnaire's assurance basics ([08, item 7](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#what-the-agent-needs-one-engine-for-many-jobs)); only an org-wide policy that users cannot override is Enterprise. An audit log of the document scripts the agent ran ([ADR 0039](../../adr/0039-document-scripts-run-without-approval.md)) and a sandbox come later and are not part of this stream.

### Free, premium plugins and Enterprise

**Revised 22 Oct 2026:** SurfSense's B2B jobs are paid plugins ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)), which replaces 02 decision 17's rule that all job content ships free. The rest of "who pays for what" is set here and in the [README](README.md#what-stays-free-and-what-is-sold).

- **Free, on every model the capability allows, under Apache-2.0 in the app:** Q&A, every Studio format, folders, the agent harness, the format skills, every engine (`docxkit` once it ships), the study pack and the capability jobs (conversion, comparison, transcription, redaction, organizing) as they are built, and the shared job infrastructure: the catalogue and its entry points, the eval harness, the row-by-row runner, provenance and its checks, per-row review, page citations, the tie-out validator, the `library` and `playbook` folder roles with import and export, the answer library with its import and export, the assurance basics and the bundle runtime. The user's own playbooks, revised copies, versions and review are free too. A user who asks the general agent to change their own file, a contract included, gets a free revised copy with tracked changes. No free user is told to buy a license to use the agent.
- **Paid job plugins:** the security questionnaire, RFP, RFI and DDQ responses, the contract redline (review against a playbook), and the later B2B jobs (bank statements into a ledger, medical chronologies, contract and lease registers). Each is a `paid` bundle as the [bundles proposal](../plugins/bundles/README.md) defines it: it runs on the user's machine, installs and runs only with an unexpired SurfSense license (Individual, Team, or the 30-day trial for its term), and is delivered by the license server only to a valid license, never in the installer or the public plugin list. It carries the job: its skill and agent, workflow steps, mappings, playbooks and starter playbooks, templates, eval cases and gold corpora; for the redline that includes `crlib`, `review.py`, `playbook.py` and the starter playbooks. Its content is written outside the Apache-2.0 tree from its first commit, in a folder with its own license file. When a license lapses the plugin stops, and the app and the user's files keep working ([ADR 0019](../../adr/0019-offline-licenses.md)). Paid jobs' eval rows stay public, failures included. The license terms for local job plugins are open: the Business Source License used for the remote plugins grants production use to anyone who does not resell the work ([08, open question 1](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer)).
- **Paid license:** the job plugins above; premium plugins, such as the scraper client, source-available under the Business Source License 1.1 in `surfsense_backend/app/proprietary/` and delivered by the license server only to a valid license ([README](README.md#what-stays-free-and-what-is-sold), ADR 0047); priority support; and the Enterprise controls below. `surfsense_backend` shrinks to the license server and the premium plugins. A license never changes a verdict. The pricing FAQ's line that a paid licence is only needed for the scraper plugins and priority support becomes untrue when the first job plugin ships; the pricing page, the README's plugin section and the Terms change in that release (ADR 0067).
- **The security questionnaire is the first paid job plugin.** It arrives in M7 (J4), ahead of the redline job, with its mappings in its plugin, delivered by the license server. It needs local paid bundles and the job-pack loader (02 phase 8, `provides.skills`) first; both were deferred and now come before its beta, beside 08's items 1 to 5. The single-user answer library and its export and import stay free in the app.
- **Job packs** come through the plugin installer (P1): 02 phase 8's loader adds a plugin's skills and job agents, and SurfSense's paid job plugins use it. Other publishers' job packs, from M10, are free or charge on their own service, and never use the SurfSense license (ADR 0047). A pack's job runs at the level the model earns, "Not measured" until its cases run.
- **Enterprise:** the organization policy, `local_only` by default, the audit log, later a sandbox and mirror (I8).
- **Beyond the jobs.** [08, how SurfSense earns](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#how-surfsense-earns) lists public-data plugins inside the same license, then team features, then Enterprise with assurance. Team features (a library shared across installs, roles, approval by a second person, a signed change log, sealed per-client libraries) come later, once the jobs sell. Local bundles are designed in the deferred [bundles proposal](../plugins/bundles/README.md), whose runner ([`bundles/runner/`](../../../surfsense_local/backend/modules/plugins/bundles/runner/)), SDK and author CLI are partly built. A team library would also need in-app extension points and a writable shared-library location, an exception to [01's decision 9](01-sources-and-folders.md#decisions) that linked roots are read-only; that exception is only needed then and stays a proposal. The license terms for local job plugins, the price of the jobs, the beta's scope and team features are 08's [open questions](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer).
- **Names.** [04](04-runtime-and-packs.md)'s LibreOffice download appears as "Office support" (Settings › Downloads; "Needs Office support" on cards), so "pack" in the interface always means job content.
- **Positioning:** Gemini Notebook keeps one notebook object and gates skills by plan ([Google](https://blog.google/innovation-and-ai/products/notebooklm/better-research-notebooklm/)); SurfSense gates by measured model capability, publishes the matrix, and runs the agent loop locally; a license adds the B2B job plugins and never changes a verdict. Job pages ([`08-b2b-artifact-jobs.md`](../../../plans/community-local/seo/08-b2b-artifact-jobs.md)) go live only once the job passes on at least one model; public redline pages, legal SEO pages and legal marketing also wait for the lawyer review. The questionnaire's pages come first: HECVAT 4 (one file since February 2025, when the Full, Lite and On-Prem forms merged), CAIQ v4, and SIG Lite read from the user's licensed copy ([08, pages and reach](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#pages-and-reach)).

### Data model

Two revisions, numbered at merge and hand-written ([ADR 0005](../../adr/0005-hand-written-migrations.md)): R1's `<next>_thread_artifact.py` in M3 and S2's `<next>_workspace_settings_and_thread_jobs.py` in M4.

```text
-- R1 (M3)
chat_threads      + artifact_id INTEGER NULL                 -- raw ALTER ... REFERENCES artifacts (id)
                      ON DELETE SET NULL                     --   ON DELETE SET NULL, as 0022 adds a key
-- S2 (M4)
workspaces        + settings JSON NULL                       -- op.add_column, never batch_alter_table
chat_threads      + job_key TEXT NULL                        -- plain ADD COLUMN; chat_messages cascades from it
```

- No CHECK on `job_key`; the catalogue validates it in code, so a new job never needs a rebuild.
- Owned elsewhere and used here: `folders.role` and `chat_threads.source_scope` (01), `capability_confirmations`, `model_checks` and `model_spend` (05), and `artifact_versions` with its `approved_at` and `approved_by` (03, added by its phase 1 revision in M3).
- `test_migrations.py` checks that upgrade keeps every workspace, document, chunk, thread and message count.
- Both revisions run after 01 phase 0's `VACUUM INTO` snapshot (M0), which `upgrade_to_head` writes before applying any pending revision.

### Routes and code

| Where | Change |
|---|---|
| [`chat/schemas.py`](../../../surfsense_local/backend/modules/chat/schemas.py) | `ThreadCreate` gains `engine: Literal["chat", "agent"] \| None`, `job_key`, `artifact_id`; `ThreadRead` gains `job_key`, `artifact_id` |
| [`chat/router.py`](../../../surfsense_local/backend/modules/chat/router.py) `create_thread` | `selected_engine(session, requested=payload.engine)`, which 05's function gains; a disallowed engine is a coded 409 |
| [`turn.py`](../../../surfsense_local/backend/modules/agent/agent_threads/turn.py) | `require_model_allowed()`; the coded 409 with `handoff: true` |
| [`artifacts/service.py`](../../../surfsense_local/backend/modules/artifacts/service.py) | `list_formats(session, workspace)` reads 05's offers and the local-only reason |
| [`workspaces/schemas.py`](../../../surfsense_local/backend/modules/workspaces/schemas.py) | `settings` on read and update |
| new modules | `jobs/`, `chat/handoff.py`, `workspaces/settings.py`, `workspaces/policy.py`, `llm/capability/org_policy.py`; `resource_usage/disk.py`, served at `GET /system/disk` beside today's `GET /system/usage` ([`resource_usage/router.py`](../../../surfsense_local/backend/modules/resource_usage/router.py)); 03's `version_router.py` gains `approve` |
| frontend | `chat/engine-switch.tsx`, `chat-composer.tsx`, `model-picker.tsx`, `thread-panel.tsx`; `studio/jobs-group.tsx`, `job-card.tsx`, `job-form.tsx`, `playbook-form.tsx`, `artifact-panel.tsx`; `workspaces/workspace-rail.tsx`; `sources/sources-panel.tsx`; `models/capability-copy.ts`; `onboarding/model-step/step-copy.ts`; [`resources/resource-settings.tsx`](../../../surfsense_local/frontend/src/features/resources/resource-settings.tsx) (disk use); `updates/whats-new.tsx` |

## Options considered

### P2: workspace types (lost, 38–41)

A type chosen at creation (General, Notebook, Matter, Questionnaire, Proposal) set folders, roles, the job menu and featured formats; the model still decided how each job ran. It lost because the type is a question the user cannot answer at creation, and P2 conceded that this is its only difference from a well-built P1. Every concrete benefit it claimed works without a type. What remains is taxonomy cost (five empty states times capabilities times locales, a "which type?" decision per new job), vertical labels on folder templates until 02's engines exist, a legal claim in "Matter" while the playbooks have had no lawyer review, and no way to show under ADR 0016 that the type helps.

**Grafts taken:** persistent `folders.role` (in 01); `workspaces.settings` with `egress.local_only` by plain `add_column`; review state for jobs whose output leaves the app; job pages that land only after a passing row; "Continue this job step by step"; job actions that name the missing role. Its per-type opencode agents return as per-job agents: 02 writes one `surfsense-job-<key>` agent per job into the config once, with the job's skill as its prompt, and selects it per turn; the free agent's skill list varies only with the model.

### P3: modes the user picks per thread (lost, 40)

Ask, Create and Agent in every composer, the profile marking the recommended one. It lost because it reverses the locked decision that the engine is the model's; most free users would see a locked Agent in every composer, which reads as a paywall against the pricing FAQ; Create and Agent both make a redline on frontier models, doubling eval rows and support answers; and it is the costliest build (a thread `mode` column, a `create_turn` path, in-thread switching and forks).

**Grafts taken:** the four-value verdict vocabulary; the untested path with one inline confirmation; a Refine thread bound to the artifact; enterprise engine policy; per-thread cost; the handoff with quoted turns; a format chip that never switches. Its Ask/Agent split survives only as decision 4's two-state switch, shown when both engines are allowed.

### Also rejected

| Option | Why not |
|---|---|
| An invisible mode, like `tier` today | Jobs vanish without a reason; nobody can see what a model buys or what was tested |
| A Settings toggle as the only way to try an untested model (P1 as written) | Hidden; the inline confirmation sits where the choice is made |
| No switch, the default engine for every thread (judge J2's variant) | A frontier user would pay an agent loop for every quick question |
| `workspaces.template` | A workspace may serve several jobs; one column recreates a type |
| A model classifying each message as a job or a question | Misroutes are unequal and a 4B is unreliable at it (E4); forms cost less |
| A per-workspace model | One resident model; each workspace switch would reload one |

## Phases

| Phase | Scope | Depends on | Size | Milestone |
|---|---|---|---|---|
| W1 What's new | `updates/whats-new.tsx`: a short list of changes on first launch after an upgrade, linked to the [changelog](../../../surfsense_web/app/\(home\)/changelog/page.tsx) | nothing | S | M2 |
| R1 Refine thread | `chat_threads.artifact_id` and its revision, Refine on cards, regenerate-only fallback | 03 phase 2; until 05 P4a (M4), Refine shows on the five spec-backed formats as "Not measured", 05's unmeasured default, then reads `edit_rungs` | S | M3 |
| S1 Surface on a seam | `Reason` codes; capability lines in the picker, settings and onboarding; Studio reasons; the composer's pre-send warning in place of the 409; handoff; offline states. "Test this model" is left out until 05 P6 (M10) | 05 P4a: `capability_of()` with the unmeasured default and live gates, no rows | M | M4 |
| S2 Workspace data | its revision; `WorkspaceSettings`; `require_model_allowed()` at every call site; local-only and author settings; a disk-usage view in Settings › Resources adding up versions, the Trash (30 days), the engines' view cache (500 MB) and the agent's text cache as they land, and, from M8, packs | 01 phase 0's pre-migration snapshot | S | M4 |
| J1 Catalogue and roles | `jobs/` catalogue, roles, setup, offers; Studio Jobs group; Start from a job | 01 phase 1 (folders, `folders.role`) | M | M5 |
| J2 Study pack | the format-bundle run; job forms; `/` in Answer threads | J1 | S | M5 |
| S3 Answer and Work on files | the switch, `ThreadCreate.engine`, inline confirmation, thread cost | 05 P1, P2 and P4a (native route, confirmations); 01 phases 3a and 3b (per-thread scope); released with 05 P4b's Claude and `free_agent_tasks` rows and 03 phase 3; `ENABLED_BY_DEFAULT` is already true | S | M5 |
| J4 Questionnaire | its entries and setup question; a synthetic sample questionnaire. Revised 22 Oct 2026: the job is a paid plugin, with its mappings in the plugin ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)). M7 ships before M6's redline job | P1, with local paid bundles and the job-pack loader, before the beta; the shipped Excel revise engine and revised copies (2.2.0); 02 phase 5a, as revised: 08's items 1 to 5 for a minimum beta or 1 to 7 for the full one, `surfsense-sheet-fill`, the questionnaire job skill and its `surfsense-job-security-questionnaire` agent; item 7 includes S2's per-workspace local-only lock. Not a new xlsx engine, M1's clean-room fix or the redline workflow | S | M7 |
| J3 Redline | job thread and step-by-step entries, "Make a revised copy", self-attested review, the starter-playbook label; a sample contract under a redistributable licence; an OS notification when a long job finishes while the window is unfocused. The job is a paid plugin that carries `crlib`, `review.py`, `playbook.py` and the starter playbooks | P1; 02 phases 0 and 1 (the clean-room fix lands in M1, now off the critical path and kept for the contracts wave), 1b, 3 and 4; 03 phase 4. It ships after M7, the RFP job and the extraction stack | M | M6 |
| J3b Own playbook | "Make a playbook from this document", the playbook form, `playbook_invalid`, playbook export and import | J3; 02's playbook format, validation and drafting workflow | S | M6 |
| P1 Job packs | job plugins and packs from the plugin installer: their jobs in the catalogue, "tested on" lines, and a paid job's license state on its card (trial offered, licensed, lapsed). Revised 22 Oct 2026: SurfSense's paid job plugins need it, so it comes before J4's beta ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)) | 02 phase 8; the plugin installer; local paid bundles (08's item 11) | S | M7, before J4 (was M10); other publishers' packs in M10 |
| E1 Organization policy | `org_policy.py`, the policy file | an Enterprise customer's deployment answer (Open questions) | M | M10 |

Until 05's matrix lands rows, S1 to J2 ship today's behaviour with honest labels: every model is "Not measured", and no verdict is invented. Each milestone that ships a phase here adds a how-to page per new feature to the user docs.

## Tests

- `tests/unit/jobs/test_catalog.py`: every role exists in `Role`; skills, workflows and `study-pack`'s formats name real entries.
- `tests/unit/jobs/test_offers.py`, table-driven over capability × roles × settings: a missing role disables the action with `missing_role`; `workflow` offers only step by step, `job_thread` both; local-only with a remote model gives `workspace_local_only`; `study-pack` takes its weakest format verdict; `contract-redline` offers no run on a model without a passing row; a starter playbook carries the starter label and a user's own playbook does not; an invalid playbook disables the action with `playbook_invalid`; a paid job without a license offers the trial, a lapsed license locks it while its outputs stay listed, and neither changes its verdict.
- `tests/integration/jobs/test_runs.py`: `run_as` above the level answers 409; a `job_thread` run creates an agent thread with `job_key` and the role scope; a workflow run creates a revised copy; set-up twice creates no second folder and keeps a renamed folder's role; a `job_thread` turn names `surfsense-job-<key>` and sends no per-turn `system`; approval without a reviewer name answers 422.
- `tests/integration/chat/test_threads.py`: `engine="agent"` without the agent answers 409 with a code; `engine=None` follows `default_engine`; an agent thread whose model lost the agent gets `handoff: true`; the handoff keeps the scope and quotes the last three turns verbatim.
- `tests/integration/workspaces/test_local_only.py`: with `local_only` and a remote selection, a chat turn, Studio create, job run, thread creation and agent turn are refused before any provider call (the test provider fails if called); a queued Studio job fails with the reason at run time.
- `tests/integration/chat/test_offline.py`: with the remote host unreachable, a turn answers `model_unreachable` and a job with a workflow offers step by step on the last local model; a version in flight fails and the head is unchanged.
- `tests/integration/test_migrations.py`: no rebuild of `workspaces` or `chat_threads`; workspace, document, chunk, thread and message counts unchanged; the reflected `artifact_id` key matches the model.
- `tests/unit/llm/capability/test_org_policy.py`: policy only lowers verdicts; flipping the license state never changes `capability_of()`.
- Frontend: `engine-switch.test.tsx` (hidden without the agent, default from the capability, confirmation when untested); `job-card.test.tsx` (verdict labels, missing-role and `playbook_invalid` text, the starter label, step by step kept on agent-capable models, an axe check); `playbook-form.test.tsx` (nothing saved until the user saves); `model-picker.test.tsx` (capability line, no "Test this model" before P6); `artifact-panel.test.tsx` (Refine only with rung 1, the reviewer prompt, the self-attested tag, the download notice and the external copy as the default download).

## What this changes in other streams, ADRs and proposals

- **[ADR 0044](../../adr/0044-a-score-sets-the-default-mode-never-whether-agentic-is-allowed.md)** records what #2207 built instead: modes chosen per chat, a measured score setting the default mode. Still to record from this page: one workspace kind; the license never changes a verdict; organization policy may only lower one; no verdict stands for a hold SurfSense places itself.
- **[`01-which-engine.md`](../agent/01-which-engine.md) and the [agent README](../agent/README.md) "Where the agent appears":** the model decides which engines a thread may use; when it allows both, the user picks per thread at creation. "A thread keeps its engine" stands.
- **[01](01-sources-and-folders.md):** roles live on 01's `folders.role` with this stream's `Role` vocabulary (`evidence`, `target`, `playbook`, `library`); templates set them through `set_up_job()`.
- **[02](02-skills-and-engines.md):** section 6 reads 05's `Capability` (`engines`, `jobs[key].level`, `skills`, `bash`) through `policy_for(capability)`; job threads run on predefined `surfsense-job-<key>` agents; the playbook format, its validation and the drafting workflow behind "Make a playbook from this document" are 02's, and the form and failure codes are this stream's; the redline's release rule is decision 13 here; phase 5a now builds the questionnaire on the shipped Excel revise engine, with no new xlsx engine, and phase 5b's `questionnaire_fill` becomes 08's shared row-by-row runner; `workspaces.settings.revision_author` is created by this stream's revision. Revised 22 Oct 2026: decision 17's free job content gives way to paid job plugins, whose skills and job agents phase 8's job-pack loader adds, and phase 8 now comes before the questionnaire's beta ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)), as "Free, premium plugins and Enterprise" above sets out.
- **The free agent lists at most three skills** (02 decision 11, 05 section 4), following SkillsBench's drop at four or more.
- **[03](03-editable-artifacts.md):** 03's entry points read `capability_of(session).formats`, `edit_rungs[format]` and `"agent" in capability.engines`; it carries `approved_at` and `approved_by` on `artifact_versions`, and its approve route's `write_properties` puts the review record in downloaded copies' custom document properties; the external copy is a revised copy's default download; its questions for this stream are answered under "Artifacts: Refine and review".
- **[04](04-runtime-and-packs.md):** the interface calls the LibreOffice download "Office support", under Settings › Downloads.
- **[05](05-model-ladder-and-evals.md):** 05's P4a supplies the seam S1 builds on (the `capability/` package with the unmeasured default, live gates, confirmations and `SelectionRead.capability`, no rows) and P4b the rows, so the surface ships before the matrix; reasons are `Reason(code, values)`; `selected_engine()` takes `requested`; `apply_org_policy()` runs last in `capability_of()`; the free agent is granted on `agent_smoke` and `free_agent_tasks`; a job with `needs_passing_row` has no unmeasured default.

## Open questions

1. Where does the organization policy file live on each OS, is it signed, and do Enterprise customers deploy it by MDM?
2. ~~Are four roles enough for RFPs, where the solicitation is the target but the output is a new compliance matrix, not a revised copy?~~ Answered 21 Oct 2026: the RFP job's first output is a revised copy of the issuer's own response workbook, then the issuer's `.docx` Q&A table filled by cell address, so the four roles fit. A compliance matrix from a solicitation PDF waits for page citations, and the question returns with it ([08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#second-wave-first-in-line-rfp-and-ddq-responses-from-the-same-library)).
3. Which formats make the study pack, and should the user be able to drop one before running?
4. Job pages deep-link into "Set up for a job". Electron registers no protocol handler today; is a `surfsense://` handler wanted, given that it is new attack surface?
5. Should "Record the review in the file" be on by default, given that the reviewer's name then travels to the counterparty?

The default engine on cached routes is the README's [maintainer question 7](README.md#open-questions-for-the-maintainer), settled by M4's measurement. The paid line and the Show HN were settled on 22 Oct 2026: the B2B jobs are paid plugins ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)), and the maintainer posts the Show HN that week. The license terms for local job plugins, the price of the jobs, a minimum or full questionnaire beta, and team features are the maintainer's open questions in [08](../../../plans/community-local/seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer).
