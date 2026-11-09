# ADR 0086: The contract redline ships with the Business switch, as an app runner on SurfSense's own Word engine

- **Status:** Accepted
- **Date:** 2026-11-05
- **Supersedes:** [ADR 0080](0080-surfsense-sells-one-business-license-priced-per-person.md), in part: its order of jobs, which put the contract redline last. The rest of ADR 0080 stands.
- **Source:** maintainer decision, 5 Nov 2026 (no permalink)

## Context

ADR 0080 lists the paid jobs in order, the security questionnaire first and the contract redline against a playbook last, after RFP and RFI responses and the extraction stack. The file-agent proposal gave two reasons for waiting: the redline's planned engine, `docxkit` and `crlib`, needs a clean-room fix before it can ship, and its starter playbooks need a lawyer's review.

On 5 Nov 2026 the maintainer decided to add the contract redline in the Business switch release, beside the questionnaire, and to improve both after release.

Since those plans were written, the app gained its own Word engine, written from ECMA-376 and shipped with revised copies. It writes real tracked changes and comments into a copy of a `.docx`, and it never writes the user's file. The questionnaire set the pattern for paid jobs: its runner lives in the app, and its signed pack holds only data ([ADR 0082](0082-the-license-server-delivers-job-packs-from-private-releases.md)).

## Decision

- **Release.** The contract redline ships in the Business switch release as the second paid job, ahead of RFP and DDQ responses and the extraction stack.
- **What it does.** It reviews one Word (`.docx`) contract against the firm's own playbook: its positions, its standard agreement, or both, chosen from the workspace's sources. It returns a revised copy with tracked changes and comments, and reports each review point as met, changed, not covered by the playbook, or left to a person.
- **No invented positions.** Where the playbook says nothing on a point, the job reports it and leaves the contract alone.
- **Runner in the app.** The runner, `word-clauses/1`, lives in the app under Apache-2.0 and writes through SurfSense's own Word engine. `docxkit` and `crlib` are not used, so their clean-room fix does not apply to the job.
- **Data-only pack.** The pack holds data only: the review points, the prompts and the skill.
- **Names.** The job key is `contract-redline`, in its own pack `surfsense-contract-redline` under the entitlement `JOB_CONTRACT_REDLINE`. The questionnaire's pack is left alone, so a license or an app without the new job keeps getting questionnaire updates.
- **Price.** Business includes it at no extra price, the default of ADR 0080's open question a.
- **v1 scope.** The first turn on one contract, with review points for non-disclosure agreements first.
- **No starter playbook in v1.** A firm without a playbook gets its points reported as not covered. No playbook content ships, so none needs a lawyer's review. Legal marketing still waits for one.
- **Real data only.** It is measured on real contracts with expert labels, against a real published agreement standing in as the firm's playbook.

## Consequences

- The questionnaire and the redline packs are published on the switch day. Every Business license, trial and converted license is issued with both codes, so none needs a backfill of `metadata.jobs`.
- A redline the user directs through the free revise tool stays free. What is paid is the review against a playbook and its report ([ADR 0067](0067-b2b-jobs-ship-as-paid-plugins.md)).
- The engine's limits become the job's limits. It cannot edit headers, footers or footnotes. Every change carries the author "SurfSense". A change whose anchor cannot be placed goes to a person instead of being forced.
- The playbook format, the "Make a playbook" workflow, starter playbooks, replies to a counterparty's markup and the per-model release gate in the file-agent proposal are not part of v1.
