---
name: surfsense-job-contract-redline
description: Review a counterparty's Word contract (.docx), such as an NDA, against the firm's own playbook and redline it with tracked changes and comments. Use when asked to review, check or mark up a contract against the firm's playbook, standard positions or standard agreement.
---

# Contract redline

1. The user selects the counterparty's contract, a Word file (.docx), and the firm's playbook: its standard positions, its own standard agreement, or both. If no contract is selected, ask for it; if no playbook is selected, ask which documents hold the firm's positions.
2. Call `surfsense_run_job` with `job` "contract-redline", `document_id` the contract's number, and `source_ids` the playbook's numbers. Leave `source_ids` out to use every other selected source.
3. The job checks each review point against the playbook alone and checks every playbook quote against it. It makes a revised copy of the contract in Studio with tracked changes by "SurfSense": each change carries a comment the other side may read, and SurfSense's reasoning with the playbook quote it rests on is an internal comment, which stays in Studio. Where the playbook takes no position, the contract is left alone. Never redline the contract yourself with `surfsense_revise_document` for a playbook review, and never invent a position the playbook does not state.
4. If the tool says the job is still running, tell the user it will appear in Studio. When it is done, give the counts, name the points left to a person and why, and say that their own file is unchanged. Say that a person should read every change before the contract goes back to the other side; they can accept or reject the changes in Studio or in Word.
