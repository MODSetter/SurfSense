# File agent: business strategy

What SurfSense sells, to whom and in what order, now that it becomes a file
agent. It is the business half of the
[file agent proposal](../../docs/proposals/file-agent/README.md) and builds on
the demand research in [`seo/08-b2b-artifact-jobs.md`](seo/08-b2b-artifact-jobs.md)
and [`seo/07-what-users-do.md`](seo/07-what-users-do.md).

**Sources.** Repository facts were checked on `dev_mod` at `0847e12f7` on
3 Oct 2026. Market facts come from the design phase's research reports of the
same date (E1 Gemini Notebook, E2 competing file agents, E4 small models, I8
business shape), cited here by their primary URLs. Every cost below is an
**estimate** unless the text names a measurement; no SurfSense job has been
measured on any model yet
([05, Today](../../docs/proposals/file-agent/05-model-ladder-and-evals.md#today)).

## The headline

1. **Sell the edit, not the agent.** Agent, skills and Office output are now a
   Google feature on its paid plans. Editing the customer's own file, with
   tracked changes and a per-operation report, on the user's machine, with the
   model they choose, is offered by nobody credible.
2. **Contract redline ships first; the security questionnaire is the first
   buyer target.** The redline engine exists and the questionnaire engine does
   not, so the redline ships first (M6). The questionnaire is the larger market
   with the lower liability. Its spreadsheet engine starts right after the
   clean engines (M1), and the job ships free in M7.
3. **The app, the agent and every job, with all its content, stay free and
   open source.** Job skills, playbooks, questionnaire mappings, RFP templates
   and eval cases are Apache-2.0 and ship in the app. The license sells premium
   plugins, priority support and Enterprise controls. Premium plugins are
   source-available under the Business Source License in
   `surfsense_backend/app/proprietary/`, and the license server delivers them
   only to a valid license. The paid side is thin today; what else to sell is
   decided after the
   [create-and-edit slice](../../docs/proposals/file-agent/07-create-and-edit-mvp.md)'s
   video and real user feedback.
4. **No job page, README line or landing claim ships before an eval row backs
   it,** and no legal page before a lawyer has reviewed the starter playbooks.
   The job × model matrix is the marketing asset no competitor can copy.
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
  Anthropic's open legal plugin stops at Markdown redlines
  ([knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins)).
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
- **Anything about timing against Cowork's change.** It takes effect on 6 Oct
  2026, and SurfSense's agent is still off in installers
  (`ENABLED_BY_DEFAULT = false` in
  [`enabled.mjs`](../../surfsense_local/electron/scripts/opencode/enabled.mjs)).
  There is nothing to point a Cowork user to yet. The flag flips in M5, once
  05's `agent_smoke` rows on the native Claude route and its `free_agent_tasks`
  rows are committed and agent files become versions (03 phase 3)
  ([README](../../docs/proposals/file-agent/README.md)).

## Who buys first, and which job ships first

Both candidates come from [08](seo/08-b2b-artifact-jobs.md). They compare like
this:

| | Contract redline | Security questionnaire |
|---|---|---|
| Demand (08) | Legal play $584K/mo ad value; `ai contract review` 880 at $67, clickstream 807 → 1,261 | Security play $701K/mo; named questionnaires 3,700–4,400 clickstream a month all year, +12% |
| Engine | built: `docxkit` about 19,000 lines, `crlib` about 12,000 ([02, Today](../../docs/proposals/file-agent/02-skills-and-engines.md#the-skills-project)) | `xlsx` is a scaffold; every command `NOT_IMPLEMENTED` |
| Evidence | 77.7% with the skill against 0% without, 4 evals, Haiku 4.5, n=1 | none |
| Work before release | clean-room fix (02 phase 0, L; M1), engine tools (1, L), the external download (1b, M), skills and workflow (3, 4, M), revised copies (03 phase 4, L), job surface (06 J3, M), all in M6 | all of the left except the redline workflow, plus the xlsx engine (02 phase 5a, XL) and a recalculation decision ([04](../../docs/proposals/file-agent/04-runtime-and-packs.md) decisions 3, 17); M7 |
| Who reviews the output | a lawyer, for a counterparty | the vendor's own security lead, for a customer |
| Liability | high: no lawyer has reviewed the playbooks or output (I8 risk 6) | lower: answers come from the company's own policies, and the company signs them anyway |
| Incumbents | Claude for Word and Microsoft's Word Legal agent do native tracked changes inside Word; Spellbook about $89–500/user/mo (reported) | Conveyor from $9,600/yr ([pricing](https://www.conveyor.com/pricing)); Loopio about $20k/yr (reported); Vanta bundled; open source: QResponder with 6 stars |
| Free 4B tier | per clause group, not measured | per question, the shape a 4B handles when the app supplies the passage (E4 ladder, T0 "per field") |

**Recommendation: ship the redline first, aim at the questionnaire buyer first.**

- **Redline ships first** because it is the job whose engine exists, and it
  exercises everything the questionnaire needs too: the clean-room fix, engine
  tools, versions, revised copies, review state and the eval matrix. It ships
  free in the app in M6, under one release rule that the
  [README](../../docs/proposals/file-agent/README.md),
  [02](../../docs/proposals/file-agent/02-skills-and-engines.md) and
  [06](../../docs/proposals/file-agent/06-product-shape.md) also state:
  - The redline job is offered on a model once that model's eval row passes the
    job gate. A capability verdict only ever reflects eval rows, so no verdict
    holds the job for legal review, and "Not on this model" is never used for
    one.
  - Until a lawyer reviews the starter playbooks, each starter playbook carries
    the label "Starter playbook — not reviewed by a lawyer; not legal advice" on
    the job card, in the issues list and in the exported issues file. A user's
    own playbook carries no such label.
  - Public job pages, SEO pages and legal marketing wait for the lawyer's
    review. Selling to legal and security buyers also waits for the provenance
    legal review (02 phase 0L).
- **The questionnaire is the first buyer target.** The first buyer is the
  person at a small B2B software vendor who answers customer questionnaires: a
  security lead, an IT lead or a founder. They hold NDA-bound evidence, they
  meet the same questions reworded by every customer
  ([r/sysadmin](https://www.reddit.com/r/sysadmin/comments/1rkwxpt/why_do_all_security_reviews_feel_the_same/)),
  and they cannot justify $9,600 to $20,000 a year. The xlsx engine work (02
  phase 5a) starts right after M1, in parallel with the redline. The job (06 J4)
  ships free in M7, with its mappings in the app: it needs the engine tools (02
  phase 1) and revised copies (03 phase 4), not the redline workflow. What such
  a team might pay for is undecided (What stays free and what is sold).
  On the README's rough milestone durations (one maintainer with agents, to be
  replaced by measured velocity after M1), M7 lands about 18 to 28 weeks after
  M0 starts: February to mid-April 2027, an estimate.
- **Then:** RFP response (shares the evidence and library folders; its output
  shape is an [open question in 06](../../docs/proposals/file-agent/06-product-shape.md#open-questions)),
  then the second wave in 08: insurance, real estate and construction, finance.

## What stays free and what is sold

The public promise binds this. The pricing FAQ says "everything the app itself
does stays free" and "The licence does not lock any of the app's own features"
([`pricing-content.ts`](../../surfsense_web/components/pricing/pricing-content.ts),
lines 163 and 168), and [ADR 0019](../../docs/adr/0019-offline-licenses.md) says
a license never disables the app.

| Free, on every model the capability allows | License (Individual, $60 first year then $120) | Enterprise (custom, invoiced) |
|---|---|---|
| Q&A, every Studio format, folders and linked folders | Premium plugins: the scraper plugin, when it ships | Organization policy that can only lower capabilities ([06](../../docs/proposals/file-agent/06-product-shape.md#organization-policy-enterprise)) |
| The agent harness, format skills, engines, versions, revised copies, review state | Priority support | Local-only by default for new workspaces |
| Every catalogue job with all its content, Apache-2.0 and in the app: job skills, workflows, playbooks, questionnaire mappings, RFP templates and eval cases; a user's own playbook made from their positions document; export and import of a workspace, a playbook or a library folder (M6) | | Later: audit log of the document scripts the agent ran, sandbox, license and plugin mirror |
| Job packs installed through the plugin system (M10): an open-source way to extend the catalogue, never paywalled | | Named support |
| Office support, the LibreOffice download, which is someone else's code ([04](../../docs/proposals/file-agent/04-runtime-and-packs.md) decision 19) | | |

The free side is this large because the promise is public, Claude for Excel
and Copilot give format editing away, the student and 4B audience is the
community engine rather than the buyer ([07](seo/07-what-users-do.md)), and
gating local Apache-2.0 code invites a fork that removes the gate. So nothing
in `surfsense_local/` is gated, job content included: the license's code is
premium plugins, which never enter the open-source tree.

**Where premium plugins live.** `surfsense_backend` shrinks to two things:
the license server ([`app/license/`](../../surfsense_backend/app/license/),
which already issues Keygen licenses) and the premium plugins, such as the
scraper client, kept in
[`app/proprietary/`](../../surfsense_backend/app/proprietary/LICENSE) under
the Business Source License 1.1, which the root
[`LICENSE`](../../LICENSE) already carves out of Apache-2.0. The license server
delivers a premium plugin only to a valid license; the app downloads it after
per-host consent and checks its sha256. The installer never carries premium
plugin code. Job content is not premium: the engines, workflows, job skills,
playbooks, mappings, templates and eval cases all stay Apache-2.0 in
`surfsense_local/`. This reverses
[ADR 0025](../../docs/adr/0025-scraper-client-as-paid-plugin.md)'s premise that
paid plugin code is Apache-2.0, and the
[plugins proposal](../../docs/proposals/plugins/README.md)'s "every plugin is
Apache-2.0", for paid plugins only; the file-agent README proposes ADR 0047 to
record it.

Copy should say it plainly: "The app, its engines and every job are open
source. Premium plugins are source-available and come with a license, which
also pays for support." Open work: a license-server route that serves a
premium plugin against a valid license, its license check and its tests, and
the app's download, consent and install path, all before the first premium
plugin ships.

**Gaps in the paid offer today.** No plugin exists, the pricing page still says
"No plugin ships in version 2.0" while the app is 2.1.0
([`package.json`](../../surfsense_local/electron/package.json), line 6), and the
Enterprise card promises a mirror, central policy and an egress audit log that
are not built (I8 gap 2). Until the scraper plugin ships, priority support is
the Individual license's only deliverable, and the Enterprise card should mark
unbuilt items as planned.

**What else could be sold is undecided.** The paid side is thin today: one
premium plugin that has not shipped, priority support, and Enterprise controls
that are mostly unbuilt. What a license sells beyond them is revisited after
the [create-and-edit slice](../../docs/proposals/file-agent/07-create-and-edit-mvp.md)'s
video and real user feedback. None of the candidates prices job content, and
none is chosen:

1. **Organization features individuals do not need.** A shared answer library
   and shared playbooks across a team, admin policy, an audit log, managed
   deployment and SSO. They suit the questionnaire buyer, whose team answers
   the same questions for every customer.
2. **Bundled frontier model access.** A license that includes Claude usage, so
   the user needs no API key. It needs a relay server, and every document sent
   to the model passes through it. That goes against the local-first story and
   against the decision not to host inference, which this plan keeps today
   (onboarding point 5 and open question 8 below).
3. **Support and assurance for regulated buyers.** Security documentation, a
   sandbox and signed builds. Security and legal buyers also need an invoice, a
   support channel and a named party, regardless of source availability.

## What frontier-first costs the user

SurfSense has no hosted inference, and a Claude subscription cannot be used:
Claude is reached with the user's own API key
([ADR 0038](../../docs/adr/0038-chatgpt-plans-sign-in-through-openai-not-codex.md)).
Every agent step is the user's bill.

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
  $115 in API spend plus a $120 license, against Conveyor's $9,600. That
  comparison is safe to publish only once the questionnaire job has a measured
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
4. **Explain the key once, without blame.** The user needs an API key from
   Anthropic's Console, billed by Anthropic separately from any Claude.ai
   subscription. The onboarding text says so before the user goes looking.
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
| [README](../../README.md) lead | "The air-gapped, open-source NotebookLM alternative. Turn documents you can't upload into briefings, decks, reports, study guides and podcasts" | Lead with the edit: your folder in, your own file back with tracked changes, on your machine, with the model you choose. Keep NotebookLM in the comparison table, updated for its cloud computer and Office output | the first job passing on one model; until then only the comparison table changes |
| README comparison table | NotebookLM rows on sources, models, licence | add rows: local folders, edits the user's file with tracked changes, model choice, where the agent runs; concede media breadth | none: these are facts about Gemini Notebook today |
| [`/private-ai-for-business`](../../surfsense_web/app/\(home\)/private-ai-for-business/page.tsx) | "Point it at a discovery folder…"; "Contract review runs against the executed copy sitting on your disk" | Read the copy against what has shipped. Linked folders are 01 phase 4a (M8) and the redline is 06 J3 (M6); until then the lines should describe uploads and Q&A | ship-dependent |
| Every surface naming privacy | "Documents never leave your laptop" | add the qualifier: "unless you choose a cloud model" | none |
| [Privacy page](../../surfsense_web/app/\(home\)/privacy/page.tsx) | its description says "your documents never leave your machine"; section 3.2 lists three kinds of destination: update checks to github.com, model downloads to registry.ollama.ai and huggingface.co, and a model provider the user configures | M0: the qualifier. Then each milestone that adds a destination names it: api.anthropic.com in M4, including `count_tokens` calls, which send the text being counted ([05](../../docs/proposals/file-agent/05-model-ladder-and-evals.md#1-the-native-anthropic-provider-chat-titles-studio)); release-assets.githubusercontent.com for packs in M8 ([04](../../docs/proposals/file-agent/04-runtime-and-packs.md) decisions 9 and 18) | the release that adds the destination |
| [User docs](../../surfsense_web/content/docs/v2/index.mdx) | one placeholder page: "Its documentation is being written now" | one how-to page per new feature in `content/docs/v2` at each milestone's exit: folders (M2); versions and Refine (M3); the Claude key and spending caps (M4); Answer and Work on files (M5); revised copies and playbooks (M6); the questionnaire (M7); linking a folder and Office support (M8); a troubleshooting page that grows with each | each milestone's release |
| [Changelog](../../surfsense_web/changelog/content/) and [announcements](../../surfsense_web/lib/announcements/announcements-data.ts) | the newest changelog entry is dated 16 Aug 2026; v2.0.0 was tagged on 18 Sep 2026 | a changelog entry and an announcement for every milestone release, starting with M0's 2.1.x point release | each release |
| [Downloads](../../surfsense_web/app/\(home\)/downloads/page.tsx) | Windows, macOS and Linux panels, with no macOS status | a macOS status line: notarization blocked since 3 Oct 2026, and, if it still is in M5, the agent ships on Windows and Linux first | now (M0) |
| [Pricing](../../surfsense_web/components/pricing/pricing-content.ts) | Individual sells scraper plugins; "No plugin ships in version 2.0" | correct the version; mark unbuilt Enterprise items as planned; keep the license to premium plugins, priority support and Enterprise, and price no job or job content | now (M0) |
| Job pages (new) | none | one page per job, following the vendors that win organically with one page per artifact (08): "Fill a security questionnaire from your own policies", "Redline a contract against your playbook", "Answer an RFP from past proposals"; each names the document languages its job supports | a committed passing row on at least one model; for the redline page and any legal SEO page, also the lawyer's review of the starter playbooks |
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
| B0 | Honest copy now | the privacy qualifier on every surface and on the privacy page; landing lines matched to what has shipped; pricing version fix; Enterprise items marked planned; the macOS status on /downloads; a changelog entry and announcement for the 2.1.x point release | M0 | nothing | S |
| B1 | Clean engines | the clean-room fix and no-regression gate (02 phase 0), with the provenance legal review (0L) in parallel; the baseline re-run at n=3 on Haiku 4.5 and on Sonnet 5.5 at low effort before 15 Oct 2026, the earliest date Haiku 4.5 may retire | M1 | a spec author and a separate implementer | L |
| B2 | Frontier evidence | native Anthropic provider, spend ledger and caps, first paid sweep (05 P1, P2, P3a); the privacy page names api.anthropic.com; how-to pages for the Claude key and spending caps | M4 | B1 | M, about $150 |
| B3 | Redline in the app | 02 phases 1, 1b, 3, 4 and 6; 03 phase 4; 06 J3; revised copies download without internal comments by default; the user's own playbook and "Make a playbook from this document"; workspace and playbook export; free, with the starter playbook labelled | M6, after the agent is on in installers (M5) | B1, B2; versions (M3); per-thread folders and `copy_original` (M5) | L |
| B4 | Questionnaire | the xlsx engine (02 phase 5a), started right after M1; 06 J4, free, with its mappings and eval cases Apache-2.0 in the app. Open-source job packs through the plugin installer (02 phase 8, 06 P1) follow in M10, never paywalled | M7 | B1; 02 phase 1 and 03 phase 4 from M6; not the redline workflow | XL |
| B5 | Pages | model page; questionnaire job page; redline page and legal SEO pages after the provenance legal review (02 phase 0L) and the lawyer's review of the starter playbooks | from M4 (model page) and M7 (questionnaire page) | committed rows from B2–B4 | M |
| B6 | Enterprise | organization policy (06 E1); audit log and mirror when a customer's deployment needs them | M10 | an Enterprise conversation | M |
| B7 | RFP and second wave | RFP job, then insurance, real estate, finance (08) | after M7; not yet in a milestone | B4 | L each |

## Risks, and what would change the plan

| Risk | Signal | What changes |
|---|---|---|
| Anthropic, Microsoft or Google ship a local agent | a local option returns to Cowork or Copilot | lead with model choice, open source and per-job evidence; local alone stops being the wedge |
| Tracked-change redlining becomes free in Word | Claude for Word and the Word Legal agent spread to small firms | the redline's sale narrows to local, privileged work and playbooks; the questionnaire matters more |
| The clean-room gate fails or the legal review flags `docxkit` or `crlib` | gate results in `document_skills/gate/`; lawyer's opinion | the flagged code joins the rewrite list; M1 and with it B3 slip; nothing ships before it passes |
| The privacy story contradicts the Claude default | a buyer or reviewer quotes "never leaves your laptop" against a Claude run | B0's qualifier; local-only workspaces; the privacy page names each destination as it arrives |
| Liability for a legal output | a user ships an unreviewed redline | review state on job outputs (06 decision 10), with a reviewer name the user enters and the app calls self-attested; the starter-playbook label on the job card, the issues list and the exported issues file; legal pages wait for the lawyer's review |
| Prompt injection from a counterparty's file | an exfiltration like the one PromptArmor showed on Cowork ([write-up](https://www.promptarmor.com/resources/claude-cowork-exfiltrates-files)) | engines cannot write untracked or send anything (02 decisions 7, section 10); job threads deny bash; ship 02 phase 6 (M6) before marketing to security buyers |
| A competitor copies the open job content | SurfSense's playbooks, mappings or templates ship in another product | Apache-2.0 allows it; the lead rests on the app, the engines and the published eval rows; premium plugins stay under the Business Source License |
| Frontier cost deters users | measured token medians well above these estimates | default to the workflow level where it passes; cheaper columns earn rows |
| The 4B tier fails its own floors | 4B rows below 05 section 7 targets | the free promise narrows to Q&A and the formats that pass; the wording above already allows it |
| macOS cannot ship | notarization failed on 3 Oct 2026 (Apple agreement expired; [04](../../docs/proposals/file-agent/04-runtime-and-packs.md#open-questions)) | Windows and Linux first, the agent included from M5; a notarized macOS build that carries opencode is a macOS release gate; the downloads page says so |
| License holders get nothing | scraper license mode not live when hosted tokens are purged on 18 Oct 2026 (I8 gap 1) | priority support is the license's deliverable until the scraper plugin ships through the license server, so consider extending affected licenses; what else a license includes is revisited after the video and real user feedback (What stays free and what is sold) |

**What would change the order of jobs:** a measured questionnaire engine in
less time than the redline's remaining work, or a lawyer's review that cannot
be had soon. Either moves the questionnaire to ship first.

## Open business questions

Each with a recommended answer.

1. **Does the free promise cover the agent?** Yes. Decide it in the open now,
   because the FAQ is live, 06 already assumes it, and the agent is on in
   installers from M5.
2. **Where do premium plugins live?** Decided: under the Business Source
   License in `surfsense_backend/app/proprietary/`, served by the license
   server to a valid license, with `surfsense_backend` otherwise reduced to the
   license server. Job content is not premium: it is Apache-2.0 and ships in
   the app. Still open: whether a plugin the server has delivered keeps working
   after the license expires. Recommended: yes for the installed version, with
   updates stopping, matching ADR 0019's rule that a license never disables the
   app.
3. **What does a license sell beyond premium plugins, support and
   Enterprise?** Undecided. Revisit it after the video and real user feedback,
   choosing among the candidates above (What stays free and what is sold):
   organization features, bundled frontier model access, or support and
   assurance for regulated buyers. Job content stays free and Apache-2.0
   whichever is chosen.
4. **Is $120 a year the right Individual price for a business tool?** Keep it
   until the paid side is revisited after the video. It is far below every
   vertical tool; raise it on evidence, never by gating free features.
5. **Which job first?** Redline ships first (M6) because its engine exists; the
   questionnaire is the first buyer target and ships free (M7), and its xlsx
   engine work starts right after M1 (above).
6. **Does the lawyer review gate the redline's release or only its marketing?**
   Only its marketing. The redline job is offered on a model once that model's
   eval row passes the job gate; no capability verdict is used to hold it.
   Until the lawyer's review, each starter playbook carries "Starter playbook —
   not reviewed by a lawyer; not legal advice" on the job card, in the issues
   list and in the exported issues file, and a user's own playbook carries no
   label. Public job pages, SEO pages and legal marketing wait for the review.
   The README, 02 and 06 state the same rule.
7. **Must a sandbox exist before selling to security buyers?** No, but two
   things must: job threads with bash denied, and Studio's `exec()` of
   model-written code inside the worker replaced. After the create-and-edit
   slice, Studio's Word and PDF take two paths
   ([07](../../docs/proposals/file-agent/07-create-and-edit-mvp.md#after-the-slice)):
   small models write Markdown that committed builders render, and strong
   models keep writing a script, which runs in SurfSense's script runner, a
   separate process killed at its time limit
   ([ADR 0039](../../docs/adr/0039-document-scripts-run-without-approval.md)).
   PowerPoint and Excel take the same two paths: a script on the runner for
   strong models, and for small models a builder from a flat spec once it
   scores at least the script path's baseline (02 phase B); until then a
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
10. **Is a Team tier needed?** Not yet. In v1 colleagues share through files:
    a playbook, a library folder or a whole workspace exports to a file another
    install imports (M6). Sharing beyond files is out of scope while the app is
    single-user and local. Synced playbooks and a review workflow would be a
    Team tier's content; wait for three Enterprise conversations that ask for
    it.
11. **Should job pages deep-link into the app?** Not in v1: link to downloads
    and the job's setup instructions. A `surfsense://` handler is new attack
    surface ([06, open questions](../../docs/proposals/file-agent/06-product-shape.md#open-questions)).
12. **Should SurfSense speak to Cowork's change on 6 Oct?** Not until the agent
    ships in installers (M5). Pull the keyword data, and write one factual
    comparison page only if demand exists.
