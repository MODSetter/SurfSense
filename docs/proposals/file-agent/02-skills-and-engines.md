---
status: proposed
code:
  - document_skills/
  - surfsense_local/backend/modules/agent/opencode_config.py
  - surfsense_local/backend/modules/agent/opencode_runtime.py
  - surfsense_local/backend/modules/agent/opencode_client/client.py
  - surfsense_local/backend/modules/agent/mode_policy.py
  - surfsense_local/backend/modules/agent/prompts/agent.md
  - surfsense_local/backend/modules/agent/prompts/job.md
  - surfsense_local/backend/modules/agent/job_skill.py
  - surfsense_local/backend/modules/agent/skills_manifest.py
  - surfsense_local/backend/modules/agent/config_writes.py
  - surfsense_local/backend/modules/agent/tool_endpoint/
  - surfsense_local/backend/modules/agent/model_endpoint/
  - surfsense_local/backend/modules/agent/harness/
  - surfsense_local/backend/modules/agent/agent_threads/
  - surfsense_local/backend/modules/engine_runs/
  - surfsense_local/backend/modules/workflows/
  - surfsense_local/backend/modules/playbooks/
  - surfsense_local/backend/worker/engines/
  - surfsense_local/backend/worker/workflows/
  - surfsense_local/backend/worker/studio/office/
  - surfsense_local/backend/worker/consumer.py
  - surfsense_local/backend/worker.py
  - surfsense_local/backend/shared/queue.py
  - surfsense_local/backend/shared/config.py
  - surfsense_local/backend/bundling/worker.spec
  - surfsense_local/electron/electron-builder.yml
  - surfsense_local/electron/src/main/sidecars/python.ts
  - surfsense_local/electron/src/main/sidecars/opencode-home.ts
  - surfsense_local/frontend/src/features/agent/step-label.tsx
  - .github/workflows/document-skills.yml
---

# Skills and engines

> SurfSense's document work runs on deterministic engines that the app ships and no model can rewrite: a model writes a plan as data, an engine applies it to a copy of the file, checks the result and reports every operation. Agent-capable models reach the engines through typed SurfSense tools and learn the jobs from shipped SKILL.md files; smaller models get fixed workflows that call the same engines, with a skill the harness picks and a plan held to a JSON schema. The engines are the skills project's own code (`docxkit`, `crlib`, plan schemas, playbooks and graders). They ship in SurfSense after a scoped clean-room fix replaces the parts derived from Anthropic's proprietary skills, behind a no-regression eval gate and a provenance record that CI keeps true.

Facts below were checked on 3 Oct 2026 in this repo (`dev_mod` at `0847e12f7`), in opencode `1.18.32` source under `references/opencode-dev` (two patches behind the pinned `1.18.34`; marked *likely* where that matters), and in the skills project at `references/skills_to_improve` (branch `contract-redline-m1`: code at `f0bb40d`, developer docs at `5780aec`). `references/` is git-ignored, so those paths are named, not linked. Sibling streams: [01 sources and folders](01-sources-and-folders.md), [03 editable artifacts](03-editable-artifacts.md), [04 runtime and packs](04-runtime-and-packs.md), [05 model ladder and evals](05-model-ladder-and-evals.md) and [06 product shape](06-product-shape.md). Milestone numbers (M0 to M10) are the [README](README.md)'s.

## Today

### The agent

- opencode runs with `"skill": "deny"` ("SurfSense ships no skills."), `"external_directory": "deny"`, `"bash": "ask"` and edits allowed only under `*/agent/outputs/*`, on the one agent `surfsense` ([`opencode_config.py`](../../../surfsense_local/backend/modules/agent/opencode_config.py) `PERMISSION`). The config has no `skills` key. The comment on the edit rule says opencode matches the path from a project root of `/` for a folder outside git, so the pattern needs the literal `/agent/outputs/`.
- opencode still scans `skills.paths` under SurfSense's four environment flags; only the permission hides skills, and it works per skill name (`skill/index.ts`, *likely*).
- The scalar `external_directory: deny` blocks skill folders, which opencode would otherwise allow read-only (`agent/agent.ts`, `readonlyExternalDirectory`). It does not block the folder for cut tool outputs: after merging the config, opencode appends `external_directory: {<Truncate.GLOB>: allow}` to every agent unless a deny names exactly that glob, and the last match wins (`agent/agent.ts`, "Ensure Truncate.GLOB is allowed unless explicitly configured").
- A bash rule such as `python "<skills>/*"` is no boundary: `*` matches `/` and `..`, so a script the agent wrote into `outputs/` also passes (`core/src/util/wildcard.ts`). Approved commands inherit `OPENCODE_SERVER_PASSWORD` ([agent](../../architecture/agent.md#known-gaps)), which opencode's server reads from its environment (`server/auth.ts`).
- The wildcard ignores case only on Windows: the pattern is compiled with flags `si` on `win32` and `s` elsewhere (`core/src/util/wildcard.ts`).
- When the agent reads a file, opencode walks from the file's folder up towards the session folder, excluding the session folder itself, and in each folder attaches the first of `AGENTS.md`, `CLAUDE.md` (unless `OPENCODE_DISABLE_CLAUDE_CODE` is set) or `CONTEXT.md` that exists. It appends that file to the read tool's output as a `<system-reminder>` beginning `Instructions from: <path>`, whatever `OPENCODE_DISABLE_PROJECT_CONFIG` says (`session/instruction.ts` `find` and `resolve`, `tool/read.ts`). It also attaches `<XDG_CONFIG_HOME>/opencode/AGENTS.md` to every session (`globalFiles`), and SurfSense sets `XDG_CONFIG_HOME` to its own folder ([`opencode.ts`](../../../surfsense_local/electron/src/main/sidecars/opencode.ts)).
- With `OPENCODE_PURE` set, no plugin loads (`plugin/index.ts`: `flags.pure ? [] : …`). Without it, opencode loads every `{plugin,plugins}/*.{ts,js}` in its config folders (`config/plugin.ts`); agent and command Markdown files are scanned the same way (`config/agent.ts`, `config/command.ts`).
- Every turn names the agent `surfsense` and sends no per-turn `system` ([`client.py`](../../../surfsense_local/backend/modules/agent/opencode_client/client.py) `send_turn`). opencode accepts a per-turn `system` string and a per-session `permission` ruleset (`session/prompt.ts`, `session/session.ts`).
- A per-turn `system` does not survive auto-compaction. After compacting, opencode adds a "continue" user message that carries the agent and model but no `system` (`session/compaction.ts`). The request builder joins the agent's `prompt` with only the last user message's `system` (`session/llm/request.ts` `prepare`, called with `user: lastUser` from `session/prompt.ts`). An agent's `prompt` is in every request.
- SurfSense's config defines the one agent `surfsense`, with `prompt` set to `prompts/agent.md`, which replaces opencode's provider prompt (`opencode_config.py`, `agent_prompt()`). `AgentSetup` holds only the model, its window, the endpoint URL and the launch key.
- `ready_opencode()` writes the config, then waits until `_serves()` sees a running opencode with the same launch key and window; it compares nothing else ([`opencode_runtime.py`](../../../surfsense_local/backend/modules/agent/opencode_runtime.py)). Electron restarts opencode whenever the file changes, ending any turn in progress (`opencode_config.py` docstring).
- The prompt is 3,178 characters under a 4,000 cap (`test_opencode_config.py`, `len(agent["prompt"]) < 4000`; [`prompts/agent.md`](../../../surfsense_local/backend/modules/agent/prompts/agent.md)). Its step 4 tells the model to list sources with `glob`; its "Producing files" sends Word, spreadsheet and PDF requests to Studio; its "Shell commands" section assumes bash.
- Agent citations come only from `surfsense_search_sources` outputs ([`citations.py`](../../../surfsense_local/backend/modules/agent/agent_threads/citations.py) `searched_chunks`).

### The tool endpoint

- Two tools, `search_sources` and `create_artifact`, in a hand-written stateless MCP server ([`offered_tools.py`](../../../surfsense_local/backend/modules/agent/tool_endpoint/offered_tools.py)). `test_it_offers_its_tools_with_flat_schemas` pins the list and its order and forbids `$ref`, `$defs` and `anyOf`.
- Tools register per workspace at `/agent/tools/workspaces/{ws}` ([`registration.py`](../../../surfsense_local/backend/modules/agent/tool_endpoint/registration.py)). A call carries no session, thread or call id.
- `call()` runs each tool inside `transact()`. SQLite's `BEGIN IMMEDIATE` with a 5 s busy timeout means a long tool blocks every other writer.
- `add_tool_server()` sets no `timeout` ([`client.py`](../../../surfsense_local/backend/modules/agent/opencode_client/client.py)). opencode then applies its 30 s `DEFAULT_TIMEOUT` to connecting and to listing tools (`mcp/index.ts` `connectTimeout`, `mcp/catalog.ts` `defs`). A tool call with no configured timeout passes `timeout: undefined` with `resetTimeoutOnProgress`, so the MCP SDK's own 60 s default applies, reset on progress (`mcp/catalog.ts` `convertTool`). SurfSense's own client gives up after 30 s (`_TIMEOUT`). `initialize` declares no `instructions` ([`protocol_version.py`](../../../surfsense_local/backend/modules/agent/tool_endpoint/protocol_version.py)).

### The worker

- `consume()` fails every `PROCESSING` artifact document at start for any queue that is neither ingest nor plugins ([`worker/consumer.py`](../../../surfsense_local/backend/worker/consumer.py), [`interrupted_documents.py`](../../../surfsense_local/backend/worker/interrupted_documents.py)). A new queue added to `_QUEUES` falls into that branch.
- [`worker.py`](../../../surfsense_local/backend/worker.py) imports `worker.consumer` before reading its arguments, so any extra entry point pays for the queue and model imports.
- The plugin runner already builds a child environment from scratch and stops process trees ([`plugin_environment.py`](../../../surfsense_local/backend/modules/plugins/bundles/runner/plugin_environment.py), [`stop_process_tree.py`](../../../surfsense_local/backend/modules/plugins/bundles/runner/stop_process_tree.py)).
- `original_path()` returns a document's original only when its folder holds exactly one file other than what the OS leaves there ([`original_file.py`](../../../surfsense_local/backend/modules/documents/original_file.py)), so nothing derived may be stored beside an original.

### Studio's Office path

- DOCX, PPTX, XLSX and PDF run model-written Python with `exec()` on a worker thread, unsandboxed, without approval, under a `thread.join(120)` that cannot stop it ([`office/runner.py`](../../../surfsense_local/backend/worker/studio/office/runner.py); [studio](../../architecture/studio.md#the-builder-rule-and-where-it-is-broken)). Tests pin that behaviour: `test_render_executes_generated_code_and_keeps_its_bytes` and `test_execute_times_out_a_hanging_script` in `tests/unit/worker/test_studio_office.py`, and four exec tests in `tests/integration/worker/test_studio.py`.
- Each format folder ships a `SKILL.md` named `docx`, `xlsx`, `pptx` or `pdf`, read with `importlib.resources`, never by opencode ([`office/spec.py`](../../../surfsense_local/backend/worker/studio/office/spec.py)). A comparison by 8-word sequences finds none shared with Anthropic's skills.
- `generate.run_model()` already takes `json_schema` and turns thinking off ([`generate.py`](../../../surfsense_local/backend/worker/studio/shared/generate.py)).
- The worker's lock file holds lxml 6.1.3, openpyxl 3.1.5, pypdfium2 5.13.0, jsonschema 4.26.0, psutil, python-docx, python-pptx, xlsxwriter and reportlab, but no pypdf, langgraph or deepagents ([`uv.lock`](../../../surfsense_local/backend/uv.lock)).

### The skills project

- `contract-redline` scores 77.7% on 4 evals against 0% without the skill; `docx` 1.00 against 0.00 on 3, and 0.29 for Anthropic's original. Claude Haiku 4.5 only, one run per cell. `xlsx` is a scaffold; `pdf` and `pptx` have no SKILL.md (`docs/ARCHITECTURE.md` section 1).
- The engine is a library under its CLIs: `docxkit.plan.apply_plan(input_bytes, plan)` resolves every operation before writing, builds in memory and self-checks (`docxkit/plan.py:2320`; `docs/INTEGRATION.md` 5.1).
- **Paragraph ids.** `para.id` is `P:<w14:paraId>` when the paragraph has a unique paraId, else `S:<story key>:<n>` by position; headers, footers, footnotes and endnotes are their own stories. Revisions are `R:<key>:<w:id>` and changes `X:<key>:<n>`; comments are `C:<id>` (`docxkit/doc.py` docstring; `plan_schema.json` `$defs.anchor` pattern `^(P:[0-9A-Fa-f]{8}|S:[^:]+:[0-9]+)$`, revision pattern `^[RX]:[^:]+:.+$`). Files exported by LibreOffice or Google Docs usually carry no paraIds, so every paragraph has a positional `S:` id that shifts after an insert.
- **The plan schema.** `docx-edit-plan/1` has 22 `$defs`; its `op` is an OpenAPI `discriminator` with no `oneOf`, checked by docxkit's own small validator (`plan.py` `validate`, the schema's description). The `jsonschema` library ignores `discriminator`, so it would check only `required: ["op"]`.
- **Every docxkit write is tracked.** Accepting a counterparty's markup without tracking needs `options.allow_untracked_accept` (refusal `UNTRACKED_ACCEPT_NOT_ALLOWED`). Accept and reject are `trackchanges.apply` with a revision selection, not plan operations (`docxkit/cli_accept.py`, `trackchanges.py`).
- **Authors matter downstream.** `compare_documents(sent_pkg, return_pkg, our_authors)` classifies a counterparty's return by which revisions are "ours" (`docxkit/compare.py:744`). It produces a delta report, not a redline file.
- Refusal codes are docxkit's own: `ANCHOR_NOT_FOUND`, `ANCHOR_AMBIGUOUS`, `UNKNOWN_PARA`, `STALE_PLAN`, `REWRITE_SCOPE`, `TOUCHES_HIDDEN`, `SELF_CHECK_FAILED` and others (`docxkit/codes.py`, `plan.py`).
- **Playbooks have a grammar and an import check.** crlib reads playbooks as Markdown in a fixed grammar: a header (`kind`, `side`, `contract_types`, `configured`), then one `## <ID> — <Title>` issue per position with `applies_to` and `importance` bullets and fixed `###` sections (`Standard`, numbered `Fallbacks`, `Walk-away`, `Model language`, `Tell the counterparty`, `Rationale`, `Detect`, `Internal notes`) (`improved_skills/contract-redline/references/playbook-format.md`). `crlib/playbook_md.py` parses it (`parse_file`) and validates it (`validate_files`). A user's playbook in Word, PDF, Excel or text is copied, not rewritten: its text is extracted with locators, normalized to the grammar with a mapping from every field to source quotes, and `playbook.py trace` refuses any field whose numbers, negations or content words are not in its quotes (`references/importing-playbooks.md`, `crlib/cli_playbook_trace.py`). The starter playbooks under `assets/playbooks/` (customer and vendor DPA, reseller, SaaS MSA and SOW; NDA; general; four jurisdiction flag packs) are in English.
- The Word oracle tooling exists: `tools/word/word_oracle.ps1` drives Word, `tools/com/oraclelock.ps1` serialises COM access, and `shared/tests/mutators.py` corrupts fixtures in known ways.

### The licence position

- Anthropic's docx, xlsx, pptx and pdf skills forbid derivative works and redistribution ([docx LICENSE.txt](https://raw.githubusercontent.com/anthropics/skills/main/skills/docx/LICENSE.txt); "source-available, not open source", [anthropics/skills](https://github.com/anthropics/skills)).
- A sha256 comparison of `shared/src` against every file under `original_skills/` finds **45 identical files**: 39 XSDs, `office/soffice.py`, `office/validators/__init__.py`, three `office/helpers/pptx_*.py` and a one-byte `__init__.py` holding a newline. **14 files are modified copies**: `office/validate.py`, `office/validators/{base,docx,pptx,redlining}.py`, `office/helpers/__init__.py`, `comment.py`, `merge_runs.py`, `accept_changes.py` and five `templates/*.xml`. `recalc.py` is a modified copy of the xlsx original.
- **docxkit touches derived material at three points.** `docxkit/check.py` builds its XSD gate `xml.xsd_no_new_errors` on `office.validators.base`; `atoms.py` and `canon.py` import `rendered_text` from `office/helpers/__init__.py`; and `comments_write.py` copies comment parts from `templates/` (`TEMPLATES_DIR`) when a file has none. The maintainer's traced scope names the first two; the third is five XML files totalling about 10.8 KB, mostly namespace declarations.
- **The graders hold a second XSD copy.** `tools/eval/graders/schemas/SOURCE.json` names Anthropic's schema folder as the source and says the files are byte-identical apart from UTF-8 and LF normalisation. It notes that `opc-coreProperties.xsd` imports Dublin Core schemas from dublincore.org, which the graders never fetch.
- Anthropic's originals also sit in `contract-redline-workspace/` and the other `*-workspace/skill-snapshots/` folders.
- **Two kinds of file sit under `improved_skills/*/scripts/`.** Most are synced byte copies of `shared/src`, derived files included, pinned by each folder's `SHARED_LOCK.json` (`source: shared/src`): `office/`, `templates/`, the `docxkit` and `xlsxkit` copies, `comment.py`, `merge_runs.py`, `accept_changes.py`, `recalc.py`, `docx_redline.py`, `xlsx_tool.py` and `env_check.py`. `crlib/`, `review.py` and `playbook.py` exist nowhere else: `improved_skills/contract-redline/scripts/` at `f0bb40d` is their only origin.
- Compared by 10-word sequences, `docxkit/` (about 19,000 lines), `crlib/` (about 12,000), `xlsxkit/` and `tools/eval/` share only namespace URIs and import lines with Anthropic's scripts.

## Decisions

1. **Engines and skills live in a new top-level tree, `document_skills/`, beside `plugins/`.** The provenance gate needs one bounded tree; the worker, the eval matrix and plugin packs all import it; its tests need no backend. The backend already takes `plugins/bundles/core/manifest` as a path dependency ([`pyproject.toml`](../../../surfsense_local/backend/pyproject.toml)).
2. **The improved skills ship after a scoped clean-room fix (maintainer decision, 3 Oct 2026).** `docxkit`, `crlib`, the plan schemas, playbooks and graders carry over. The 39 schemas are re-sourced from their publishers; the derived validator, helpers and comment templates are rewritten clean-room; unused pptx and LibreOffice parts are dropped; the docx-js "Gotchas" text is rewritten from docx-js's own docs. A no-regression eval gate, a Word-oracle test of the new validator, a similarity scan and a provenance file decide when it is done, and a short legal review comes before selling to legal and security buyers (section 2). *Reason:* the licence forbids derivatives, but the value is the maintainer's own engines: the improved docx skill scores 1.00 where Anthropic's original scores 0.29.
3. **Engines are a library: bytes in, a report out.** No CLI, `sys.exit` or stdout rewiring; those served `python script.py`, which SurfSense never runs.
4. **The agent reaches engines through engine tools that take ids, never paths.** `inspect_document` and `edit_document` come first; `compare_documents` and `export_document` follow once the first two are measured. Formats add arguments, not tools. Every write is a new artifact version with a per-operation report.
5. **Agent and selection edits are all-or-nothing; workflow edits may apply in part.** A failed operation in an agent edit saves nothing and fails the version; a workflow passes `partial=True` and its version is ready with the skipped operations listed. An agent can resend; a workflow has no one to resend.
6. **A version whose plan is complete when it starts runs as `engine_job` on an `engines` queue; reads create no version.** Each engine operation runs in a killable child process, never inside `transact()` and never on a worker thread. Reads are cached by content hash. A thread cannot be stopped; a process can. A read that made a version would fill the append-only list and block edits with 03's one-in-flight rule.
7. **Engine edits are always tracked, and the model cannot turn tracking off.** docxkit writes only tracked changes; the tool has no `tracked` argument and the server never sets `allow_untracked_accept`. A prompt-injected document must not be able to ask for a silent change.
8. **Revisions and comments carry a user-set author, never a model's name.** A redline goes to a counterparty with its author on every change, and `compare_documents` tells ours from theirs by that name.
9. **SKILL.md files follow the open Agent Skills format, name SurfSense tools and hold no scripts.** They load read-only through `skills.paths`, allowed by name per model. The skills project's texts teach CLI commands SurfSense never runs, so every SKILL.md is rewritten as a procedure in the tools' words.
10. **Skill names start with `surfsense-`.** opencode keeps the last of two same-named skills, and `docx`, `xlsx`, `pdf` and `pptx` are Anthropic's.
11. **A job thread runs its job's own predefined agent, whose prompt carries exactly one skill, and denies the skill tool and bash; a free agent thread lists at most three skills.** The skill lives in the agent's `prompt`, not in a per-turn `system`, so compaction cannot drop it (Today). SkillsBench measured +18.0 pp for one skill, +19.0 pp for two or three and +10.1 pp for four or more, and found comprehensive-length skills gain +0.7 pp ([SkillsBench](https://arxiv.org/abs/2602.12670); research E3, E4). Gemma-3-4B picks the right skill 84.5% of the time against 99.5% for Qwen3-30B ([arXiv 2602.16653](https://arxiv.org/abs/2602.16653)).
12. **Below agent capability, fixed workflows run plan, engine, verify, repair, with each plan held to a JSON schema.** The harness picks the workflow; one workflow is one job. A workflow is [05](05-model-ladder-and-evals.md)'s `workflow` rung, the lowest of its three (`agent`, `job_thread`, `workflow`).
13. **Studio's Office formats move from `exec()` to spec builders, back under [ADR 0010](../../adr/0010-studio-builders-not-sandboxes.md), and never leave a free user worse off.** Before `runner.py` is deleted, the `exec()` path is measured on the default 4B with the same cases as the builders. A builder replaces `exec()` for a format on any model where it scores at least that baseline. Where it does not, that format keeps the `exec()` path on local models until the builder catches up, which is today's behaviour. The prompt tier is not a capability signal, so no tier keeps `exec()`. After [07](07-create-and-edit-mvp.md#after-the-slice)'s slice, every Office format takes two paths: models that count as strong keep writing a document script, which runs in SurfSense's script runner ([ADR 0039](../../adr/0039-document-scripts-run-without-approval.md)), and small models move to a builder (Markdown for Word and PDF, a flat spec for PowerPoint and Excel) once it scores at least the script path's baseline on that model; until then the format keeps its script, run on the runner. Which models count as strong comes from [05](05-model-ladder-and-evals.md#4-the-capability-profile)'s measured capability; no reliable signal for it exists yet.
14. **One new ADR, [ADR 0040](README.md#adrs-to-write-or-amend), shared with [03](03-editable-artifacts.md):** "Edits run shipped engines on model-written plans, make append-only versions, and never write the user's file." Edits need no approval, because engines run neither model-written code nor the shell. ADR 0028's decision stands; its text changes as listed under [What this changes](#what-this-changes-in-existing-adrs-and-proposals).
15. **Stay on opencode 1.18.x; build a harness adapter or a Goose spike only on a named result from [05](05-model-ladder-and-evals.md)'s matrix.** The 2.x server API is labelled experimental ([openapi.json](https://opencode.ai/v2/openapi.json)) and its ACP is not ported ([#35457](https://github.com/anomalyco/opencode/issues/35457)).
16. **The model endpoint simplifies tool schemas, recovers text-written tool calls for local models, and strips instruction reminders from the working folder.** The first two are listed gaps that stall small models; the third is the only in-turn block on persisted instructions that does not depend on letter case.
17. **Format skills, engines and all job content ship free in the app under Apache-2.0.** Job skills, playbooks, questionnaire mappings, RFP templates and eval cases are open source and ship in the installer. The security-questionnaire job arrives that way in M7, with no pack. Phase 8 lets the plugin installer add job packs as an open-source extension mechanism, never paywalled. What the license sells is premium plugins, priority support and Enterprise controls ([README](README.md), ADR 0047); no job content is among them.
18. **A job is offered on a model once that model's eval row passes the job gate, and no verdict is ever used to hold a job for another reason.** A capability verdict reflects eval rows only, so "Not on this model" never stands for a pending legal review. Until a lawyer reviews the starter playbooks, each carries "Starter playbook — not reviewed by a lawyer; not legal advice" on the job card, in the issues list and in the exported issues file; a user's own playbook carries no such label. Public job pages, SEO pages and legal marketing wait for that review.
19. **A user's own playbook enters as crlib's structured format, validated before every job and reviewed by the user.** "Make a playbook from this document" drafts the structure from the firm's positions document, and the user corrects it in a form ([06](06-product-shape.md)). *Reason:* the redline workflow's schema enumerates playbook rule ids and checks "never" rows, so a playbook that is only a folder of documents cannot drive it.
20. **Engines report a code and its values for every operation and every line the user must see; the interface renders them through the ICU catalogs.** English is the fallback and the text the model reads. The interface ships ten catalogs ([`translations/`](../../../surfsense_local/frontend/translations/); [ADR 0029](../../adr/0029-icu-translation-catalogs.md), [0030](../../adr/0030-formatjs-renders-interface-text.md)).
21. **Internal comments never leave by default.** A docx revised copy downloads as its `external` file, with internal comments removed and a leak scan in the report; the copy with internal comments is an explicit second choice.

## Design

### 1. The tree

```text
document_skills/
  README.md               the tree, its checks, and how provenance works
  provenance.json         one row per file
  engines/                distribution surfsense-document-engines, import surfsense_engines
    src/surfsense_engines/
      package/            OPC zip I/O and copy safety (from office/opc.py, safexml.py), xml_text.py
      docx/               inspect, plan, apply, check, xsd_check, compare, changes, comments, external
      xlsx/               inspect, fill, check (new)
      pdf/                pages (new)
      contract/           crlib, review.py and playbook.py: the playbook grammar, validation, trace, review checks
      flat_ops.py         the tools' flat operations, turned into each engine's plan
      report.py           apply-report/1
      messages.py         the English template for every code
      schemas/            re-sourced XSDs with SOURCE.json
    specs/                the clean-room behaviour specs (section 2)
    tests/
  skills/                 shipped as resources/skills, with MANIFEST.json
  graders/                graders, fixtures, truth; never import engines
  gate/                   no-regression results, Word-oracle results, scan report
  checks/                 check_provenance.py, lint_skills.py, refused_hashes.txt, refused_shingles.txt
```

- `AGENTS.md` gains a sixth tree, its commands and its test line.
- The backend adds `surfsense-document-engines = { path = "../../document_skills/engines", editable = true }`. `bundling/worker.spec` collects `surfsense_engines` with its XSDs. The API spec does not: the API never imports engines. What the API shows of an engine's work (revision lists, outlines, reports) is computed in the worker and stored on the version or in its folder (section 4).
- Graders read the XSDs from the engines' `schemas/` folder by path, as data; they import no engine code, so a grader can never pass because the engine under test agrees with itself.
- `electron-builder.yml` copies `document_skills/skills` to `skills`. `python.ts` `pythonEnv()` passes `SURFSENSE_LOCAL_SKILLS_DIR`, and `AgentSettings` in [`shared/config.py`](../../../surfsense_local/backend/shared/config.py) gains `skills_dir`.
- The package is `surfsense_engines`, not the skills project's generic `office`.

### 2. The clean-room fix

SurfSense ships the improved skills once the parts derived from Anthropic's skills are replaced. This is M1 work, beside 05's eval harness: no engine is vendored into SurfSense before it is done. It is not part of M0's point release, which ships without it.

**Scope.** Line counts are `wc -l` at `f0bb40d`.

| # | Files | Lines | Fix | Becomes |
|---|---|---|---|---|
| 1 | `office/schemas/` (39 XSDs) and `tools/eval/graders/schemas/` (the second copy) | data | Re-source from the publishers (ECMA-376 Parts 1, 2 and 4, ISO/IEC 29500-3 for markup compatibility, Microsoft's open specifications for the `w14`/`w15`/`w16*` extensions), keep each publisher's notice, record URL and sha256 per file | `engines/src/surfsense_engines/schemas/`, one copy |
| 2 | `office/validators/base.py` (922), `docx.py` (670), `redlining.py` (125), `office/validate.py` (232), `validators/__init__.py` | ≈1,950 | Clean-room rewrite on lxml from ECMA-376, including markup-compatibility handling (`mc:Ignorable`, `mc:ProcessContent`, `mc:AlternateContent`) | `docx/xsd_check.py`: validate each part and report only errors the input lacked, which is what `xml.xsd_no_new_errors` needs |
| 3 | `comment.py` (205), `merge_runs.py` (213), `accept_changes.py` (92), `recalc.py` (50); the derived parts of `office/helpers/__init__.py` (121) | ≈560 + helpers | Drop the four scripts: docxkit already writes comments (`comments_write.py`), accepts and rejects (`trackchanges.py`) and works on atoms, so nothing needs merged runs; recalculation is [04](04-runtime-and-packs.md)'s `recalc_after()` under its decision 17. Rewrite `rendered_text` and any other derived helper from ECMA-376 Part 1's `xml:space` rules | `package/xml_text.py` |
| 4 | `office/helpers/pptx_chart.py` (170), `pptx_slide.py` (60), `pptx_theme.py` (114), `office/validators/pptx.py` (428); `office/soffice.py` (192) | ≈770 + 192 | Drop. pptx is not built; `soffice.py` is unused and unsafe on Windows, and the hardened LibreOffice runner is [04](04-runtime-and-packs.md)'s | nothing |
| 5 | The docx-js "Gotchas" list in `improved_skills/docx/SKILL.md` | text | Rewrite from docx-js's own documentation in the skills project. SurfSense ships none of it: Word creation runs on the python-docx builder (section 7) | nothing in SurfSense |
| 6 | `templates/comments.xml`, `commentsExtended.xml`, `commentsExtensible.xml`, `commentsIds.xml`, `people.xml` | ≈10.8 KB | Generate the empty parts in code from ECMA-376's and Microsoft's part definitions (found here; not in the traced scope) | `docx/comment_parts.py` |

**What carries over, what goes, what never moves.**

| Skills project path | Verdict |
|---|---|
| `docxkit/*` minus its `cli_*.py`, with the three touch points rewired to items 2, 3 and 6 | carry over as `docx/` |
| `docxkit/plan_schema.json`, `contract-review/1` | carry over as internal plan schemas |
| `office/opc.py`, `safexml.py`, `codes_common.py`, `untrusted_patterns.py`, `xlsx_io.py`, `fonts.py`, `png.py` | carry over into `package/` and the kits using them |
| `xlsxkit/codes.py`, the xlsx `SPEC.md` decisions | carry over as the start of `xlsx/` |
| `improved_skills/contract-redline/scripts/{crlib/,review.py,playbook.py}@f0bb40d`, their only origin, and `improved_skills/contract-redline/assets/playbooks/` | carry over file by file; the starter playbooks carry the starter label until a lawyer reviews them (decision 18) |
| `shared/tests/` (including `mutators.py`), `tools/eval/graders/*.py`, fixtures, truth, calibration | carry over after a fixture licence check, into `engines/tests/` and `graders/` |
| `_bootstrap.py`, `pack.py`, `unpack.py`, `env_check.py`, `sync_shared.py`, `docx_redline.py`, `xlsx_tool.py`, every `cli_*.py` | drop: no CLI, no hand-edited XML, one package instead of byte copies |
| every SKILL.md and reference text | rewritten for SurfSense's tools (section 5) |
| `original_skills/`, every `*-workspace/skill-snapshots/`, the synced copies of `shared/src` under `improved_skills/*/scripts/` (`office/`, `templates/`, the `docxkit` and `xlsxkit` copies, `comment.py`, `merge_runs.py`, `accept_changes.py`, `recalc.py`, `docx_redline.py`, `xlsx_tool.py`, `env_check.py`), `.skill` zips, the project's git history | never vendored; `docxkit` and the kept `office/` modules come from `shared/src` |

**Process.**

1. **A spec author** reads only ECMA-376, Microsoft's published extension specifications, lxml's documentation and the skills project's own `SPEC.md` files. They write `engines/specs/xsd_check.md`, `xml_text.md` and `comment_parts.md`: inputs, outputs, refusal codes, markup-compatibility rules and the "report only new errors" contract.
2. **A separate implementer**, who has never opened the originals, works in a SurfSense checkout, which never contains them, from those specs and the maintainer's existing tests for the replaced modules (`test_wp1_validate.py`, `test_wp5_check.py` and the others that exercise the gate). A test that encodes an original's quirk rather than ECMA's rule goes back to the spec author, who rewrites it and records why. When agents do the work, the two roles are two sessions, and the implementer's working folder holds neither `original_skills/` nor the skills repository.
3. **Carried-over files** are copied by the maintainer file by file. Each keeps a header naming its origin path and `f0bb40d` and gets a provenance row.
4. **The pull request** names the spec author, the implementer and what each consulted. A reviewer who has not read the originals signs off.

**The no-regression gate.** The clean tree replaces the skills project's tree only when all four hold, and the gate re-runs on every change to `docx/`, `package/` or `graders/`. Results are committed to `document_skills/gate/` with run ids and the sha256 of the code they ran on.

1. **Same evals, same truth.** docx D01, D03 and D05 stay at 1.00. contract-redline E01, E02, E07 and E11 match or beat iteration 3's 77.7%, run 3 times per eval instead of once. The maintainer runs them with the skills project's harness (`tools/eval`, `opencode_run.py`) on a build with the clean modules swapped in; [05](05-model-ladder-and-evals.md)'s matrix repeats them inside SurfSense later. Haiku 4.5, the executor behind the 77.7%, retires "not sooner than" 2026-10-15 (research E4), so iteration 3's baseline is re-run at n=3 on Haiku 4.5 and on Sonnet 5.5 at low effort before that date, and the gate keeps a baseline either way.
2. **The validator against Word, not against Anthropic's code.** For each fixture and each mutation in `shared/tests/mutators.py`, `tools/word/word_oracle.ps1` (serialised by `tools/com/oraclelock.ps1`) records whether Word opens the file without a repair prompt. `xsd_check` must flag every file Word repairs or refuses and pass every file Word opens cleanly. Each disagreement where the schema and Word legitimately differ is listed with its reason. This needs Windows and Word, so it runs on the maintainer's machine; CI checks that the committed results name the current sha256 of `xsd_check.py`.
3. **A similarity scan** of every file that ships, against `original_skills/`, the `skill-snapshots/` folders and the 45 identical and 14 modified files listed in [Today](#the-licence-position), and nothing else, so carried-over code is never scanned against its own synced copies: byte hashes and 10-word shingles, excluding namespace URIs, import lines, files under 64 bytes and the XSDs (which rule 1 of the licence gate covers). The expected result for `docxkit` and `crlib` is near zero; every hit is rewritten or explained in its provenance row. The report is committed as `gate/similarity.md`.
4. **A complete provenance file**, as the licence gate below checks.

**Legal review.** `docxkit` and `crlib` look like new code but were written by someone who had read the originals. Before SurfSense is sold to legal and security buyers, a lawyer reviews `provenance.json`, the similarity report, the process record and each schema publisher's terms. It does not hold back the free app. A file the review finds too close joins the rewrite list; a schema whose terms do not allow redistribution leaves the set, and `xsd_check` skips that part, as the graders already skip core properties.

**The provenance record.** `document_skills/provenance.json` holds, per file, `path`, `origin` (`new`, `clean-room:<spec path>`, `carried-over:<path>@f0bb40d`, `re-sourced:<url>` or `third-party:<SPDX id>`), `author`, `spec_author` for clean-room files, `reviewer`, `notice` for re-sourced files, and `sha256` for data and re-sourced files.

**The licence gate**, `checks/check_provenance.py` in `.github/workflows/document-skills.yml`, fails a pull request when:

1. a file in the tree has no provenance row, a data file's sha256 differs from its row, or a re-sourced file's sha256 differs from its row. A weekly job downloads each `re-sourced:<url>` and checks that the publisher still serves those bytes.
2. a file of 64 bytes or more that is not a schema has its sha256 in `checks/refused_hashes.txt`, the hashes of every identical or modified Anthropic file listed in [Today](#the-licence-position), generated once by the maintainer (hashes are not copies);
3. such a file shares more than 20 ten-word sequences with `checks/refused_shingles.txt`, hashed shingles of the same files with namespace URIs and import lines excluded, which catches a paste a byte hash misses;
4. [04](04-runtime-and-packs.md)'s `scripts/licenses/check_python.py`, called with its shared policy, fails on the frozen worker's resolved packages.

### 3. The engine library

```python
@dataclass(frozen=True)
class Notice:
    code: str                       # a key in messages.py and in the ICU catalogs
    values: dict[str, str | int]    # what the message fills in


@dataclass(frozen=True)
class OpOutcome:
    index: int
    op: str
    target: str        # the id as the tool received it
    status: Literal["applied", "failed", "skipped"]
    code: str | None   # docxkit's codes, plus STALE_ANCHOR and BATCH_REFUSED
    values: dict[str, str | int]
    message: str       # the English text of code and values: one sentence the model can act on


@dataclass(frozen=True)
class EngineResult:
    output: bytes | None          # None when nothing was saved
    outcomes: list[OpOutcome]
    checks: list[Check]           # id, ok, code, values
    must_tell_user: list[Notice]  # shown by the UI whatever the model says
    input_sha256: str
```

- `report.py` `as_report(result) -> dict` writes `apply-report/1`, the one report shape: `schema`, `saved`, `ops` (`index`, `op`, `target`, `status`, `code`, `values`, `message`), `applied`, `failed`, `skipped`, `checks`, `must_tell_user` (`code`, `values`), `input_sha256`, `output_sha256`. [03](03-editable-artifacts.md)'s `apply_report.from_engine` stores it as given.
- `messages.py` holds one English template per code. The model reads the English `message`; the interface renders `code` and `values` through the ICU catalogs under `engine.<code>`, falling back to English (decision 20). A lint test fails when an engine code has no English template or no key in the English catalog.
- `docx.inspect(data, view, start, count)`: `P:<paraId> | style | text` lines with `~hidden`, `~comment` and `~change` marks (docxkit `outline.build_outline`). A paragraph without a unique paraId, and every header, footer, footnote and endnote paragraph, prints as `S:<story>:<n>@<h>`, where `<h>` is the first 8 hex digits of the input's sha256; revisions and changes print as `R:…@<h>` and `X:…@<h>`. `P:` and comment ids carry no tag.
- `docx.apply(data, ops, *, author, partial=False)`: `flat_ops.to_docx_plan()` builds `docx-edit-plan/1` with `source.sha256` set to the input's hash and `author` from the caller; docxkit's own `plan.validate` checks it (never `jsonschema`, which ignores the discriminator); `apply_plan` runs it. Any tagged id whose `<h>` is not the input's gets `STALE_ANCHOR` before the engine runs: "S:footnotes:3 came from another version; inspect version 5 again." All-or-nothing unless `partial=True`: on a refusal the other operations are `skipped` with `BATCH_REFUSED` and `saved` is false.
- `docx.compare(sent, returned, our_authors)`, `docx.external` (internal comments removed, leak scan) and `docx.changes` (revision rows for an issues sheet and for 03's revision list).
- `xlsx.inspect` and `xlsx.fill(data, cells)`: values go into the sheet XML through the OPC layer, never through openpyxl's save, which loses shapes ([openpyxl docs](https://openpyxl.readthedocs.io/en/stable/)). A formula cell is refused unless the op says `replace_formula`. The child sets `fullCalcOnLoad="1"` and clears the cached `<v>` of every formula whose inputs changed, or of every formula when that set is unknown. Delivered values follow [04](04-runtime-and-packs.md) decision 17: when Office support (04's LibreOffice download) is installed, 04's `recalc_after()` writes LibreOffice's values into those cleared cells only; IronCalc values never reach a file and, if IronCalc is adopted after 04's open question 7, feed only the diff and the report ("expected 42 in B7"); without LibreOffice the cells stay cleared and the report names them.
- `pdf.pages(data, start, count)`: per page, a `--- page 12 ---` header and its text from pypdfium2. Form filling waits for pypdf.
- **Schemas load without a network.** `docx/xsd_check.py` parses every XSD with `XMLParser(no_network=True)` and a resolver that serves only files under `schemas/` and refuses anything else; `opc-coreProperties.xsd`'s Dublin Core imports are not bundled, so core properties are not schema-checked, as in the graders.

### 4. The tool surface

**One order for every tool, owned here.** `offered_tools.TOOL_ORDER` is: `search_sources`, `create_artifact`, `inspect_document`, `edit_document`, `revise_artifact`, `compare_documents`, `export_document`. [01](01-sources-and-folders.md) changes the first two's arguments; [03](03-editable-artifacts.md) adds `revise_artifact`. A tool not yet built is left out without reordering the rest. What a thread lists depends on its kind, through the per-thread registration URL that [01](01-sources-and-folders.md) introduces:

| Thread | Tools listed |
|---|---|
| Free agent | all seven |
| Job thread | `search_sources`, `inspect_document`, `edit_document`, plus `compare_documents` and `export_document` when the job names them |

Within one thread the list never changes, so the prompt cache holds for the thread.

| Tool | Arguments, all flat | Returns |
|---|---|---|
| `inspect_document` | `source_id`, or `artifact_id` + `version`; `view` (`outline`, `changes`, `comments`, `cells`, `pages`, `check`, `report`, `playbook`); `start`, `count` | a page under 20,000 characters, ending with the next `start` |
| `edit_document` | `source_id`, or `artifact_id` + `version`; `ops`; `title` | the new version and its report |
| `compare_documents` (phase 1b) | `sent_*` and `returned_*` ids and versions | the delta as an issues list |
| `export_document` (phase 1b) | `artifact_id`, `version`, `kind` (`external`, `issues`) | a derived artifact for sending |

The clean copy of a redline is not an export: it is [03](03-editable-artifacts.md)'s `clean` file role on the same version. The same holds for the copy a counterparty receives: every committed docx revised-copy version also gets an `external` file from `docx.external` in the same job, with the leak scan in its report, and 03's Download offers it first. "With changes (internal)" is the explicit second choice (decision 21). Until phase 1b ships that file, `edit_document` refuses `audience: internal`.

The edit schema is one array of flat objects:

```json
{
  "type": "object",
  "properties": {
    "source_id": {"type": "integer"},
    "artifact_id": {"type": "integer"},
    "version": {"type": "integer"},
    "ops": {"type": "array", "items": {"type": "object", "properties": {
      "op": {"type": "string", "enum": ["replace", "insert", "delete", "rewrite", "add_paragraphs", "delete_paragraphs", "comment", "reply", "no_reply", "respond", "set_cell"]},
      "at": {"type": "string", "description": "An id exactly as inspect_document printed it: P:1A2B3C4D, S:footnotes:3@9f2c11ab, R:document:14@9f2c11ab, X:header1:2@9f2c11ab, C:5, or Sheet1!B4."},
      "through": {"type": "string", "description": "The last paragraph of a range."},
      "find": {"type": "string"},
      "occurrence": {"type": "integer"},
      "position": {"type": "string", "enum": ["before", "after", "start", "end"]},
      "text": {"type": "string"},
      "scope": {"type": "array", "items": {"type": "string"}},
      "comment": {"type": "string"},
      "audience": {"type": "string", "enum": ["external", "internal"]},
      "decision": {"type": "string", "enum": ["accept", "reject", "counter", "hold"]},
      "reason": {"type": "string"},
      "replace_formula": {"type": "boolean"}
    }, "required": ["op", "at"]}},
    "title": {"type": "string"}
  },
  "required": ["ops"]
}
```

"`source_id` or `artifact_id`" and per-op rules are checked in code, because `oneOf` and `anyOf` break small models' grammars. An edit of a source makes a new artifact, a revised copy through 03's `start_revised_copy`; an edit of an artifact makes its next version, and only from the head ("version 4 is not the latest, 5 is; inspect 5").

**How flat operations map** (`flat_ops.to_docx_plan()`; each op gets `id` `op<index>`, and `comment` plus `audience` become docxkit's `comment_spec` on any change op):

| Flat op | docxkit op | Mapping |
|---|---|---|
| `replace` | `replace` | `at`→`para`, `find`, `text`→`with`, `occurrence` |
| `insert` | `insert_text` | `at`→`para`; `position` before/after with `find` and `occurrence`→`at.before`/`at.after`, or start/end→`at.start`/`at.end`; `text` |
| `delete` | `delete_text` | `at`→`para`, `find`, `occurrence` |
| `rewrite` | `rewrite` | `at`→`para`, `text`, `scope` |
| `add_paragraphs` | `insert_paragraphs` | `at`→`after` (or `before` when `position` is before); `text` split on newlines into `paragraphs`, each `like` the anchor |
| `delete_paragraphs` | `delete_paragraphs` | `at`→`from`, `through` (default `at`)→`to` |
| `comment` | `comment` | `at` P:/S:→`anchor.para` with `find`, `occurrence`; with `through`→`anchor.from`/`to`; R:/X:→`anchor.revision`; `text`; `audience` |
| `reply` | `reply` | `at` (C:)→`to`, `text`, `audience` |
| `no_reply` | `no_reply` | `at` (C:)→`to`, `reason` |
| `respond` | `respond` | `at` (R:/X:)→`revision`, `decision`, `text`; `mode` is always `leave` |
| `set_cell` | `xlsx.fill` | `at` (Sheet!A1), `text` as the value, `replace_formula` |

Accepting or rejecting tracked changes outright is not an agent operation: it is [03](03-editable-artifacts.md)'s `revisions/decide` route, a `review` version that runs docxkit's `trackchanges.apply` on the selected revisions.

**The report fails loudly:**

```text
Nothing was saved: operation #3 failed; the other 7 were valid.
#3 replace at P:1A2B3C4D failed (ANCHOR_NOT_FOUND): "Net 30" is not in that paragraph, which reads "Payment is due within thirty days".
Correct #3 and send all 8 again against version 4.
```

The full report is stored on the version for the UI ([03](03-editable-artifacts.md)), because models drop what an engine told them (I3, lesson 19).

**How an edit runs.**

1. `tool.py` gains `JobTool(listing, start, wait)`. `offered_tools.call()` runs `start` inside `transact()` and `wait` outside it.
2. `modules/engine_runs/start.py` `start_engine_run(session, workspace_id, thread_id, arguments) -> int` checks arguments, resolves the input and calls 03's `start_version(kind=edit, origin=agent, base_number=…, plan=ops, chat_thread_id=thread_id, queue="engines")`, or `start_revised_copy(..., plan=ops, queue="engines")` for a source. `thread_id` comes from the per-thread registration URL ([01](01-sources-and-folders.md)); 03's `attach_steps`, matching the tool part after the turn, fills only `step_ref`. Every `source_id` passes 01's `require_in_scope` first. The ops are stored in the version's `plan` file role, never `spec`, so a revised copy never looks Refine-able.
3. A source's original reaches the engine only through [01](01-sources-and-folders.md): `start_engine_run` calls `resolve_original` in its short transaction, and `engine_job` calls `copy_original` with no session open, into the job's scratch folder. `copy_original` refuses when the file changed on disk since it was read; the version then fails with that message, 01 sets the root's `reconcile_requested_at`, and the report says: "contract.docx changed on disk; SurfSense is re-reading it. Try again when it is ready."
4. `modules/engine_runs/wait.py` `wait_for_engine_run(version_id, deadline)` polls the version every 0.5 s in short sessions for at most 25 s, inside both the MCP SDK's 60 s call limit and SurfSense's own 30 s client. If the run is still going it answers: "Version 5 is still being made; call surfsense_inspect_document with view report on artifact 12 version 5." `add_tool_server()` keeps the default timeout.
5. When a turn is aborted, `agent_threads/turn.py` calls `engine_runs.cancel_for_thread(thread_id)`, which cancels that thread's pending and running engine versions, so the head never moves after the user stopped.
6. Progress shows as the step's running state and through `notify_artifact_updates`. MCP progress notifications need a streamed reply that the endpoint refuses by test (`test_no_event_stream_is_offered`).

**How a read runs.** `inspect_document` creates no version and holds no slot.

1. It resolves the input's sha256 without copying: a source's `content_hash` ([01](01-sources-and-folders.md)) or a version file's sha256 ([03](03-editable-artifacts.md)).
2. If the view is cached, the API pages it from disk; the API reads text files, never engine code. Views of an artifact version live in its folder as `artifacts/<id>/v<n>/views/<view>.txt`, written by the job that makes the version and deleted with its files. Views of a source live in `<data>/engine_cache/<sha256>/<view>.txt`, evicted least-recently-used above 500 MB (an estimate) and when no document has that hash any more.
3. On a miss it enqueues `engine_read(sha256, view, input_ref)` on the engines queue and waits up to 25 s for the file. The engines worker runs the read in a child once per (sha256, view), not once per page, and writes the view atomically.

**Where the work happens.**

- `shared/queue.py` gains `engines_queue`; `worker/consumer.py` `_QUEUES` gains `"engines": (engines_queue, 2)`, supervised by Electron as a fourth worker sidecar. On the Studio queue an edit would wait behind four Studio jobs sharing one model slot.
- `consume()` gains an explicit `engines` branch that calls `worker/engines/interrupted_runs.py::fail_interrupted_engine_runs()`, which fails only versions whose `queue` is `engines` (and the document of a revised copy whose v1 was one). The Studio branch's sweep skips documents whose in-flight version is an engines version; [03](03-editable-artifacts.md)'s `fail_interrupted_versions(queue)` takes the queue. The engines consumer imports only `modules.engine_runs.tasks`, not `import_tasks()`, so it does not idle at the Studio consumer's 541 MB ([04](04-runtime-and-packs.md)).
- **The engines worker never loads the embedding encoder.** Chunks and vectors for an engine or agent version's body are computed by the Studio worker, never the engines worker: [03](03-editable-artifacts.md)'s `index_version` takes an engine version over once its run succeeds, and 03's `version_job` indexes an agent version. The [README](README.md)'s whole-stack memory budget measures this worker's idle and busy private bytes on the 16 GB reference laptop at the M5 and M6 exits.
- Which job runs a version is its `queue`, set by `start_version` and changed only when a finished engine run is handed over to be indexed: `engines` when the plan is complete at start (an agent edit, a revised copy with a plan, a `review` from `decide`); `studio` when a model must write content first (Refine, a selection edit, chat Edit, a workflow). `_run_version` never runs an `engines` version and `engine_job` never runs a `studio` one. A Studio version that needs an engine (a selection edit's `rewrite` on a file-backed docx, a workflow's apply step) calls `worker/engines/run.py::run_in_child()` from its own job.
- `modules/engine_runs/tasks.py` `engine_job(version_id)` uses [03](03-editable-artifacts.md)'s `worker/jobs.py::begin_version` and `finish_version` as its guards. It calls `worker/engines/run.py` `run(version_id)`: copy the input to a temporary folder, start `worker --engine-op <request.json>` (the frozen worker re-executing itself, as `main.py` does for `--probe-devices`), wait at most 180 s, and stop the tree on timeout or cancel with `stop_process_tree`. For an xlsx edit it then runs [04](04-runtime-and-packs.md)'s `recalc_after(version_id, deadline)` outside those 180 s, with its own 150 s budget. When the run succeeds, one short transaction records the version's files, report, plan, `views/outline.txt` and the revision rows from `docx.changes` in the version's `changes`, sets `queue` to `studio` and the status back to `pending`, and enqueues 03's `index_version`, which chunks, embeds and calls `commit_version` in the Studio worker. 03's `revisions` and `compare` routes and its text-quote resolver therefore read stored data.
- `worker.py` dispatches `--engine-op` before importing `worker.consumer`; `worker/engines/engine_op.py` runs one operation and exits. Its environment is built from scratch like `plugin_environment()`: no `SURFSENSE_LOCAL_SECRET`, proxies at a dead loopback port. The original's sha256 is compared before and after.
- **The author.** `workspaces.settings.revision_author`, in the JSON column [06](06-product-shape.md)'s `WorkspaceSettings` defines and adds by plain `ADD COLUMN` (phase 1 adds the column if 06 has not), is passed as `author` to every engine write and as `our_authors` to compare. It defaults to "SurfSense", and the first revised copy in a workspace asks for a name or organisation. The model never sets it.
- `step-label.tsx` gains a label per tool ("Edited contract.docx: 8 changes").

### 5. Skills

| Skill | Kind | Ships in | Needs | Document languages |
|---|---|---|---|---|
| `surfsense-word-edit` | format | phase 3 (M6) | docx engine | any the engine reads |
| `surfsense-contract-redline` | job | phase 3 (M6) | docx engine, a valid playbook | English: the starter playbooks and their `Detect` words are English |
| `surfsense-sheet-fill` | format | phase 5a (M7) | xlsx engine | any |
| `surfsense-security-questionnaire` | job | phase 5a (M7) | xlsx, pdf, docx forms | English first |
| `surfsense-rfp-response` | job | later | xlsx, pdf, docx forms | English first |

PDF reading needs no skill; `inspect_document` with `view: pages` and one line of tool guidance cover it.

**When a job is offered** (decision 18). A job is offered on a model once that model's eval row passes the job gate; 05 holds the gate and its unmeasured default, and 06 shows the verdict. The playbooks' lawyer review never changes a verdict: until it is done, every starter playbook carries "Starter playbook — not reviewed by a lawyer; not legal advice", which the job card, the issues list and the exported issues file (`export_document`, kind `issues`) all print. The label is keyed to the playbook's origin, so a user's own playbook never gets it. Public job pages, SEO pages and legal marketing wait for the review.

**Languages.** Each job skill states its supported document languages in its frontmatter (`metadata.surfsense-languages`, such as `en`), and the job card shows them. [05](05-model-ladder-and-evals.md) adds at least one non-English case per job family; a language joins the list when its cases pass.

Frontmatter is the spec's: `name` equal to the folder, `description`, `license: Apache-2.0`, string-to-string `metadata` such as `surfsense-workflow: contract-redline` ([spec](https://agentskills.io/specification)). The body is a procedure in the tools' words:

```markdown
---
name: surfsense-word-edit
description: Edit the user's Word files with tracked changes and comments. Use when asked to revise, redline, comment on or clean up a .docx.
license: Apache-2.0
---
1. Read the file with surfsense_inspect_document, view outline. Never open a .docx with read.
2. Write every change as one surfsense_edit_document call, copying ids exactly as printed, tags included.
3. If nothing was saved, fix only the failed operations and send them all again.
```

`improved_skills/contract-redline/SKILL.md` is about 46,000 bytes today, mostly commands, exit codes and repair loops the engine now owns; the rewrite is a procedure plus `references/` for the playbook format and decision rules.

**Lint**, `checks/lint_skills.py`, in CI and as a backend unit test:

- `name` matches `^surfsense-[a-z0-9]+(-[a-z0-9]+)*$` and the folder;
- `description` at most 200 characters, trigger first;
- body at most 150 lines and 6,000 characters (about 1,500 tokens); references one level deep, each at most 20,000 characters, read only when needed;
- no `scripts/` folder and no executable file;
- no `` !` ``, `$ARGUMENTS`, `$1` or `@path`, which opencode's command route substitutes (I2; I3 lesson 17);
- no Unicode tag characters (U+E0000 to U+E007F) or other invisible format characters;
- every `surfsense_*` name it mentions exists in `offered_tools.TOOL_ORDER`;
- `skills/MANIFEST.json` lists the sha256 of every file.

**Loading.** `opencode_config()` adds `"skills": {"paths": [skills_dir, *pack_skill_dirs]}`, and `PERMISSION` becomes `permission_for(setup)`, from the fields `AgentSetup` gains in section 6:

```python
{
    "bash": setup.bash,  # "ask" or "deny", from 05's capability (section 6)
    # Last match wins. Per-thread folders come from 01; the workspace folder
    # stays for threads whose opencode session predates them. The sources/
    # deny follows both allows because "*" spans "/", so a mirrored folder
    # named "outputs" would otherwise open sources/ to edits. The instruction
    # denies come last, so those names stay unwritable inside outputs/.
    "edit": {"*": "deny",
             "*/agent/threads/*/outputs/*": "allow", "*/agent/outputs/*": "allow",
             "*/agent/threads/*/sources/*": "deny",
             "*AGENTS.md": "deny", "*CLAUDE.md": "deny", "*CONTEXT.md": "deny"},
    "external_directory": {"*": "deny", f"{setup.skills_dir}/*": "allow",
                           **{f"{d}/*": "allow" for d in setup.pack_skill_dirs},
                           f"{setup.truncation_dir}/*": "allow"},
    "skill": {"*": "deny", **{name: "allow" for name in setup.skills}},
    "webfetch": "deny", "websearch": "deny", "task": "deny", "question": "deny",
}
```

- The truncation allow restates what opencode already adds per agent, so a later opencode that stops adding it cannot hide cut outputs.
- `*` denies the built-in `customize-opencode`. A test asserts `skills.urls` is never set.
- Before each config write, `modules/agent/skills_manifest.py::verify_skills(skills_dir)` checks every shipped file against `MANIFEST.json` and leaves out any skill that fails. A pack's skills are checked against the catalogue's sha256 the same way.

**Instruction files, three layers.**

1. The edit rules above, which hold on Windows, where matching ignores case.
2. `modules/agent/model_endpoint/request_shaping.py` removes from every tool result any `<system-reminder>` block that begins `Instructions from: ` and names a path under SurfSense's data directory, before the request reaches the model, on both the chat-completions relay and [05](05-model-ladder-and-evals.md)'s Messages passthrough. SurfSense never places an instruction file there itself ([01](01-sources-and-folders.md) renames mirrored ones), so nothing legitimate is lost. This is the in-turn block on macOS and Linux, where `outputs/agents.md` passes the edit deny and a case-insensitive volume still finds it as `AGENTS.md`.
3. Before and after each turn, `agent_threads/turn.py` renames any file in the thread's working folder whose casefolded name is `agents.md`, `claude.md` or `context.md` to `<name>.blocked` and tells the user. Electron's `opencode-home.ts` refuses to start opencode when its config folder holds `AGENTS.md`, `CLAUDE.md` or any `plugin`, `plugins`, `agent`, `agents`, `command`, `commands`, `mode` or `modes` entry, and shows why.

**Context.** Three listed skills at 200 characters cost about 900 characters of system prompt with their names and locations. In a free agent thread a loaded body costs up to about 1,500 tokens and is never pruned by compaction (`session/compaction.ts`, `PRUNE_PROTECTED_TOOLS = ["skill"]`). In a job thread the body is part of the agent's prompt, so every request carries it. [05](05-model-ladder-and-evals.md) decides whether the 32,768-token floor rises.

**Variants.** One SKILL.md per skill for every agent mode; workflows read none. A per-family variant is added only when the matrix shows a rewrite passing where the shared text fails: per-backbone rewrites have gained up to 25.8 points ([arXiv 2605.30723](https://arxiv.org/abs/2605.30723)), while self-written skills lost 8 to 11 ([SkillsBench](https://arxiv.org/abs/2602.12670)).

### 6. opencode config, prompts and job entry points

**What the capability turns on.** 02 reads four fields of [05](05-model-ladder-and-evals.md)'s `Capability` and derives nothing else. `modules/agent/mode_policy.py::policy_for(capability) -> AgentPolicy` is a thin reading of them, and `opencode_config()` copies its result into the fields `AgentSetup` gains: `skills`, `bash` and `shell_section`, beside `skills_dir`, `pack_skill_dirs` and `truncation_dir`.

| `Capability` field | What 02 does with it |
|---|---|
| `engines` | `"agent"` in it lets a free agent thread run on agent `surfsense`; without it no free agent thread opens |
| `skills` | the free agent's allow-list, at most three names (decision 11) |
| `bash` | `deny` for every model until a sandbox exists ([ADR 0039](../../adr/0039-document-scripts-run-without-approval.md)); the field stays so a sandbox can later turn it to `ask` for the free agent. `deny` also drops the prompt's "Shell commands" section. Job threads and workflows deny always |
| `jobs[key].level` | `job_thread`: a job thread may open on agent `surfsense-job-<key>`. `workflow` or `job_thread`: `start_workflow()` accepts the job, since a lower level is always allowed ([06](06-product-shape.md)). `off`: neither |

How the fields are derived (the gates, the unmeasured default and its one confirmation per model, live gates, organization policy) is 05's and 06's. 05 grants `agent` from `agent_smoke` and its `free_agent_tasks` family, and labels each failed frontier case skill, tool, prompt or model; a skill or prompt fix lands here before the matrix descends. The ladder is 05's three rungs: `agent` is the free agent, `job_thread` the per-job agents below, and `workflow` the runner in section 7, whose whole-plan and per-unit calls are two shapes inside that one rung. Installers carry the agent since 7 Oct 2026 (`ENABLED_BY_DEFAULT` in [`enabled.mjs`](../../../surfsense_local/electron/scripts/opencode/enabled.mjs), [README](README.md)).

- **One free agent and one agent per job.** `surfsense` stays the free agent. Each catalogue job gets `surfsense-job-<key>`. It denies `skill`, `bash` and `todowrite`, which also drops their descriptions from every request and trims opencode's fixed text for mid-size models. It keeps `glob`.
- **Prompts.** `prompts/agent.md` gains section markers so `agent_prompt(shell=False)` drops "Shell commands" whenever bash is denied. `prompts/job.md` is the job agents' shared part: the source steps, answering, untrusted text and the engine tools, with no shell, todo or skill wording. `agent.md` with and without its shell section and `job.md` are each tested under 4,000 characters.
- **Job threads.** [06](06-product-shape.md)'s job entry opens an agent thread with `job_key` set. `opencode_config()` writes one agent per catalogue job into the config's `agent` key, once: its `prompt` is `prompts/job.md` followed by the job skill's body, read by `modules/agent/job_skill.py` `job_skill_text(job)`, which rewrites the body's relative reference links to absolute paths inside the allowed skills folder; its `permission` denies `skill`, `bash` and `todowrite`. `send_turn()` gains an `agent` argument, default `surfsense`, and each turn of a job thread passes `agent=f"surfsense-job-{key}"`. `open_session.py` also creates the session with a `permission` denying `skill` and `bash`. This is SurfSense preselecting the skill.
  - *Not a per-turn `system`.* After auto-compaction opencode continues with a message that carries the agent but no `system` (Today), so a skill sent per turn would vanish after the first compaction of a long redline. An agent's `prompt` is in every request, and the same prompt every turn keeps the prompt cache.
  - *Size.* A job agent's prompt may exceed the free agent's 4,000-character test: `job.md` stays under 4,000 and the skill body under the lint's 6,000 (section 5), so each job agent's prompt is tested under 10,000. Long references stay readable files in the skill's `references/` folder.
  - *Config.* The job agents change only with the catalogue, that is with an app update or a pack install, so a job thread never rewrites the config. They live in the config file, not as files under an `agents/` folder, so Electron's config-folder check stays as it is.
- **Not opencode commands.** The command route runs every `` !`cmd` `` in a template without asking and substitutes arguments (`session/prompt.ts`), and 2.x cannot reach plugin commands headless ([#48365](https://github.com/anomalyco/opencode/issues/48365)).
- **The prompt budget.** `agent.md`'s "Producing files" becomes: new decks, quizzes, podcasts, mind maps, images and fresh Word, spreadsheet or PDF documents go to Studio; a change to an existing Word file or spreadsheet goes through `surfsense_inspect_document` and `surfsense_edit_document`; never `read` a .docx, .xlsx or .pdf.

| Change | Characters |
|---|---|
| Today | 3,178 |
| 02: "Producing files" rewritten (drafted and measured) | +106 |
| [01](01-sources-and-folders.md): `sources/**/*.md` and the folders line | +112 |
| [03](03-editable-artifacts.md): finished files in `outputs/`, working files in `outputs/_work/` | about +150 (estimate) |
| Total | about 3,546, under 4,000 |

- **Tool guidance.** `protocol_version.initialized()` returns `instructions` of at most 800 characters (copy ids exactly, tags included; a failed edit saves nothing; cite a page you read through `inspect_document` by naming the file and page in words, since bracketed labels are for search results only), which opencode appends to the system prompt unchanged each turn.
- **Config changes.** `opencode_config()` puts a digest of the rest of the config into the provider's `name` (`"SurfSense <12 hex>"`), and `_serves()` also compares it, so a change that keeps the launch key and window is not mistaken for the running config. The skill allow-list and bash policy vary only with the model, which already restarts opencode. A pack install that adds `skills.paths` and its job agents is written by `modules/agent/config_writes.py::write_when_idle()` once no turn streams in any workspace; turns started meanwhile run on the old config. Following the product panel's graft, any future allow-list that varies by something other than the model gets its own predefined agent selected per turn, not a rewrite.

### 7. Fixed workflows

```text
worker/workflows/
  run.py                    run(version_id): one workflow, one artifact version
  steps/plan.py             one constrained call: the whole plan, or one unit of work
  steps/apply.py            the engine, through worker/engines/run.py::run_in_child
  steps/verify.py           checks a schema cannot make
  steps/repair.py           failures back to the model, at most 2 rounds
  jobs/contract_redline/    workflow.py, schema.py, prompts/{compact,capable,frontier}.md
  jobs/questionnaire_fill/  phase 5b
  jobs/make_playbook/       phase 4: a user's positions document to a playbook draft
modules/workflows/
  start.py                  start_workflow(session, workspace, job, inputs) -> version id
  tasks.py                  workflow_job(version_id), on the Studio queue: it waits on the model
modules/playbooks/
  store.py                  the structured playbook beside its source document; validate_for_job()
```

`workflow_job` takes the version id, and a workflow run's id is its version id, so 03's cancel revokes it like any other version.

A workflow has two shapes built from the same steps, both inside 05's `workflow` rung. **Whole plan**: one call writes the whole plan under the job's schema when the outline fits the window ([`model_window.py`](../../../surfsense_local/backend/modules/agent/model_window.py)). **Per unit**: the harness splits the work and makes one call per unit. The runner picks the shape from the window; the matrix measures the rung, not the shape.

The redline workflow, per unit:

1. The harness inspects the contract and splits the outline into clause groups sized to the window.
2. Per group, one call under a schema built for it: `{"findings": [{"rule": <enum of playbook rule ids>, "para": <enum of the group's outline ids, P: or tagged S:>, "quote", "action": <replace | comment | none>, "text", "comment"}]}`. The grammar can only produce anchors and rules that exist.
3. Verify: each `quote` is in its paragraph (fuzzy at 0.9, never across digits, negations or party names, as crlib repairs), and no finding breaks a playbook "never" row. Failures go back once with the reason.
4. Apply with `partial=True`, check, and release one version whose report lists what was skipped.

- Plans go through `generate.run_model(..., json_schema=...)`, with [04-workflows](../agent/04-workflows.md)' write-then-format rule where a step writes prose. A remote model that ignores `response_format` (Claude through the compatibility layer, until [05](05-model-ladder-and-evals.md)'s native provider) gets the schema checked and repaired after the reply.
- A workflow holds the model slot only while it plans. On a local model, chat meanwhile shows "Waiting for the running job" ([README](README.md)).
- If a remote model becomes unreachable mid-run, the workflow's version fails with that reason and the head stays where it was.
- Which jobs a model may run as workflows comes from `capability.jobs` (section 6); the job catalogue and its routes are [06](06-product-shape.md)'s and call `start_workflow()`.

**Playbooks** (decision 19). The redline job reads crlib's structured playbook, never a folder of prose.

- **Format.** crlib's grammar ([Today](#the-skills-project)), stored as `playbook/1`: a SurfSense-owned JSON of the parsed issues (`id`, `title`, `applies_to`, `importance`, `owner`, `escalate_to`, and the `standard`, `fallbacks`, `walk_away`, `model_language`, `tell_counterparty`, `rationale`, `detect` and `internal_notes` sections), plus `origin` (`starter`, `pack:<id>` or `user`), the source document's id and `content_hash`, and, for a user's playbook, the trace mapping from every field to its quotes. Rule ids are the issue ids, which the workflow's per-group schema enumerates; `walk_away` holds the "never" rows its verify step checks.
- **Where it lives.** A playbook is a typed file in the workspace's `playbook` role folder ([06](06-product-shape.md)'s `Role`): the user's Word, PDF, Excel, Markdown or text document is the source, and `modules/playbooks/store.py` keeps its structured form in `<workspace>/playbooks/<document id>.json`, beside it rather than in the document's own folder, because `original_path()` reads a folder's one file (Today). Starter playbooks ship as `playbook/1` files in the skill's folder; a pack's ship in the pack. A job thread reads the chosen playbook through `inspect_document` with `view: playbook`, which pages the stored issues as text.
- **Validation before a job starts.** crlib's `validate_files` runs in the worker whenever a `playbook/1` file is written, and its result is stored in the file. `validate_for_job(session, workspace_id, job)` in 06's `start_job_run()` reads only that stored result, since the API never imports engines; `workflow_job` validates again in the worker before its first model call. No playbook in the role folder gives `missing_role` (`{role: "playbook"}`). A playbook whose JSON is missing or failed validation, whose `content_hash` no longer matches its source, or which the user has not confirmed gives `playbook_invalid` (06's `{rule, problem}`: `rule` is the failing issue's id, or the playbook file when its JSON is missing, stale or unconfirmed). Both are codes on the job card; [06](06-product-shape.md) adds them and the form.
- **"Make a playbook from this document."** A fixed workflow, `jobs/make_playbook/`, on any document in the role folder: the engine extracts its text with locators (`review.py`'s `extract-text`, carried over as a library function); per group of source lines, one call under a schema drafts issues whose every field is a quote or "not specified in your playbook"; crlib's `trace` refuses any field its quotes do not support, which goes back to the model once and is then left empty; `validate_files` checks the result. It runs on the Studio queue like the other workflows but makes no artifact version: its output is a draft `playbook/1`. The draft opens in 06's form, where the user edits each issue and confirms; only a confirmed draft is saved with `origin: user`, validated again on save.
- **Moving a playbook.** Export writes the confirmed playbook as crlib's Markdown grammar and its `playbook/1` JSON in one file a colleague can import; import runs the same validation and asks for the same confirmation. The workspace export bundle carries playbooks with the rest ([README](README.md)). It ships in M6 with the redline workflow.

**Studio's Office formats** (decision 13). Each `worker/studio/office/<format>/` gains `schema.py`, a flat spec (docx: Markdown, parsed by markdown-it-py as [07](07-create-and-edit-mvp.md#after-the-slice) decision 7 sets out; pptx: slides with a layout enum, title, bullets and notes; xlsx: sheets of columns, rows and formulas; pdf: markdown), and `builder.py` on python-docx, python-pptx, xlsxwriter or reportlab, all bundled. Each block may name the sources it came from, rendered as a Sources list and resolved through the version's `inputs.sources`, so Office outputs keep chat's citations. `office/pipeline.py` `render()` asks for the spec under `json_schema`, validates, builds, and returns the spec in `Built` for [03](03-editable-artifacts.md) to store once its `Built.spec` lands.

- **The baseline first.** Before any format leaves `exec()`, 05's `schema` family runs each Office format through today's `exec()` path on the default 4B and commits those rows. The builders run the same cases.
- **Per format, per model.** `office/pipeline.py` picks the builder for a format on every remote model and on every local model where the builder's row scores at least the `exec()` baseline; elsewhere that format keeps the `exec()` path on local models, unchanged from today, until the builder catches up. No free user loses a format they have today. A builder serves small models only; strong models keep a script on the runner (decision 13).
- **Then the deletion.** When no format still needs it, one change deletes `runner.py`, the `name: docx`/`xlsx`/`pptx`/`pdf` SKILL.md files, `test_render_executes_generated_code_and_keeps_its_bytes`, `test_execute_times_out_a_hanging_script` and the other code-execution tests in `test_studio_office.py`, and the four exec tests in `test_studio.py`; builder tests replace them. [05](05-model-ladder-and-evals.md)'s `schema` family measures the Office specs like any other format.

### 8. The model endpoint

New files in `modules/agent/model_endpoint/`, applied when the model is local, except the reminder strip, which applies to every route:

- `tool_schemas.py` `simplified(tools)` rewrites what llama.cpp's grammar builder refuses (type arrays with null, null-only `anyOf`, objects without properties, free-form `additionalProperties`). SurfSense's own schemas pass through unchanged; opencode's built-ins need it.
- `text_tool_calls.py`, a transformer in `relay._frames()`, buffers content once it sees `<tool_call>` or `<function=`, parses the call and emits a `tool_calls` delta with `finish_reason: "tool_calls"`, only when the request declared tools and only for declared names.
- `tool_call_repair.py` fixes trailing commas, Python literals and truncated JSON in arguments, and matches a name by case and separator, never by fuzzy guess.
- `request_shaping.py` gains the instruction-reminder strip (section 5).
- Hermes' MIT `schema_sanitizer.py`, `qwen_parser.py` and `hermes_parser.py` are the references (I9). Ported code keeps its MIT notice and gets a provenance entry.

### 9. The harness

- **Stay on 1.18.x.** Move when all hold: the 2.x OpenAPI leaves `0.0.1` and "experimental", ACP is ported (#35457), headless commands work (#48365), and SurfSense can pin npm platform tarballs by sha512 ([`@opencode/cli`](https://registry.npmjs.org/@opencode%2Fcli)). Estimated cost L: client routes and events, `permission` to action/resource/effect `permissions`, `prompt` to `system`, `serve --standalone` so it never joins a user's own opencode, npm staging. Skills carry over because SurfSense's names equal their folders. The skills project accepted on 2.0.12, so phase 3 re-runs acceptance on 1.18.34 through SurfSense's endpoint.
- **An adapter, when a result calls for it.** `modules/agent/harness/protocol.py` would define `Harness`, shaped on [ACP](https://agentclientprotocol.com/protocol/overview): `open_session(folder, tool_servers, permission)`, `prompt(session, parts, *, agent, system)`, `updates(session)`, `answer_permission(request, reply)`, `cancel(session)`, with `opencode_harness.py` wrapping `OpencodeClient` and `TurnFrames`. It is built when either holds: [05](05-model-ladder-and-evals.md)'s matrix shows 27–35B profiles failing `agent_job` on the `surfsense-job-<key>` agents through context overflow or compaction before the first tool result, which points at opencode's fixed text rather than the task; or opencode announces an end of 1.x support.
- **A Goose spike**, at most two weeks, never shipped, on the same trigger: [Goose](https://github.com/aaif-goose/goose) (Apache-2.0) over ACP against SurfSense's model and tool endpoints, network locked, on the redline job.
- **No in-process agent loop yet.** langgraph and deepagents are not desktop dependencies, so it would be a third engine. Workflows serve small models; mid-size models get the job agents first.

### 10. Security

- **Injection from documents.** Engine output reaches the model as tool text, which `request_shaping` already defuses for control tokens. The outline labels hidden text, comments and tracked changes, `untrusted_patterns.scan` flags text addressed to an AI, and the report tells the user. No engine tool sends, fetches or writes anywhere but a new version, and tracking cannot be turned off (decision 7). Phase 6 adds fixtures with white, vanished, tiny and comment-borne instructions that the redline job must ignore, including one asking for untracked changes.
- **Supply chain.** Only shipped and pack skills load, each checked against its manifest at every config write; the four flags stay on; no `skills.urls`; `customize-opencode` is denied. A per-user install keeps resources under the user's profile, so the skills folder is writable: the manifest catches a changed skill file, but an approved shell command can alter any file of a per-user install, the app included. That residual risk is the shell approval itself, and it is why local and job threads deny bash.
- **Persisted instructions.** The three layers in section 5.
- **The server password.** `OPENCODE_PURE` stays on: without it, an approved command could drop a plugin into the config folder that then runs unapproved in every later session. Job threads and local models deny bash, which removes the exposure there. For the free remote agent, a shipped local plugin whose `shell.env` hook blanks `OPENCODE_SERVER_PASSWORD` is adopted only if both hold: Open question 3 confirms the hook works at 1.18.34 without npm work, and Electron's start check pins that one file by sha256 and refuses any other entry. Until then the exposure stays a listed Known gap behind the per-command approval.
- **Network.** A unit test parses `surfsense_engines` and refuses imports of `socket`, `http`, `urllib.request`, `httpx` and `requests`. Schemas load with `no_network=True` and a local-only resolver, and a test loads every schema with sockets blocked. The engine child's proxies point at `127.0.0.1:9`. The agent's missing egress test ([agent](../../architecture/agent.md#known-gaps)) is built in phase 6, with engine tools in the run.

### 11. Distributing skills

- Format skills ship in the installer, free, and are replaced whole on each update.
- All job content ships in the app under Apache-2.0 the same way: each job's skill, references, playbooks or mappings, templates, workflow prompts and eval cases. The security-questionnaire job and its mappings arrive in M7 inside the app, with nothing to download (decision 17).
- Phase 8 adds job packs through the plugin installer, an open-source extension mechanism that is never paywalled. A pack plugin needs a manifest field `provides.skills` naming folders the app adds to `skills.paths`, to `external_directory` (one allow per folder, so references can be read) and, for each job it adds, a `surfsense-job-<key>` agent (section 6). Under [plugins/02-extending](../plugins/bundles/02-extending.md) that is a lifecycle change maintainers design. Packs carry data only; workflow code stays in the app.
- Job packs are Apache-2.0, as the [plugins proposal](../plugins/README.md) has every plugin. The Business Source License 1.1 covers only premium plugins, such as the scraper client, kept in `surfsense_backend/app/proprietary/` and delivered by the license server to valid licenses ([README](README.md), ADR 0047). The engines and workflows stay free code in `surfsense_local/`.

## Options considered and rejected

| Option | Why not |
|---|---|
| Ship the skills project's tree as it is | 45 byte-identical and 14 modified files from proprietary skills would go out under Apache-2.0 |
| Rewrite `docxkit` and `crlib` too | They are the value (1.00 against 0.29) and share only namespace URIs and imports with the originals; the similarity scan and the legal review check that claim |
| Rewrite the validator by porting the original | Not clean-room; the gate tests it against Word instead |
| A `tracked` argument on the edit tool | Lets an injected document ask for a silent change; docxkit cannot write untracked edits anyway |
| Partial apply for agent edits | The same version would be ready in one stream and failed in another; an agent can resend |
| Engines collected into the API too | Doubles the frozen size of the engines and the parsing surface in the process that serves the UI; the routes need only stored results |
| `inspect_document` as a pending version | Read-only rows in an append-only list, and 03's one-in-flight rule would block edits behind a read |
| A 600 s MCP timeout | opencode uses a configured timeout for connecting and listing too, a stuck search would hang ten minutes, and SurfSense's client stops at 30 s |
| Keeping `exec()` for the frontier tier | The tier misclassifies, and no Studio eval exists to say builders lose |
| Switching every model to builders at once | A free user on the default 4B could lose an Office format that `exec()` gives them today; the baseline rule in section 7 prevents it |
| The job skill as a per-turn `system` | Lost at opencode's first auto-compaction (Today), silently, in exactly the long runs a redline makes |
| Holding the redline job at "Not on this model" until the playbook review | A verdict would then say something other than its eval rows; the starter label carries the review state instead |
| A playbook as a folder of the user's documents | The workflow's schema needs enumerated rule ids and "never" rows; prose has neither |
| Dropping `OPENCODE_PURE` for a password plugin without a start check | Any approved command could add a plugin that runs unapproved later |
| Skill scripts through bash with allow rules | `*` spans `..`; 8 to 12 approvals per job otherwise; no Python on opencode's `PATH` when packaged |
| A standalone Python for skills | Needed only for bash-run scripts, which this design removes |
| opencode custom tools running the engines | In-process on Bun, no permission unless they ask, one broken file breaks the registry, no 2.x loader |
| One tool per engine command | About 12 listings and a new prompt prefix with each format |
| `docx-edit-plan/1` as the tool input | 22 `$defs`, `$ref` and a discriminator: refused by the flat-schema test, garbled by small models |
| The plan as a file in `outputs/` | Paths as inputs, PowerShell encoding hazards (I3 lessons 6–7), a second home for plans |
| Engines on the Studio queue | An edit waits behind Studio jobs on one model slot |
| Engines as a backend slice | The licence gate would cover part of a tree; graders and packs would import backend paths |
| Preloading through opencode's command route | Unasked shell expansion and argument substitution |
| opencode 2.x now; Agent SDK, Codex or Crush | Experimental API and no ACP; Commercial Terms, Responses-only, FSL (E7) |
| An in-process LangGraph loop | Not a desktop dependency; workflows already serve small models |

## Phases

| # | Phase | Scope | Depends on | Size | Milestone |
|---|---|---|---|---|---|
| 0 | Clean-room fix | the tree; carry-over with provenance; scope items 1–6; behaviour specs; the no-regression gate, Word-oracle run and similarity scan; the licence gate; import ban and network-free schema loading; `AGENTS.md` | a spec author and a separate implementer; Word on Windows for the oracle; the baseline re-run on Haiku 4.5 and Sonnet 5.5 before 2026-10-15 | L: a new XSD check with MC handling, two small modules, schema terms, three eval runs per case | M1 |
| 0L | Legal review | provenance, scan report, process record, schema terms | 0's records | S; gates selling to legal and security buyers, not the free app | M1 |
| A | Agent config and tool order | `permission_for` with per-thread and legacy outputs, the `sources/` deny and instruction denies; `TOOL_ORDER`; config digest in `_serves()`; the reminder strip; Electron's config-folder check; prompt section markers | none; [01](01-sources-and-folders.md) phase 3a waits on it | S | M1 |
| B | Studio builders | four schemas and builders with source references; the `exec()` baseline on the default 4B first; each format leaves `exec()` per model where its builder scores at least that baseline; `runner.py` and its tests deleted once no format needs them | 05's `schema` family; the spec is stored when [03](03-editable-artifacts.md) phase 2 lands | M | M4 |
| 2 | Model endpoint | schema simplification, text tool calls, argument repair | none; can start now | M | M4 |
| 1 | Engine tools: inspect and edit | `JobTool`, `engine_runs`, engines queue, sidecar and interrupted-run branch, `--engine-op`, view caches, Word and PDF reads, Word edits, `apply-report/1` with codes and values, `revision_author`, cancel on abort, labels; `audience: internal` refused until 1b | 0; A; [03](03-editable-artifacts.md) phase 1 (`start_version` with `queue`); [01](01-sources-and-folders.md) phase 3a (managed `resolve_original` and `copy_original`, per-thread registration) | L: queue, sidecar, child process | M6 |
| 1b | Compare and export | the `external` file on every docx revised-copy version and its default download; `compare_documents`; `export_document` (`external`, `issues`) | 1; for `compare_documents`, [03](03-editable-artifacts.md) Open question 1 | M | M6 |
| 3 | Skills in opencode | two skills, lint, manifest check, `skills.paths`, `mode_policy`, the `surfsense-job-<key>` agents and `job.md`, `send_turn(agent=)`, job threads, MCP instructions, acceptance on 1.18.34 | 1; [05](05-model-ladder-and-evals.md)'s capability (P4a) and job-thread rows | M | M6 |
| 4 | Workflows and playbooks | runner in both shapes, redline workflow; `playbook/1`, `modules/playbooks/`, validation before a job, "Make a playbook from this document", playbook export and import; the starter label | 1; [06](06-product-shape.md)'s form and codes | M | M6 |
| 6 | Hardening | injection fixtures, egress test, the password plugin if Open question 3 clears it | 3 | M | M6 |
| 5a | Spreadsheet engine | xlsx engine (inspect, fill, check) under 04's decision 17, `surfsense-sheet-fill`, the questionnaire job skill, its mappings and its job agent, all in the app | 0, 1; [04](04-runtime-and-packs.md) RT1. The package work starts right after M1, beside M2 to M6 | XL: a clean engine with nothing built to carry | M7 |
| 5b | Questionnaire workflow | `questionnaire_fill` for models below the job thread | 4, 5a | M | M9 |
| 7 | Harness | adapter; Goose spike report | the trigger in section 9 | M | M10, only on its trigger |
| 8 | Job packs | `provides.skills`, loader, manifest check, per-pack `external_directory` and job agents | 3; plugin installer; [06](06-product-shape.md) | M | M10 |
| later | pptx engine; opencode 2.x | | section 9's triggers | L each | |

Office support improves phase 5a's output when installed, but nothing in this stream needs it. Milestone durations and contents are the [README](README.md)'s.

## Tests

- `tests/unit/agent/test_opencode_config.py`: `skills.paths` is the configured folder; no `skills.urls`; `skill` denies `*` and allows exactly the policy's skills; `external_directory` allows only the skills, pack and truncation folders; evaluated with opencode's wildcard semantics (last match wins, `*` spans `/`), an edit under `…/agent/threads/7/outputs/x.md` and under the legacy `…/agent/outputs/x.md` is allowed, and `…/agent/threads/7/sources/Research/outputs/a.md` and `…/outputs/AGENTS.md` are denied; there is one `surfsense-job-<key>` agent per catalogue job, each denies skill, bash and todowrite and keeps glob, and its prompt is `job.md` followed by that job's skill body, under 10,000 characters; `agent.md` with and without its shell section and `job.md` are each under 4,000 characters, and `job.md` mentions no `glob`, todo, skill or shell; a config differing only in its skill list has a different digest.
- `tests/unit/agent/test_mode_policy.py`: each row of the table in section 6: no free agent without `agent` in `engines`; at most three skills whatever `capability.skills` holds; `bash: deny` drops the shell section; a job opens a job thread only at `job_thread` and a workflow at `workflow` or `job_thread`.
- `tests/integration/agent/test_job_agent_compaction.py`, on the opencode harness with a scripted model endpoint: a job thread whose turn is forced to compact mid-turn still carries the skill text in the next model request, and a turn sent with a per-turn `system` does not, which pins the reason for the job agents.
- `tests/integration/agent/test_opencode_readiness.py`: when only the skill list changes, `ready_opencode()` waits for the restarted opencode instead of accepting the old one.
- `tests/integration/agent/test_tool_endpoint.py`: the names follow `TOOL_ORDER` and are all flat; a job thread's registration lists only its tools; both ids at once refused in a sentence; a stale version refused; one failing operation saves nothing, names the failure and marks the rest `BATCH_REFUSED`; an edit of a source produces `w:ins` and `w:del` and its report says tracked; a parallel database write succeeds while a call waits; inspect pages stay under 20,000 characters; `inspect_document` creates no `artifact_versions` row and a second page is served from the cache without a job; a call still running at 25 s answers with the version number.
- `tests/integration/engine_runs/`: a child past 180 s is killed and the version fails; an xlsx edit's `recalc_after()` runs after the child with its own budget and never writes an IronCalc value; a revised-copy version with an `audience: internal` comment gets an `external` file without it, which the default download returns, with the leak scan in its report; a changed original fails the version with the "changed on disk" line; cancel stops it; aborting a turn cancels its thread's runs; the original's sha256 is unchanged; the child's environment lacks `SURFSENSE_LOCAL_SECRET`; `revision_author` appears in `w:ins/@w:author`, `w:del/@w:author` and comment authors; starting the engines consumer while a Studio artifact is processing leaves it processing, and starting the Studio consumer leaves an engines v1 processing.
- `tests/unit/worker/test_engine_op_entry.py`: `worker --engine-op` runs without importing `worker.consumer` or huey.
- `tests/unit/agent/test_request_shaping.py`: a tool result ending in an `Instructions from: <data dir>/…/outputs/agents.md` reminder reaches the model without it; one naming a path outside the data directory is kept.
- `tests/unit/agent/test_text_tool_calls.py`: `<tool_call>` and `<function=` become calls for declared names only, and a call split across chunks is reassembled.
- `tests/unit/agent/test_tool_guidance.py`: the MCP instructions are under 800 characters and contain no bracketed page label.
- `tests/integration/agent/test_skills_load.py`, on the opencode harness: only allowed skills listed under the four flags; no `customize-opencode`; a skill reference and a truncated output can be read; a job thread reads a playbook reference through its rewritten link; a skill file that fails the manifest is not listed.
- `tests/integration/agent/test_instruction_guard.py`: an `agents.md` an approved command wrote is renamed before the next turn; on the macOS CI runner, writing `outputs/agents.md` and reading a sibling in the same turn sends no "Instructions from" text to the model.
- Electron `opencode-home.test.ts`: an `AGENTS.md`, a `plugins/x.js` or an `agents/x.md` in the config folder blocks opencode's start with a reason.
- `tests/integration/workflows/test_contract_redline.py`: with scripted replies, a bad quote is repaired once, then skipped and reported; the version is ready with the skipped op listed; a starter playbook puts the starter label in the issues file and a user playbook does not.
- `tests/integration/playbooks/`: every starter playbook converts to a valid `playbook/1`; a job with no playbook in the role folder fails `missing_role` before any model call; an invalid, unconfirmed or stale playbook fails `playbook_invalid`; "Make a playbook" with scripted replies leaves empty any field whose quote is not in the source and saves nothing until the user confirms; an exported playbook imports into another workspace and validates.
- `tests/unit/engines/test_messages.py`: every code an engine can emit has an English template in `messages.py` and an `engine.<code>` key in the English catalog, and a report's `message` is the English rendering of its `code` and `values`.
- Studio: builder tests replace the code-execution tests named in section 7, once no format still uses `exec()`; until then `office/pipeline.py`'s choice per format and model is tested against committed baseline and builder rows.
- `document_skills`: the carried-over suites pass; the clean-room modules pass the maintainer's tests (or the spec author's recorded rewrites of them); a fixture with no `w14:paraId` and a footnote edit apply through tagged `S:` ids, and the same ids against another version get `STALE_ANCHOR`; `flat_ops` turns every op in the mapping table into a plan docxkit's `plan.validate` accepts, and a deliberately malformed op is rejected by it; the import ban holds; every schema loads with sockets blocked; the gate fails on an unlisted file, a refused hash and a pasted block, and passes a newline-only `__init__.py` and an ECMA XSD with a matching `re-sourced` row; the lint fails on each rule; graders keep their negative controls and never import engines.
- The no-regression gate and the Word-oracle run are recorded in `document_skills/gate/`, not run in CI; CI checks the recorded hashes match the code.
- Model acceptance is [05](05-model-ladder-and-evals.md)'s matrix: E01, E02, E07, E11 and D01, D03, D05 per model, through the agent, the job thread and the workflow.

## What this changes in existing ADRs and proposals

- **ADR 0040, written with [03](03-editable-artifacts.md)**: "Edits run shipped engines on model-written plans, make append-only versions, and never write the user's file." It records decisions 5, 6, 7 and 21 here with 03's decisions 2, 3, 4, 5, 11, 12 and 13, that edits need no approval because no model-written code runs, and that bash allow-lists for skill scripts are refused because `*` spans `..`. [04](04-runtime-and-packs.md)'s pack ADR is 0040. Numbers follow the [README](README.md#adrs-to-write-or-amend)'s order; whichever lands first takes the next free number.
- **ADR 0042**: "Third-party skill material enters only through a provenance record." It binds future contributors and packs to section 2's gate.
- **[ADR 0010](../../adr/0010-studio-builders-not-sandboxes.md)**: "Where the code stands" loses its Office bullet when the last format leaves `exec()` (phase B), and links ADR 0040.
- **[ADR 0028](../../adr/0028-model-written-code-runs-with-approval.md)**: the decision stands; "No agent exists yet" goes; the Studio consequence narrows to formats that keep `exec()` on local models and goes when the last one leaves `exec()`.
- **[ADR 0008](../../adr/0008-two-job-queues.md)**: a note that an `engines` queue joins the others, for short CPU work an agent waits on, with its own interrupted-run sweep.
- **[Agent proposal](../agent/README.md)**: "Editing sources or artifacts" leaves Out of scope (with 03); the model-written code row links ADR 0040. **[02-tools](../agent/02-tools.md)** gains the engine tools and `TOOL_ORDER`; **[03-opencode](../agent/03-opencode.md)** its permissions, `skills.paths`, the free agent and the per-job agents, the config digest and the config-folder check; **[04-workflows](../agent/04-workflows.md)** the document workflows and builders.
- **[Plugins](../plugins/bundles/02-extending.md)**: `provides.skills`, in phase 8.
- **[Agent](../../architecture/agent.md)**, **[studio](../../architecture/studio.md)** and `AGENTS.md` as phases land; the Known gaps on schemas, text tool calls and the shell password go when fixed. In M5 agent.md's "agent test" points to 05's `agent_smoke` and the capability rule instead; `ENABLED_BY_DEFAULT` turned true on 7 Oct 2026. The Permissions row in [agent](../../architecture/agent.md#the-configuration) gains that opencode still allows its folder for cut tool outputs despite the `external_directory` deny (Today).

## Dependencies on other streams

- **[01](01-sources-and-folders.md)**: managed `resolve_original` and `copy_original` land in 01's phase 3a, checking `dedup_key` until 01's phase 1 fills `content_hash`, with linked roots added in 4a; `start_engine_run` calls `resolve_original` in its transaction and `engine_job` calls `copy_original` with no session open, and the "changed on disk" refusal fails the version, sets `reconcile_requested_at` and surfaces in the report. Per-thread registration (01 phase 3a) gives every tool call its thread, and every `source_id` passes `require_in_scope`. 01's per-thread edit rules, `sources/` deny included, are `permission_for()`'s; the instruction-name rename runs over the thread folder. This stream owns the prompt's total, of which 01's share is 112 characters, and the tool list and order. 01's phase 3a depends on this stream's phase A (edit rules, tool order), not on the engine tools, which removes the cycle.
- **[03](03-editable-artifacts.md)**: `start_version` gains `queue: Literal["studio", "engines"] = "studio"` and `artifact_versions` a `queue` column; `engine_job` runs a version only when its plan is complete at start, and selection edits and chat Edit run on the Studio queue and call `run_in_child`; `fail_interrupted_versions(queue)` and the Studio sweep skip engines versions; agent ops go in the `plan` role; `apply-report/1` is defined here (`ops`, `target`, `values`, `must_tell_user`, `saved`, `output_sha256`) and `from_engine` stores it as given; "a partial apply is ready" applies to workflows only; the `revisions` route, `compare` and the text-quote resolver read the stored `changes` and `views/outline.txt`, never engine code; `engine_job` ends a successful run by handing the version to `index_version` instead of calling `commit_version`, and chunks and vectors of engine and agent versions are computed by the Studio worker (`index_version` and `version_job`), never the engines worker; `edit_document` has no `tracked` argument at all; tool calls take their thread from 01's registration URL, while model-endpoint requests carry none, so 05's `active_turns` registry stays for those; `workflow_job` takes the version id, which is the run id; `clean` stays 03's file role and `external` is the default download of a docx revised copy; download suffixes are localized by 03; the tool order is section 4's.
- **[04](04-runtime-and-packs.md)**: the worker spec carrying the engines and pypdf (RT1); decision 17's rule for delivered workbooks, with `recalc_after()` after the 180 s child on its own 150 s budget, and IronCalc, if used, never in a file; phase 5a depends on RT1, not on Office support; `check_python.py` as the licence gate's rule 4; the engines consumer importing only its own tasks; the fourth sidecar's memory and the 500 MB view cache in the disk budget; the interface's "Office support".
- **[05](05-model-ladder-and-evals.md)**: the `Capability` fields section 6 reads (`engines`, `jobs[key].level`, `skills` at most three, `bash`); the three rungs, with whole-plan and per-unit as shapes inside `workflow`; `agent_smoke` and `free_agent_tasks` for the free agent, and job-thread rows on the `surfsense-job-<key>` agents; the failure triage that sends skill and prompt fixes here; the `exec()` baseline rows on the default 4B that phase B needs; at least one non-English case per job family; the matrix on these graders; the native Anthropic adapter; `active_turns`; the 27–35B result that would trigger phase 7.
- **[06](06-product-shape.md)**: job entry points and catalogue (phases 3, 4 and 8 wait on them); job packs through the plugin installer (phase 8) and the questionnaire job in the app (phase 5a); `WorkspaceSettings.revision_author` (phase 1 adds the column if 06 has not); review state for jobs whose output leaves the app; the playbook form and the `missing_role` and `playbook_invalid` codes on the job card; the starter-playbook label on the job card; the release rule of decision 18 stated the same way.

## Open questions

1. **Legal review.** Does a lawyer accept `docxkit` and `crlib` as the maintainer's own on the strength of the provenance record and a near-zero similarity scan? Do ECMA's, ISO's and Microsoft's terms allow redistributing each schema with its notice?
2. Are the skills project's real-document fixtures (`format-skills-design/SAMPLES.md`) licensed for a public repo?
3. Can a `shell.env` hook blank an inherited `OPENCODE_SERVER_PASSWORD` at 1.18.34, and does a `plugin` entry with `OPENCODE_PURE` off trigger `waitForDependencies` npm work?
4. What does a fourth worker sidecar cost idle with only engine tasks imported, and would a priority lane on the Studio queue do instead? The README's whole-stack memory budget answers the first half at the M5 and M6 exits.
5. How long do engine operations take on a 200-page contract on a laptop CPU? 180 s, 25 s and the 500 MB cache are estimates.
6. Does llama.cpp `b11050` build grammars fast enough for an enum of several hundred outline ids?
7. When the new validator and Word disagree with an existing truth file on a fixture, who rules, and is the truth re-recorded before the gate counts?
8. Who are the spec author and the implementer, and if both are agent sessions, what record of their inputs satisfies the legal review?
