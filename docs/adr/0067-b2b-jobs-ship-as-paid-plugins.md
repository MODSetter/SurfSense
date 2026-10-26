# ADR 0067: SurfSense's B2B jobs ship as paid plugins that run on the user's machine and unlock with a SurfSense license

- **Status:** Accepted
- **Date:** 2026-10-22
- **Supersedes:** [ADR 0047](0047-premium-plugins-are-source-available.md) in part: "all job content, and job packs" staying Apache-2.0, for SurfSense's B2B jobs
- **Source:** [08-b2b-artifact-jobs L493–556](https://github.com/MODSetter/SurfSense/blob/9c59b84affccfdcdd9c6c0c20a5f79d02b7f8d8b/plans/community-local/seo/08-b2b-artifact-jobs.md#L493-L556), [ADR 0047 L20](https://github.com/MODSetter/SurfSense/blob/9c59b84affccfdcdd9c6c0c20a5f79d02b7f8d8b/docs/adr/0047-premium-plugins-are-source-available.md#L20), [02 decision 17](https://github.com/MODSetter/SurfSense/blob/9c59b84affccfdcdd9c6c0c20a5f79d02b7f8d8b/docs/proposals/file-agent/02-skills-and-engines.md#L134), maintainer decision, 22 Oct 2026 (no permalink)

## Context

With every job and its content free, the October research found nothing a business would pay SurfSense for in any job: each revenue test came back weak, and the paid side was left to wrappers (a team library, assurance, data plugins). The same businesses already pay for the jobs themselves: self-serve questionnaire tools at $50–249 a month, Loopio at about $24K a year, statement converters at $20–280 a month, chronology services per page ([08](../../plans/community-local/seo/08-b2b-artifact-jobs.md#the-bets)).

SurfSense reaches people through organic search, user posts and creators. Those channels carry general, shareable work: decks and reports from files, converters, OCR, transcription, a local alternative to Claude Cowork. The B2B jobs run on confidential files nobody posts. So the free product distributes and the B2B jobs earn.

The public promise fits a plugin. The pricing FAQ says everything "the app itself" does stays free and that the license "does not lock any of the app's own features" ([`pricing-content.ts`](../../www/app/(home)/pricing/pricing-content.ts)), and the license gates plugins and priority support only ([ADR 0019](0019-offline-licenses.md)).

## Decision

- **SurfSense's B2B jobs are paid plugins.** That covers the security questionnaire, RFP, RFI and DDQ responses, the contract redline (review against a playbook), bank statements into a ledger, medical chronologies, contract and lease registers, and B2B jobs added later. Each is a `paid` bundle: it installs and runs only with an unexpired SurfSense license (Individual, Team, or the 14-day trial for its term), as the [bundles design](../proposals/plugins/bundles/README.md) defines `access: paid`. It runs on the user's machine and is delivered by the license server only to a valid license, never in the installer or the public plugin list ([ADR 0047](0047-premium-plugins-are-source-available.md)).
- **A job plugin carries the job:** its skill and agent, its workflow steps, its mappings (questionnaire layouts and scoping logic), its playbooks and starter playbooks, its templates, and its eval cases and gold corpora. For the contract redline that includes `crlib`, `review.py`, `playbook.py` and the starter playbooks.
- **The app keeps everything else, free under Apache-2.0:** Q&A, Studio, the general agent and its format skills, every engine (Word revisions as tracked changes, Excel and PowerPoint revisions, PDF tools, OCR, speech-to-text, data analysis; `docxkit` once it ships), the study pack, the capability jobs (conversion, comparison, transcription, redaction and organizing, as they are built), and the job infrastructure every job uses: the job catalogue and its entry points, the eval harness, the row-by-row runner, per-answer sources and checks, per-row review, page citations, the tie-out validator, the answer library with its import and export, the assurance basics, the bundle runtime, and the `library` and `playbook` folder roles. A playbook imported without the redline plugin is kept as the user's files; the plugin validates it when it runs.
- **The line falls between an edit and a job.** A user who asks the general agent to change their own file, a contract included, still gets a free revised copy with tracked changes. What is paid is the job: the playbook, the review against it and the issues list; a questionnaire's mappings and answer matching. The checks and the exceptions list they produce are shared infrastructure.
- **The user's data is never locked.** Libraries, the user's own playbooks, outputs and revised copies are files that open and export without a license. When a license lapses the job plugin stops, and the app and the user's files keep working (ADR 0019).
- **Eval results stay public.** Every paid job's eval rows are published with their failures, and no page names a model as able to do a job unless a committed row says so.
- **Other publishers' job packs** are free or charge on their own service, and never use the SurfSense license (ADR 0047).

## Consequences

- No paid job ships before local paid bundles and the job-pack loader (02 phase 8, `provides.skills`) exist. Both were deferred and now sit on the questionnaire's path.
- A paid job's content is written outside the Apache-2.0 tree from its first commit, in a folder with its own license file, as `backend/plugins/proprietary/` has today. Nothing a plugin sells is committed to `surfsense_local/`.
- **Enforcement is delivery and terms, not the check in the app.** A check on the user's machine can be stripped by any fork (ADR 0019). What holds is that the license server serves a job plugin and its updates only to a valid license, plus the plugin's license terms. The Business Source License in [`backend/plugins/proprietary/LICENSE`](../../backend/plugins/proprietary/LICENSE) grants production use to anyone who does not resell the work. That is enough for code that runs on SurfSense's server, but it would let a business run a local job plugin without a license. The terms for local job plugins are decided with the lawyer before the first one ships: a Business Source License with a narrower Additional Use Grant, or a closed license.
- The free promise on `/pricing` still holds, but one FAQ line, "A paid licence is only needed for the scraper plugins and priority support", becomes untrue when the first job plugin ships. That page, the README's plugin section and the Terms change in that release.
- The clean-room fix and the provenance review still apply to `docxkit` and `crlib`: paid code must be the maintainer's own as much as free code.
- 02 decision 17, the file-agent README's "What stays free and what is sold", 06's free and premium section, 08 and the business strategy change with this record.

## Where the code stands

- No job plugin exists. Bundles are deferred; their runner ([`modules/plugins/bundles/runner/`](../../surfsense_local/backend/modules/plugins/bundles/runner/)), SDK and author CLI ([`backend/plugins/bundles/core/`](../../backend/plugins/bundles/core/)) are partly built. The job-pack loader and the license server's route for paid bundles are not built.
- What the free agent does today stays free: the [`surfsense-revisions`](../../surfsense_local/backend/modules/agent/skills/surfsense-revisions/SKILL.md) skill and `surfsense_revise_document` redline the user's own Word file on request, as tracked changes and comments. Live case 9 ([`test_contract_redline.py`](../../surfsense_local/backend/tests/live/test_contract_redline.py)) exercises that on a contract. The skill's examples name contracts and redlining, so a follow-up rewords them, and renames the case, so the free skill does not present contract review as a feature.
- No playbook review, starter playbook or issues list is in the repository: `docxkit` and `crlib` live only in the git-ignored skills project.
