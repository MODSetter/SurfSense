# File agent: business strategy

What SurfSense sells, to whom and in what order, now that it becomes a file
agent. It is the business half of the
[file agent proposal](../../docs/proposals/file-agent/README.md) and builds on
the demand research in [`seo/08-b2b-artifact-jobs.md`](seo/08-b2b-artifact-jobs.md)
and [`seo/07-what-users-do.md`](seo/07-what-users-do.md).

**Revised 21 Oct 2026** for the October B2B research
([`seo/08-b2b-artifact-jobs.md`](seo/08-b2b-artifact-jobs.md)): the security
questionnaire now ships first, the contract redline moves behind the extraction
jobs, insurance is dropped, and a team library plugin is proposed as the paid
hook. The sections changed are the headline, "Who buys first", the paid side,
plugin delivery, the frontier-cost notes, the phases, the risks and open
questions 3, 5, 10 and 12. Everything else is as written on 3 Oct.

**Revised 22 Oct 2026: the B2B jobs are paid plugins**
([ADR 0067](../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)). Each runs on
the user's machine and installs and runs only with an unexpired SurfSense
license: Individual, Team, or the 14-day trial for its term. The app, the
general agent, the engines and the shared job infrastructure stay free and
Apache-2.0. That reverses this document's rule that every job and all its
content stay free, and moves team features to later, once the jobs sell. The
sections changed are the headline, the questionnaire beta and redline notes in
"Who buys first", "What stays free and what is sold", the cost comparison, the
pricing row, phases B3, B4, B4b and B7, the risks and open questions 1 to 5
and 10.

**Sources.** Repository facts were checked on `dev_mod` at `0847e12f7` on
3 Oct 2026, and the revised sections on `dev` at `746c5fd66` on 21 Oct 2026. Market facts come from the design phase's research reports of the
same date (E1 Gemini Notebook, E2 competing file agents, E4 small models, I8
business shape), cited here by their primary URLs. Every cost below is an
**estimate** unless the text names a measurement; no SurfSense job has been
measured on any model yet
([05, Today](../../docs/proposals/file-agent/05-model-ladder-and-evals.md#today)).

## The headline

1. **Sell the job on an owned answer library, not the edit.** Agent, skills and Office
   output are a Google feature on its paid plans, and since October so is
   editing the customer's file with tracked changes: Copilot for Legal in Word
   (7 Oct), Clio's Review Playbooks (1 Oct) and Claude for Word with Anthropic's
   Claude for Legal ([08, what changed](seo/08-b2b-artifact-jobs.md#what-changed-since-29-september)).
   What SurfSense can make its own is the combination: a library the customer
   owns and governs, filled into the requester's own file without breaking it,
   on the user's machine or with the model plan they already pay for. Parts of
   it exist elsewhere (Comp AI answers from policies; UpGuard fills sheets in
   place), so the claim is the combination, never "nobody else". Editing stays the free capability every job
   writes through; the job is what is sold (item 3).
2. **The security questionnaire ships first, then RFPs from the same library;
   the contract redline waits.** This plan's own trigger has fired: "a measured
   questionnaire engine in less time than the redline's remaining work". The
   byte-preserving Excel revise engine shipped in 2.2.0, so the remaining
   questionnaire work is roughly 8 to 16 weeks of S and M items (an estimate), while the redline still needs the clean-room
   fix, M6 and a lawyer's review, and its single-document edge is now bundled
   into Word. Asking the agent to redline one's own file stays a free edit;
   the playbook redline returns after the extraction stack as a paid job
   plugin, and contract work also returns as a multi-file register on that
   stack.
3. **The app and the general agent stay free and open source; the B2B jobs
   are paid plugins.** Revised 22 Oct 2026
   ([ADR 0067](../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)): the
   security questionnaire, RFP, RFI and DDQ responses, the contract redline
   against a playbook, bank statements into a ledger, medical chronologies,
   contract and lease registers, and later B2B jobs each ship as a plugin that
   runs on the user's machine and installs and runs only with an unexpired
   SurfSense license, the 14-day trial included. The license server delivers it
   only to a valid license, never in the installer or the public plugin list.
   The plugin carries the job: its skill and agent, workflow, mappings,
   playbooks and starter playbooks, templates, eval cases and gold corpora.
   Q&A, Studio, the format skills, every engine, the study pack, the capability
   jobs and the shared job infrastructure stay Apache-2.0 in the app, and the
   user's libraries, playbooks and outputs open and export without a license.
   The license also sells the scraper plugins, priority support and Enterprise
   controls. No job plugin exists yet: each needs local paid bundles and the
   job-pack loader first. Team features come later, once the jobs sell, and
   Enterprise assurance sits on top
   ([08, how SurfSense earns](seo/08-b2b-artifact-jobs.md#how-surfsense-earns)).
4. **No job page, README line or landing claim ships before an eval row backs
   it,** and no legal page before a lawyer has reviewed the starter playbooks.
   The job × model matrix is the marketing asset no competitor can copy. A
   paid job's eval rows stay public, failures included (ADR 0067).
5. **Frontier-first costs the user about $1–3 per job on Claude Sonnet 5.5**
   (estimated). That is cheap for a business and a wall for the free audience,
   so onboarding must show the cost before the first job and keep the local
   path whole.

## The position after Gemini Notebook and Cowork

| | Gemini Notebook | Claude Cowork (Pro, Max) | Claude for Word | SurfSense, as designed |
|---|---|---|---|---|
| Where the agent runs | a cloud computer per notebook on paid tiers: Ultra and business plans from 8 Jun 2026 ([Google](https://blog.google/innovation-and-ai/products/notebooklm/better-research-notebooklm/)), AI Pro on the web "in the coming weeks" from 16 Jul ([Google](https://blog.google/innovation-and-ai/products/gemini-notebook/notebooklm-gemini-notebook/)); not the free tier | Anthropic's cloud from 6 Oct 2026; "Only on your computer" goes away ([Claude help](https://support.claude.com/en/articles/15520349-use-claude-cowork-on-web-desktop-and-mobile)) | inside Word, model in Anthropic's cloud | on the user's machine |
| Sources | uploads and Drive; no source folders, AI labels instead | folders chosen per session; cloud sessions ignore local folder attachments ([#93460](https://github.com/anthropics/claude-code/issues/93460)) | the open document | folders and linked disk folders ([01](../../docs/proposals/file-agent/01-sources-and-folders.md)) |
| Editing the user's file | new files; slide revisions ignore sources; PPTX reportedly images | "Edit with Claude" on drafts | native tracked changes ([docs](https://claude.com/docs/office-agents/word)) | revised copy with tracked changes, per-operation report, versions ([03](../../docs/proposals/file-agent/03-editable-artifacts.md)) |
| Model | Gemini only, compute quota per 5 hours | Claude only | Claude; curated list | any: local, Claude by key, OpenAI-compatible |
| Price | AI Pro $19.99/mo; Ultra $99.99+; the cloud computer is on Ultra and business plans, with Pro rolling out | Pro $20/mo, Max $100+ ([pricing](https://claude.com/pricing)) | paid Claude plan | free app; the user's API bill |

**What SurfSense can credibly own:**

- **Local by construction.** The agent loop, the index, the files, the versions
  and the engines run on the user's machine. There is no SurfSense server, no
  telemetry ([ADR 0016](../../docs/adr/0016-no-telemetry.md)) and no egress
  without per-host consent ([ADR 0027](../../docs/adr/0027-egress-consent-per-host.md)).
- **Folder-native.** A linked folder on disk as a source root. Google answered
  folder demand with labels and collections; the two folder extensions for it
  have 90,000 and 40,000 users
  ([Chrome Web Store](https://chromewebstore.google.com/detail/notebooklm-tools-for-gemi/hiibkpjljigehlnnecbgehkhfibmahjn)).
- **Edits in the customer's format, verified.** Shipped engines apply a
  model-written plan to a copy, check it and report each operation; the user's
  file is never written ([02](../../docs/proposals/file-agent/02-skills-and-engines.md)).
  This is no longer unique for a single Word file: Anthropic's Apache-2.0
  [Claude for Legal](https://github.com/anthropics/claude-for-legal) writes
  tracked changes through Claude for Word, and Copilot for Legal does it inside
  Word. What stays distinct is filling the requester's own workbook without
  breaking its dropdowns and macros, from a library the customer owns.
- **Model choice, measured.** The app says what each model can do, from a
  published eval row ([06](../../docs/proposals/file-agent/06-product-shape.md)).

**What it must not claim:**

- **That agent plus skills plus Office output is new.** Google ships it.
- **"Your files never leave your machine" when a cloud model is selected.** With
  Claude, each request's contents go to `api.anthropic.com`
  ([06, the comparison table](../../docs/proposals/file-agent/06-product-shape.md#a-free-user-on-qwen3-4b-and-a-user-on-frontier-claude)).
  The true sentence is narrower: nothing leaves unless you pick a cloud model,
  and a workspace can be marked local only, which refuses every remote model
  before a request is sent (06 decision 7).
- **Frontier results on local models.** A 4B model fails agent loops (BFCL v4
  multi-turn 22.1% for Qwen3-4B-Instruct-2507,
  [leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html)).
- **Anything about timing against Cowork's change.** It took effect on 6 Oct
  2026, and SurfSense's agent reached installers with 2.2.0 on 9 Oct 2026,
  after `ENABLED_BY_DEFAULT` turned true in
  [`enabled.mjs`](../../surfsense_local/runtimes/opencode/enabled.mjs)
  on 7 Oct.

## Who buys first, and which job ships first

Both candidates come from [08](seo/08-b2b-artifact-jobs.md). As of 21 Oct
2026 they compare like this:

| | Contract redline | Security questionnaire |
|---|---|---|
| Demand (08, October) | contracts use cases $368K/mo, 64% of searches clause lookups and templates; `ai contract review` 1,104 at $97, clickstream 1,005 → 1,156 | questionnaire core $128K/mo at $27, clickstream 5,425, −4% raw over the year; `hecvat` is 51% of it |
| Engine | `docxkit` about 19,000 lines and `crlib` about 12,000, only in the git-ignored skills project; the clean-room fix has not started ([02, Today](../../docs/proposals/file-agent/02-skills-and-engines.md#the-skills-project)). The shipped revise tool already writes tracked changes | the shipped Excel revise engine (`set_cell`, `set_range`) keeps charts, pivots and macros byte for byte; missing are workbook inspection and validation, provenance, the library and per-row review: mostly M items, roughly 8–16 weeks in all (estimate) |
| Evidence | 77.7% with the skill against 0% without, 4 evals, Haiku 4.5, n=1 | none |
| Work before release | clean-room fix (02 phase 0, L; M1), engine tools (1, L), the external download (1b, M), skills and workflow (3, 4, M), job surface (06 J3, M) | the job-gate harness (M), workbook inspection and validation (M+S+S+S), provenance (M), the library with import (M + S–M); then per-row review (M), assurance basics (S–M + M) and the row-by-row runner (L). Revised copies shipped in 2.2.0 ([08](seo/08-b2b-artifact-jobs.md#what-the-agent-needs-one-engine-for-many-jobs)) |
| Who reviews the output | a lawyer, for a counterparty | the vendor's own security lead, for a customer |
| Liability | high: no lawyer has reviewed the playbooks or output (I8 risk 6) | lower: answers come from the company's own policies, and the company signs them anyway |
| Incumbents | Copilot for Legal in Word (preview, 7 Oct 2026), Clio Review Playbooks (1 Oct), Claude for Word with Claude for Legal: all write native tracked changes against a playbook; Spellbook about $150–500/user/mo (reported) | Loopio about $24K/yr for small teams (SpendHound); Responsive about $14K; Vanta's module $3–8K/yr; self-serve tools $50–249/mo; Conveyor now shows a $0 trust-center plan and custom Enterprise; open source: Comp AI (AGPL, about 2,000 stars) |
| Free 4B tier | per clause group, not measured | per question, the shape a 4B handles when the app supplies the passage (E4 ladder, T0 "per field") |

**Recommendation (revised 21 Oct 2026): the questionnaire ships first and is
the first buyer target.**

- **The questionnaire ships first.** The first buyer is the person at a small
  B2B software vendor who answers customer questionnaires: a security lead, an
  IT lead or a founder, plus MSPs and vCISOs who answer for clients. They hold
  NDA-bound evidence and meet the same questions reworded by every customer
  ([r/sysadmin](https://www.reddit.com/r/sysadmin/comments/1rkwxpt/why_do_all_security_reviews_feel_the_same/)).
  The job fills the customer's own workbook from the company's policies and an
  approved answer library, with a source per answer and nothing unsupported,
  and it no longer waits on the clean-room fix: it runs on SurfSense's own Excel
  engine. A frontier-model beta, as a paid plugin with the 14-day trial
  ([ADR 0067](../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)), lands
  about mid-January 2027 for a minimum scope or mid-February for the full one,
  an estimate that now also waits on local paid bundles and the job-pack
  loader (08 item 11) and is re-dated once the harness lands. Which scope
  ships is
  [08's open question 3](seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer);
  the build order and the kill criteria are in
  [08](seo/08-b2b-artifact-jobs.md#lead-the-security-and-due-diligence-questionnaire),
  and the free/paid line in
  [08, how SurfSense earns](seo/08-b2b-artifact-jobs.md#how-surfsense-earns).
- **Then RFP and DDQ responses from the same library**, once the questionnaire
  passes its gate and a proposal manager joins as a design partner. Its output
  shape (06's open question) is the issuer's own response workbook first.
- **Then the extraction stack:** bank statements, medical chronologies, and
  contract and lease registers, on shared page citations, tie-out checks and a
  batch runner (about March 2027).
- **Insurance is dropped.** Applied Epic Conductor (29 Sep) and Vertafore's
  agents (GA 16 Oct) put the job inside the agency systems.
- **A redline the user asks for on their own file stays a free edit on the
  shipped revise tool**, and the playbook job (M6), a paid job plugin since
  22 Oct 2026 ([ADR 0067](../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)),
  moves behind the extraction stack. When it ships, the
  release rule that the [README](../../docs/proposals/file-agent/README.md),
  [02](../../docs/proposals/file-agent/02-skills-and-engines.md) and
  [06](../../docs/proposals/file-agent/06-product-shape.md) state still holds:
  - The redline job is offered on a model once that model's eval row passes the
    job gate. A capability verdict only ever reflects eval rows, so no verdict
    holds the job for legal review, and "Not on this model" is never used for
    one.
  - Until a lawyer reviews the starter playbooks, each starter playbook carries
    the label "Starter playbook — not reviewed by a lawyer; not legal advice" on
    the job card, in the issues list and in the exported issues file. A user's
    own playbook carries no such label.
  - Public redline pages, legal SEO pages and legal marketing wait for the lawyer's
    review. Whether the provenance legal review (02 phase 0L) also gates
    selling a job that ships no `docxkit` or `crlib` code is a question for the
    lawyer.

## What stays free and what is sold

The public promise binds this. The pricing FAQ says "everything the app itself
does stays free" and "The licence does not lock any of the app's own features"
([`pricing-content.ts`](../../www/app/(home)/pricing/pricing-content.ts),
lines 150 and 155), and [ADR 0019](../../docs/adr/0019-offline-licenses.md) says
a license never disables the app. A job plugin is a plugin, not one of the
app's own features, so the promise holds. One FAQ line, "A paid licence is only
needed for the scraper plugins and priority support", becomes untrue when the
first job plugin ships; the pricing page, the README's plugin section and the
Terms change in that release.

Revised 22 Oct 2026
([ADR 0067](../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)): the B2B jobs
moved from the free column to the license column, as paid plugins. The line
falls between an edit and a job: asking the general agent to change one's own
file, a contract included, still gives a free revised copy with tracked
changes; the playbook, the review against it and the issues list, and a
questionnaire's mappings and answer matching, are the job.

| Free, on every model the capability allows | License (Individual, $60 first year then $120; the jobs' price is open) | Enterprise (custom, invoiced) |
|---|---|---|
| Q&A, every Studio format, folders and linked folders | Premium plugins: the scraper plugin, when it ships | Organization policy that can only lower capabilities ([06](../../docs/proposals/file-agent/06-product-shape.md#organization-policy-enterprise)) |
| The agent harness, format skills, engines, versions, revised copies, review state | Priority support | Local-only by default for new workspaces |
| The study pack and the capability jobs (conversion, comparison, transcription, redaction, organizing); the shared job infrastructure: catalogue and entry points, eval harness, row-by-row runner, provenance and its checks, per-row review, page citations, tie-out validator, the `library` and `playbook` folder roles and the answer library with import and export, assurance basics, the bundle runtime; export and import of a workspace, a playbook or a library folder (M6) | The B2B job plugins, each with its skill, agent, workflow, mappings, playbooks and starter playbooks, templates and eval cases; the 14-day trial covers them; Individual or a business license at a higher price is [08's open question 2](seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer) | Later: audit log of the document scripts the agent ran, sandbox, license and plugin mirror |
| The user's own files: libraries, playbooks they wrote, outputs and revised copies open and export without a license; when a license lapses only the job plugin stops | | Named support |
| Job packs from other publishers, installed through the plugin system (M10): free, or charged on the publisher's own service, never through the SurfSense license | | |
| Office support, the LibreOffice download, which is someone else's code ([04](../../docs/proposals/file-agent/04-runtime-and-packs.md) decision 19) | | |

The free side is this large because the promise is public, Claude for Excel
and Copilot give format editing away, the student and 4B audience is the
community engine rather than the buyer ([07](seo/07-what-users-do.md)), and
gating local Apache-2.0 code invites a fork that removes the gate. So nothing
in `surfsense_local/` is gated: the license's code is premium plugins, which
never enter the open-source tree. Since 22 Oct 2026 job content is among them.
A job plugin's content is written outside the Apache-2.0 tree from its first commit,
in a folder with its own license file, and nothing a plugin sells is committed
to `surfsense_local/`. A check in the app can be stripped by a fork, so what
holds is delivery to a valid license plus the plugin's license terms.

**Where premium plugins live.** `surfsense_backend` shrinks to two things:
the license server ([`backend/license/`](../../backend/license/),
which already issues Keygen licenses) and the premium plugins, such as the
scraper client, kept in
[`app/proprietary/`](https://github.com/MODSetter/SurfSense/blob/legacy/surfsense_backend/app/proprietary/LICENSE) under
the Business Source License 1.1, which the root
[`LICENSE`](../../LICENSE) already carves out of Apache-2.0. The license server
delivers a premium plugin only to a valid license; the app downloads it after
per-host consent and checks its sha256. The installer never carries premium
plugin code. This reverses
[ADR 0025](../../docs/adr/0025-scraper-client-as-paid-plugin.md)'s premise that
paid plugin code is Apache-2.0, and the
[plugins proposal](../../docs/proposals/plugins/README.md)'s "every plugin is
Apache-2.0", for paid plugins only; the file-agent README proposes ADR 0047 to
record it.

Revised 22 Oct 2026
([ADR 0067](../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)): job content
is paid. Each B2B job plugin carries its skill, agent, workflow, playbooks,
mappings, templates and eval cases, while the engines and the shared job
infrastructure stay Apache-2.0 in `surfsense_local/`. A job plugin touches
customer files, so it runs on the user's machine as a local paid bundle, not on
the plugin host (As built, below). Its license terms are open: the Business
Source License in
[`backend/plugins/proprietary/LICENSE`](../../backend/plugins/proprietary/LICENSE)
grants production use to anyone who does not resell the work, which would let a
business run a local job plugin without a license. The choice, a narrower
Additional Use Grant or a closed license, is made with the lawyer
([08, open question 1](seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer)).

Copy should say it plainly: "The app, the agent and its
engines are open source. Business jobs and premium plugins come with a
license, which also pays for support, and a 14-day trial covers them." Open
work: a license-server route that serves a premium plugin against a valid
license, its license check and its tests, the app's download, consent and
install path, and the job-pack loader (02 phase 8, `provides.skills`), all
before the first job plugin ships
([08, item 11](seo/08-b2b-artifact-jobs.md#what-the-agent-needs-one-engine-for-many-jobs)).

**As built (21 Oct 2026).** The plugins that shipped did not take that path.
Eight scraper plugins shipped in 2.2.1 on 14 Oct and run as remote MCP servers
on `plugins.surfsense.com`; the app connects to plugins over HTTP or SSE only
([`list_entry.py`](../../surfsense_local/backend/modules/plugins/lists/list_entry.py)).
That suits plugins whose data is public. A paid feature that touches customer
files, such as a job plugin, a team library or a connector to a document
system, would send those files through SurfSense's server, so it needs the
download-and-run path above built first. That path is the deferred
[bundles proposal](../../docs/proposals/plugins/bundles/README.md), whose
runner, SDK and author CLI are partly built. Since every B2B job is now such a
plugin, local paid bundles and the job-pack loader come before the
questionnaire's beta, beside 08's items 1 to 5
([08, item 11](seo/08-b2b-artifact-jobs.md#what-the-agent-needs-one-engine-for-many-jobs)).
Team features also need in-app extension points (08, item 12).

**Gaps in the paid offer today.** On 3 Oct no plugin existed; the scrapers
shipped on 14 Oct. The Enterprise card promises a mirror, central policy and an
egress audit log that are not built (I8 gap 2) and should mark them as planned.

**What else could be sold: October's proposal.** The research in
[08](seo/08-b2b-artifact-jobs.md#how-surfsense-earns) tested the candidates
against what buyers in each job already pay for. Revised 22 Oct 2026
([ADR 0067](../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)): the job
plugins come first, and these sit beside or after them (open question 3):

1. **Public-data plugins inside the Individual licence,** on the existing host,
   starting with one capped experiment (SAM.gov opportunities and USAspending
   awards). Since 21 Oct 2026 the licence also carries one feature build request
   a year.
2. **Team features, later, once the jobs sell,** as a local bundle, selling
   only what a team needs: a library shared across installs, roles, approval by
   a second person, a signed change log, and sealed per-client libraries for
   MSPs and vCISOs. The single-user library, its owners, review dates and
   per-row review stay free. Test prices of about $1,200 a year per team and
   $2,400 per MSP, set before the decision, are hypotheses, shown only to design
   partners until at least three commit in writing.
3. **Enterprise with assurance.** The basics are published free as proof (a
   no-script job profile, a per-workspace local-only lock, an SBOM, a data-flow
   statement; signed and notarized builds already ship). Enterprise adds a
   third-party code audit, an org-wide local-only policy users cannot
   override, a local audit-log export, named support and invoicing.
4. **Paid setup through partners only**, billed by MSPs, vCISOs and proposal
   consultancies to their own clients.

**Bundled frontier model access stays rejected.** It needs a relay server that
every document passes through, against the local-first story and the decision
not to host inference (onboarding point 5 and open question 8 below), and since
2.2.2 and 2.2.3 the user's own ChatGPT or Claude plan already works.

## What frontier-first costs the user

SurfSense has no hosted inference. Every agent step is the user's bill, paid
through the user's own API key or, since 2.2.2, a ChatGPT plan through OpenAI
sign-in ([ADR 0038](../../docs/adr/0038-chatgpt-plans-sign-in-through-openai-not-codex.md))
and, since 2.2.3, a Claude Pro, Max or Team plan through the user's own Claude
Code. That makes the pitch "no per-questionnaire fee; use the plan you already
pay for". One caution for NDA-bound evidence: Claude's consumer plans (Free,
Pro, Max) fall under consumer terms that allow training if the user opts in
([Anthropic](https://www.anthropic.com/news/updates-to-our-consumer-terms)), so
job setup should recommend commercial terms or a local model.

**Prices** per million tokens, input / output / cache read
([Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing),
checked 3 Oct 2026); a 5-minute cache write costs 1.25 × input
([prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)):

| Model | Input | Output | Cache read |
|---|---|---|---|
| Opus 5.5 | $4 | $20 | $0.20 |
| Sonnet 5.5 | $2 | $10 | $0.20 |
| Haiku 4.5 (retires "not sooner than" 15 Oct 2026) | $1 | $5 | $0.10 |
| Fable 5.1 | $10 | $50 | $0.25 |

**Per-job estimates.** The redline row uses the skills project's measured
1.68 M input-side tokens per contract-redline run on Haiku, split 85% cache
reads and 15% cache writes, plus 30K output tokens at medium effort. On Sonnet
5.5 that is $0.29 of cache reads, $0.63 of cache writes and $0.30 of output:
$1.22. [05](../../docs/proposals/file-agent/05-model-ladder-and-evals.md#5-the-eval-matrix)
budgets its evals from the same measurement, split and output: its assumed `agent_job`
median of 1.2 M is about the mean over four redline and three docx cases (docx
runs used 0.52–0.74 M), which gives $0.95 per run on Sonnet. A redline alone is the
1.68 M figure. The questionnaire row is this document's own
assumption: 200 questions (the size practitioners report,
[thread](https://www.reddit.com/r/sysadmin/comments/1ovn5p5/best_way_to_get_pci_compliant/)),
run step by step, each with about 6,000 input tokens of which 2,000 are a shared
cached prefix, and 300 output tokens. The test fixtures are short; real
contracts and workbooks will cost more.

| Job | Haiku 4.5 | Sonnet 5.5 | Opus 5.5 | Fable 5.1 |
|---|---|---|---|---|
| Grounded answer (8K in, 1K out) | $0.01 | $0.03 | $0.05 | $0.13 |
| Study pack, four Studio formats (each 8K in, 2K out) | $0.07 | $0.14 | $0.29 | $0.72 |
| Contract redline, job thread | $0.61 | $1.22 | $2.15 | $5.01 |
| Same, through the OpenAI compatibility layer (no caching) | — | $3.66 | — | — |
| Security questionnaire, 200 questions step by step | $1.14 | $2.28 | $4.48 | — |

What follows from the table:

- **Native caching roughly thirds the agent bill.** The compatibility layer
  SurfSense uses today drops caching
  ([OpenAI SDK compatibility](https://platform.claude.com/docs/en/api/openai-sdk)).
  05's native Anthropic provider (P1, P2, in M4) comes before any frontier job
  is offered to users.
- **The $5 per-job default cap** (05 decision 11) fits Sonnet and Opus on these
  sizes and stops Fable on a redline. That is the right default; the cap is a
  setting.
- **Against the incumbents** a year of 50 questionnaires on Sonnet is about
  $115 in API spend (estimated) plus the license the job plugin needs ($120 at
  today's Individual renewal; the jobs' price is
  [08's open question 2](seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer)),
  against Loopio's average of
  about $24K a year for small teams or Vanta's questionnaire module at $3–8K.
  The comparison once used Conveyor's $9,600, which its pricing page no longer
  shows. It is safe to publish only once the questionnaire job has a measured
  token median.

**What that means for onboarding:**

1. **The local path stays the default and stays whole.** Onboarding already
   offers curated local models; 06 adds one line under them: "Redlines and
   working on files need a model tested for them: a larger local model, or
   Claude with your own API key."
2. **Default job model: Sonnet 5.5**, not Haiku (retiring) and not Opus (about
   twice the cost for a gain the matrix has not shown).
3. **Show money before it is spent.** A per-job estimate above $0.25, a spend
   ledger and the per-thread cost in the header (05 section 3; 06).
4. **Explain the choices once, without blame.** The user needs an API key from
   Anthropic's Console, billed by Anthropic separately from any Claude.ai
   subscription, or a Claude or ChatGPT plan through its own sign-in (2.2.2,
   2.2.3). The onboarding text says so before the user goes looking, and for
   confidential jobs it names which of these fall under commercial terms.
5. **Do not offer a managed key.** Hosted inference was dropped on purpose; a
   SurfSense key would make SurfSense a data processor for every document and
   break the "no SurfSense server" claim. An enterprise that wants Claude inside
   its own cloud can point an OpenAI-compatible connection at its own gateway;
   whether the agent works through such a gateway is not measured (open
   question 8).

## The free 4B tier: the promise and how to word it

The maintainer's goal is a free user on a 4B Qwen who gets simple Q&A and basic
artifacts through predetermined workflows. The research supports that and
nothing more: 4B models are faithful summarizers when the app retrieves
(Qwen3-4B hallucination rate 5.7%,
[Vectara](https://github.com/vectara/hallucination-leaderboard)) and produce
valid JSON under grammar constraints, and they fail as agents (E4).

| Say | Do not say |
|---|---|
| "Answers from your documents with citations, on your laptop, free, with no key and no account." | "An AI agent that runs on any laptop." |
| "Makes summaries, flashcards, quizzes, mind maps and documents from your sources." | "Edits your contracts locally" (until a 4B row passes the redline workflow) |
| "Some jobs run step by step on small models; the app shows which ones were tested." | "Works with any model." |
| "Larger local models or Claude unlock working on files." | Anything implying the 4B tier is a demo of the Claude one |

Two rules make the wording hold:

- **Every model starts "Not measured"** and loses something only on a measured
  failure (05 decision 7). No 4B verdict is invented before its row lands.
- **The 4B tier is never framed as a lesser product.** It is a different job
  set, and no free user is told to buy a license to use the agent (06, "Free,
  premium plugins and Enterprise").

## Positioning and messaging changes

| Surface | Today | Change | Gate |
|---|---|---|---|
| [README](../../README.md) lead | since 9 Oct 2026 ([#2212](https://github.com/MODSetter/SurfSense/pull/2212)): "The air-gapped, open-source NotebookLM alternative." over "The AI agent that researches, transforms and edits your documents, on your machine.", a demo video of a contract redlined as tracked changes, and a table of what it reads, creates, edits as a copy and transforms per format; it names no model and no job | Lead with the edit: your folder in, your own file back with tracked changes, on your machine, with the model you choose. Keep NotebookLM in the comparison table, updated for its cloud computer and Office output | the first job passing on one model; the 9 Oct lead names editing, which the revise tool does today, before any job has shipped |
| README comparison table | five rows against NotebookLM (now Gemini Notebook): offline use, whether documents leave the machine, editing files (added 9 Oct 2026), licence and models; no concession on media | add rows: local folders, edits the user's file with tracked changes, model choice, where the agent runs; concede media breadth | none: these are facts about Gemini Notebook today |
| [`/private-ai-for-business`](../../www/app/\(home\)/private-ai-for-business/page.tsx) | "Point it at a discovery folder…"; "Contract review runs against the executed copy sitting on your disk" | Read the copy against what has shipped. Linked folders are 01 phase 4a (M8) and the redline is 06 J3 (M6); until then the lines should describe uploads and Q&A | ship-dependent |
| Every surface naming privacy | "Documents never leave your laptop" | add the qualifier: "unless you choose a cloud model" | none |
| [Privacy page](../../www/app/\(home\)/privacy/page.tsx) | its description says "your documents never leave your machine"; section 3.2 lists three kinds of destination: update checks to github.com, model downloads to registry.ollama.ai and huggingface.co, and a model provider the user configures | M0: the qualifier. Then each milestone that adds a destination names it: api.anthropic.com in M4, including `count_tokens` calls, which send the text being counted ([05](../../docs/proposals/file-agent/05-model-ladder-and-evals.md#1-the-native-anthropic-provider-chat-titles-studio)); release-assets.githubusercontent.com for packs in M8 ([04](../../docs/proposals/file-agent/04-runtime-and-packs.md) decisions 9 and 18) | the release that adds the destination |
| [User docs](../../www/content/docs/v2/index.mdx) | one placeholder page: "Its documentation is being written now" | one how-to page per new feature in `content/docs/v2` at each milestone's exit: folders (M2); versions and Refine (M3); the Claude key and spending caps (M4); Answer and Work on files (M5); revised copies and playbooks (M6); the questionnaire (M7); linking a folder and Office support (M8); a troubleshooting page that grows with each | each milestone's release |
| [Changelog](../../www/content/changelog/) and [announcements](../../www/features/announcements/announcements-data.ts) | the newest changelog entry is dated 16 Aug 2026; v2.0.0 was tagged on 18 Sep 2026 | a changelog entry and an announcement for every milestone release, starting with M0's 2.1.x point release | each release |
| [Pricing](../../www/app/(home)/pricing/pricing-content.ts) | Individual sells scraper plugins; "No plugin ships in version 2.0" | correct the version; mark unbuilt Enterprise items as planned; keep the license to premium plugins, priority support and Enterprise. Revised 22 Oct 2026 ([ADR 0067](../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)): the job plugins join the license, and the FAQ line "A paid licence is only needed for the scraper plugins and priority support" changes, with the README's plugin section and the Terms | now (M0); the job-plugin changes in the release that ships the first job plugin |
| Job pages (new) | none | one page per named questionnaire first (HECVAT 4, CAIQ v4, SIG Lite read from the user's licensed copy) and a guide to answering a questionnaire in your own spreadsheet from your own policies; then "Answer an RFP from past proposals"; legal pages last. No HECVAT, CAIQ or SIG question text until CSA and EDUCAUSE confirm terms (08, [pages and reach](seo/08-b2b-artifact-jobs.md#pages-and-reach)) | a committed passing row on at least one model; for any legal page, also the lawyer's review of the starter playbooks |
| Cowork alternative page (new) | none | a factual comparison with Claude Cowork after its 6 Oct move to the cloud, describing shipped features only: `claude cowork alternative` is about 1,005 searches a month in clickstream at $25.58, and SurfSense is absent from the results | none: it claims no job |
| Model page (new) | none | "Which model can do which job", generated from the matrix | the first committed sweep (05 P3a, M4) |

Something the user can see ships at least every 3–4 weeks as a 2.x point
release (README). Each one carries its how-to pages, its changelog entry and
announcement, and a privacy-page change when it adds a destination.

## The eval matrix as a marketing asset

[`seo/04-competitors.md`](seo/04-competitors.md) rejected programmatic
leaderboards that need a data source SurfSense does not have. The job × model
matrix is that source:

- **It is content nobody else can write.** Each cell is a job, a model, a
  build, a window and an effort, with cases, runs, a bound and a cost per run
  (05 section 5). Google gates by plan, Anthropic by curated list; neither
  publishes per-job pass rates on local models.
- **It answers the buyer's first question** ("will this work on the laptop my
  firm gave me?") with a date and an n.
- **It publishes failures,** which is what makes the passes credible.
- **It costs money to keep.** A full frontier sweep, the Claude, OpenAI and
  Gemini columns, is about $630; with five open 100B+ models about $680–780; a
  smoke on each opencode bump about $15; the first sweep about $150 (05
  estimates). The budget follows the README: about $650
  per full sweep, run on each release that changes `profiles.json`, and a $300
  monthly cap on eval spend outside sweeps.
- **Rule:** no page, card or README sentence names a model as able to do a job
  unless a committed row says so, and it shows that row's date.

## Phases

The business phases ride on the proposal's milestones
([README](../../docs/proposals/file-agent/README.md)); the milestone column
says which release carries each.

| # | Phase | Scope | Milestone | Depends on | Size |
|---|---|---|---|---|---|
| B0 | Honest copy now | the privacy qualifier on every surface and on the privacy page; landing lines matched to what has shipped; pricing version fix; Enterprise items marked planned; a changelog entry and announcement for the 2.1.x point release | M0 | nothing | S |
| B1 | Clean engines | the clean-room fix and no-regression gate (02 phase 0), with the provenance legal review (0L) in parallel; the baseline re-run at n=3 on Haiku 4.5 and on Sonnet 5.5 at low effort before 15 Oct 2026, the earliest date Haiku 4.5 may retire | M1 | a spec author and a separate implementer | L |
| B2 | Frontier evidence | native Anthropic provider, spend ledger and caps, first paid sweep (05 P1, P2, P3a); the privacy page names api.anthropic.com; how-to pages for the Claude key and spending caps | M4 | B1 | M, about $150 |
| B4 | Questionnaire (first, revised 21 Oct) | the job-gate harness and a synthetic corpus; workbook inspection and validation, `.xlsm` uploads and an `add_sheet` operation; per-answer source and confidence; the answer library with import; then per-row review, assurance basics and the row-by-row runner (08, [items 1–8](seo/08-b2b-artifact-jobs.md#what-the-agent-needs-one-engine-for-many-jobs)). Revised 22 Oct 2026 ([ADR 0067](../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)): it ships as a paid job plugin, so local paid bundles and the job-pack loader (08 item 11) run beside items 1–5; its mappings, eval cases and corpus sit in the plugin, outside the Apache-2.0 tree, and the shared builds stay free in the app | beta about mid-Jan 2027 (minimum) or mid-Feb (full), estimates, both now also waiting on 08 item 11; re-dated once the harness lands | the harness and 08 item 11; not B1, not the redline workflow | roughly 8–16 weeks, plus item 11 (M–L + M) in parallel |
| B4b | Team features (later) | revised 22 Oct 2026: a library shared across installs, roles, second-person approval, a signed change log and sealed per-client libraries, on in-app extension points (08 item 12); local paid bundles moved to B4 | later, once the jobs sell | the job plugins selling; a writable shared-library location, an exception to [01's decision 9](../../docs/proposals/file-agent/01-sources-and-folders.md#decisions) that stays a proposal until then | M–L + L |
| B7 | RFP, then the extraction stack | RFP and DDQ responses from the same library; then page citations, table-preserving PDF reading, a tie-out validator and batch, carrying bank statements, medical chronologies, and contract and lease registers (08). Each job ships as a paid plugin; page citations, the tie-out validator and batch stay free in the app ([ADR 0067](../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)). Insurance is dropped | RFP after B4 passes its gate; extraction about March 2027 | B4 | L each |
| B3 | Redline job (moved behind B7) | 02 phases 1, 1b, 3, 4 and 6; 03 phase 4; 06 J3; revised copies download without internal comments by default; the user's own playbook and "Make a playbook from this document"; workspace and playbook export. Revised 22 Oct 2026 ([ADR 0067](../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)): the playbook review ships as a paid job plugin carrying `crlib`, `review.py`, `playbook.py` and the starter playbooks, labelled; the engines and the export stay free in the app. A user-directed redline already ships free on the revise tool | after the extraction stack | B1, B2; versions (M3); per-thread folders and `copy_original` (M5); local paid bundles and the job-pack loader (08 item 11) | L |
| B5 | Pages | the Cowork alternative page now; model page; questionnaire pages; RFP page; legal pages after the lawyer's review of the starter playbooks | from now (Cowork page), M4 (model page) and the questionnaire beta | committed rows from B2–B4 | M |
| B6 | Enterprise | organization policy (06 E1), an org-wide local-only policy, a local audit-log export and a third-party code audit; mirror when a customer's deployment needs it | M10, or earlier on an Enterprise conversation | an Enterprise conversation | M |

## Risks, and what would change the plan

| Risk | Signal | What changes |
|---|---|---|
| Anthropic, Microsoft or Google ship a local agent | a local option returns to Cowork or Copilot | lead with model choice, open source and per-job evidence; local alone stops being the wedge |
| Tracked-change redlining becomes free in Word | **fired in October**: Copilot for Legal in Word (7 Oct), Clio Review Playbooks (1 Oct), Claude for Legal | applied: the questionnaire ships first; a user-directed redline stays a free edit, and the playbook redline waits behind the extraction stack as a paid job plugin |
| A suite vendor ships a questionnaire skill with a persistent library | Microsoft, Anthropic or Google fill questionnaires in place and keep the library; or Vanta gives questionnaire automation away | the questionnaire drops to second wave; lead with model choice, the owned library and local processing (08 kill criteria) |
| Licensed question text | CSA, EDUCAUSE or Shared Assessments object to mappings or samples | no question text ships until terms are confirmed in writing; mappings read the user's own copy; eval samples are synthetic |
| The clean-room gate fails or the legal review flags `docxkit` or `crlib` | gate results in `document_skills/gate/`; lawyer's opinion | the flagged code joins the rewrite list; M1 and with it B3 slip; nothing ships before it passes |
| The privacy story contradicts the Claude default | a buyer or reviewer quotes "never leaves your laptop" against a Claude run | B0's qualifier; local-only workspaces; the privacy page names each destination as it arrives |
| Liability for a legal output | a user ships an unreviewed redline | review state on job outputs (06 decision 10), with a reviewer name the user enters and the app calls self-attested; the starter-playbook label on the job card, the issues list and the exported issues file; legal pages wait for the lawyer's review |
| Prompt injection from a counterparty's file | an exfiltration like the one PromptArmor showed on Cowork ([write-up](https://www.promptarmor.com/resources/claude-cowork-exfiltrates-files)) | engines cannot write untracked or send anything (02 decisions 7, section 10); job threads deny bash; ship 02 phase 6's injection fixtures and egress test before marketing the questionnaire to security buyers. Phase 6 sits in M6 today, so either it moves forward with the questionnaire or that marketing waits: a scheduling decision for the maintainer |
| A competitor copies a job plugin's content, or a fork strips its license check | SurfSense's playbooks, mappings or templates ship in another product; a job plugin runs without a license | Revised 22 Oct 2026 ([ADR 0067](../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)): job content is no longer Apache-2.0; it sits outside the open tree and the license server delivers it and its updates only to a valid license. Its license terms, still open ([08, open question 1](seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer)), set what a copier may do. The engines and shared job infrastructure stay Apache-2.0, and the lead still rests on the app, the engines and the published eval rows |
| Frontier cost deters users | measured token medians well above these estimates | default to the workflow level where it passes; cheaper columns earn rows |
| The 4B tier fails its own floors | 4B rows below 05 section 7 targets | the free promise narrows to Q&A and the formats that pass; the wording above already allows it |
| macOS cannot ship | notarization stops when Apple's developer agreement lapses, as on 3 Oct 2026 until the account holder accepted it; the v2.1.0 and v2.2.0 builds were notarized, 2.2.0's carrying opencode ([04](../../docs/proposals/file-agent/04-runtime-and-packs.md#signing-and-notarization)) | the account holder accepts it, which needs no code; Windows and Linux ship meanwhile |
| License holders get nothing | scraper license mode not live when hosted tokens are purged on 18 Oct 2026 (I8 gap 1) | priority support is the license's deliverable until the scraper plugin ships through the license server, so consider extending affected licenses. Revised 22 Oct 2026: what a license adds next is the B2B job plugins ([ADR 0067](../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)), with their price open ([08, open question 2](seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer)) |

**What would change the order of jobs:** a measured questionnaire engine in
less time than the redline's remaining work, or a lawyer's review that cannot
be had soon. Either moves the questionnaire to ship first. The first fired in
October (2.2.0 shipped the Excel revise engine), and the order changed. What
would change it again is in [08's kill criteria](seo/08-b2b-artifact-jobs.md#kill-criteria).

## Open business questions

Each with a recommended answer, except where a question now points to 08.

1. **Does the free promise cover the agent?** Yes. Decide it in the open now,
   because the FAQ is live, 06 already assumes it, and the agent has been in
   installers since 2.2.0 (9 Oct 2026). Revised 22 Oct 2026
   ([ADR 0067](../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)): the
   general agent stays free, including a revised copy of the user's own file,
   a contract included; the B2B jobs are paid plugins on top of it.
2. **Where do premium plugins live?** Decided: under the Business Source
   License in `surfsense_backend/app/proprietary/`, served by the license
   server to a valid license, with `surfsense_backend` otherwise reduced to the
   license server. Revised 22 Oct 2026
   ([ADR 0067](../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)): job
   content is premium. Each B2B job plugin is written outside the Apache-2.0
   tree, runs on the user's machine and reaches only a valid license; its
   license terms are open
   ([08, open question 1](seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer)).
   That also settles expiry for job plugins: a job plugin runs only with an
   unexpired license and stops when it lapses, while the app and the user's
   files keep working, which keeps ADR 0019's rule that a license never
   disables the app.
3. **What does a license sell beyond premium plugins, support and
   Enterprise?** Revised 22 Oct 2026: the B2B job plugins
   ([ADR 0067](../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)). Beside
   them, as proposed on 21 Oct: public data plugins inside the Individual
   licence and Enterprise with assurance; team features come later, once the
   jobs sell (What stays free and what is sold). Bundled model access stays
   rejected. The jobs' license terms and price are 08's open questions 1 and 2.
4. **Is $120 a year the right Individual price for a business tool?** Revised
   22 Oct 2026: it is now a question about the job plugins and is
   [08's open question 2](seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer),
   with no recommendation here. Either the Individual license ($60 the first
   year, then $120) unlocks the job plugins, or business jobs need a business
   license at a higher price. Self-serve questionnaire tools charge $50 to $249
   a month. Whichever is chosen, a price rises on evidence, never by gating
   free features.
5. **Which job first?** Revised 21 Oct 2026: the questionnaire ships first,
   as a beta about mid-January or mid-February 2027; then RFPs from the same
   library; then the extraction stack; the redline playbook job comes after
   (above). Since 22 Oct 2026 each ships as a paid job plugin with the 14-day
   trial, and both beta dates also wait on local paid bundles and the job-pack
   loader ([ADR 0067](../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)).
6. **Does the lawyer review gate the redline's release or only its marketing?**
   Only its marketing. The redline job is offered on a model once that model's
   eval row passes the job gate; no capability verdict is used to hold it.
   Until the lawyer's review, each starter playbook carries "Starter playbook —
   not reviewed by a lawyer; not legal advice" on the job card, in the issues
   list and in the exported issues file, and a user's own playbook carries no
   label. Public redline pages, legal SEO pages and legal marketing wait for the review.
   The README, 02 and 06 state the same rule.
7. **Must a sandbox exist before selling to security buyers?** No, but two
   things must: job threads with bash denied, and Studio's `exec()` of
   model-written code inside the worker replaced, which
   [#2184](https://github.com/MODSetter/SurfSense/pull/2184) did on 11 Oct
   2026. After the create-and-edit
   slice, Studio's Word and PDF take two paths
   ([07](../../docs/proposals/file-agent/07-create-and-edit-mvp.md#after-the-slice)):
   small models write Markdown that committed builders render, and strong
   models keep writing a script, which runs in SurfSense's script runner, a
   separate process killed at its time limit
   ([ADR 0039](../../docs/adr/0039-document-scripts-run-without-approval.md)).
   PowerPoint and Excel run their scripts on the runner for every model
   since #2184, and move to a builder from a flat spec for small models once
   it scores at least the script path's baseline (02 phase B); until then a
   format keeps its script, so free users lose nothing. No
   model-written code runs in a job on any model. The runner is not a sandbox:
   a script runs with the user's privileges, and ADR 0039 has this answer
   revisited before SurfSense is marketed to security, legal or government
   buyers.
8. **A managed-key or hosted-inference offer for enterprises?** No. Measure the
   agent through an enterprise's own OpenAI-compatible gateway instead, and
   publish that row.
9. **Who pays for evals?** The project: about $650 per full sweep on each
   release that changes profiles, and a $300 monthly cap outside sweeps, as the
   README recommends; community-submitted local rows (05 section 9) cover
   hardware the project lacks.
10. **Is a Team tier needed?** Revised 22 Oct 2026
    ([ADR 0067](../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)): team
    features come later, once the jobs sell
    ([08's open question 4](seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer)).
    Colleagues keep sharing through files for free: a playbook, a library
    folder or a whole workspace exports to a file another install imports (M6).
    Team features would sell only what files cannot do: a library shared
    across installs, roles, second-person approval, a signed change log, and
    sealed per-client libraries. The shared library needs a writable location,
    an exception to 01's decision 9 that stays a proposal until then.
    `pricing-content.ts` keeps Team and Enterprise as one quoted tier until
    team features ship; test prices go to design partners and a pre-order page
    only.
11. **Should job pages deep-link into the app?** Not in v1: link to downloads
    and the job's setup instructions. A `surfsense://` handler is new attack
    surface ([06, open questions](../../docs/proposals/file-agent/06-product-shape.md#open-questions)).
12. **Should SurfSense speak to Cowork's change on 6 Oct?** Yes. The agent ships
    in installers since 2.2.0, and the demand exists: `claude cowork
    alternative` is about 1,005 searches a month in clickstream at $25.58, with
    SurfSense absent from the results, and `claude cowork linux` rose from 502
    to 955 (08). Write one factual comparison page about shipped features now.
