---
status: in-progress
tracking: https://github.com/MODSetter/SurfSense/issues/2414
code:
  - surfsense_local/backend/modules/jobs/
  - surfsense_local/backend/worker/studio/job_run/
  - surfsense_local/backend/scripts/job_eval/
  - surfsense_local/frontend/src/features/jobs/
  - backend/license/jobs.py
---

# The contract redline job

> The second paid job, shipped beside the security questionnaire in the Business switch release ([ADR 0086](../adr/0086-the-contract-redline-ships-with-the-business-switch-on-the-word-engine.md)). A firm adds the counterparty's Word contract and its own playbook to Sources. The job checks each review point against the playbook and returns a revised copy of the contract, with tracked changes and comments.

## What the user sees

1. Add the contract, as a `.docx`, and the firm's playbook to **Sources**. The playbook can be the firm's positions, its own standard agreement, or both.
2. In **Jobs**, choose **Run** beside **Contract redline**, pick the contract, tick the playbook, then **Start**.
3. Progress counts review points. The result is a revised copy in Studio, with tracked changes by "SurfSense", a comment on every change, and the usual **With changes** and **Clean** downloads. The user's file is never written.
4. The Done view reports each point:
   - **changed:** the contract deviated from the playbook, or lacked a term it requires;
   - **meets your playbook;**
   - **not covered by your playbook:** the playbook states no position, so the contract is left alone there;
   - **for a person:** the job could not settle the point, or could not place its change.

Comments come in two kinds:
- **External:** a short reason the counterparty may read.
- **Internal:** SurfSense's reasoning and the playbook quote it rests on. An internal comment never leaves Studio; the downloads leave internal comments out.

## How it works

The runner `word-clauses/1` lives in the app beside `workbook-rows/1` and writes through SurfSense's own Word engine. Like the questionnaire's runner, it is pure over files and a model, so the worker and the eval harness run the same code.

1. **Read the contract with the engine's own reader**, never the ingested Markdown. Every anchor must then pass the engine's quote rules: found exactly once, inside one paragraph, and clear of fields. Each paragraph gets an id, its text, and the list label Word shows (clause numbers are not in the text).
2. **Find the firm's position on each review point** from the playbook sources, with the questionnaire's evidence retrieval (BM25 plus the embedder).
3. **Ask the selected chat model once per point**, under a JSON schema. The answer gives a verdict, the paragraphs it rests on, a playbook quote, the change (replace, insert after or delete, with the exact old text) and the two comments. The contract outline is the shared prefix, so it is cached across points.
4. **Check the answer.**
   - The playbook quote must be found word for word.
   - The old text must be in the named paragraph, matched with curly quotes and dashes folded, then widened until it is unique.
   - The firm's checker model, when one is set, says whether the quoted position supports the change.
   - A change that fails any check goes to a person.
5. **Pre-flight.** The runner applies every change to a scratch copy with the engine's partial mode, so one bad anchor sends one point to a person instead of failing the run. One internal summary comment always applies, so a contract that already meets the playbook still saves a version.

## The runner's contract

- **Entry point.** One pure function with `fill_workbook`'s keyword arguments (`on_row`, `stop`, `embed`, `checker`, `settings`, `take_turns`), so the Studio worker and the eval harness call the same code. The pieces both runners need already sit outside `workbook_rows` on the work's branch (`modules/jobs/asking/`).
- **Config** (`job.json`, loaded by `word_clauses/config.py`, `BAD_JOB_CONFIG` on anything wrong): prompts (system, point, repair, check), review points (key, title, what a position covers, playbook queries, contract hints), verdicts, retrieval settings, `points_per_call`, and the firm settings the job declares.
- **Report:** `runner`, `model`, `checker`, `settings`, `seconds`, `points`, counts by verdict plus `skipped`, one `answers` entry per point (verdict, paragraphs, whether it changed, codes, playbook quote), and `exceptions` as five-item rows. It has no `sheets` and no confirm entries: tracked changes are already proposals.
- **Ops:** only the Word engine's `replace_text`, `insert_paragraphs`, `delete_paragraphs` and `add_comment`, in document order. When two points change one paragraph, the first keeps the change and the second goes to a person.

## The pack

The pack `surfsense-contract-redline` is private, signed and data only. It holds:
- the review points, with their titles, what a position on each covers, and standing queries for the playbook;
- the prompts;
- the skill, which tells the agent to call the job rather than redline by hand.

v1's review points are those of a non-disclosure agreement: what counts as confidential, marking, oral information, purpose, who may receive it, compelled disclosure, publicity, no license, return or destruction, retention, non-solicitation, survival, independent development and similar information. More contract types are more data in the same pack.

## Measuring it on real data

Every case is a real document. Each file's source, licence, retrieval date and sha256 are recorded in the private eval folder, beside the questionnaire's.

- **Contracts:** real NDAs whose clauses experts labelled against fixed statements of position (ContractNLI, CC BY 4.0; CUAD v1, CC BY 4.0, for later contract types), put into a `.docx` container without changing their text. Real standard agreements as published `.docx` files test the engine on real Word structure.
- **The firm's playbook:** a real published standard agreement and playbook: the Bonterms Mutual NDA (CC BY 4.0) with its Playbook of Additional Terms (CC0), the strongest candidate found. The firm's stance on each review point is read from its text by hand, recorded with the clause it rests on, and checked by the maintainer before any number is quoted.
- **Gold:** each (contract, point) pair, from the experts' label and the firm's stance. For example, a point the firm requires that the contract contradicts is a change; one the contract does not mention is a missing term.
- **Scores:**
  - verdict accuracy;
  - precision and recall of the changes a point needs;
  - the located paragraphs against the experts' evidence;
  - how often a blind judge finds that a changed clause now holds the firm's position;
  - integrity: rejecting every change gives back the original text, only SurfSense's changes appear, and the file passes the engine's checks;
  - cost and time.
- **Discipline:** dev and test sets split from the start, and the test set committed before any model runs on it.
- **Models:** Sonnet 5.5 at low effort, Haiku, and Qwen3.8-27B through OpenRouter. Never Opus or Fable.

## Decisions to confirm

- The names in ADR 0086: `contract-redline`, `surfsense-contract-redline`, `JOB_CONTRACT_REDLINE` and `word-clauses/1`. They are permanent once a pack is published.
- NDA points first, with more contract types later as data.
- No starter playbook in v1. A firm without a playbook gets every point reported as not covered.
- Every change and comment is by "SurfSense". A user-set author is not built yet.
- The redline is offered on every model, as the questionnaire is, with its measured rows published. The file-agent proposal's per-model release gate is not built.

## Not in v1

From the file-agent proposal:
- the `playbook/1` format and "Make a playbook from this document";
- starter playbooks;
- replies to a counterparty's markup;
- per-change accept and reject in Studio;
- headers, footers and footnotes;
- a user-set author.
