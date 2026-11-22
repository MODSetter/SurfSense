---
name: surfsense-job-security-questionnaire
description: Fill in a security or due-diligence questionnaire workbook (.xlsx, .xlsm) from the firm's own policies, with a source and quote for every answer. Use when asked to fill in, answer or complete a security questionnaire.
---

# Security questionnaire

1. The user selects the client's questionnaire workbook and the firm's policies. If no workbook is selected, ask for it; if no policy is selected, ask which documents to answer from.
2. Call `surfsense_run_job` with `job` "security-questionnaire", `document_id` the workbook's number, and `source_ids` the policies' numbers. Leave `source_ids` out to use every other selected source.
3. The job answers every question Yes, No, N/A or Needs review from the policies alone and checks every quote against them. It makes a revised copy of the workbook in Studio with the answers in the client's own cells, a "SurfSense answers" sheet with each answer's source and quote, and a "SurfSense exceptions" sheet. Never answer the questions yourself, and never edit the workbook with `surfsense_revise_document`.
4. If the tool says the job is still running, tell the user it will appear in Studio. When it is done, give the counts, name the exceptions that need a person, and say that their own file is unchanged. Some rows left to a person carry a suggested answer with its evidence, such as N/A for a control a provider runs for the firm: say how many, and that once the user has checked them they can ask you to confirm them, which `surfsense_confirm_job_suggestions` does with the run's artifact id. Never confirm them unasked. Say that a person should read every answer before the workbook goes to the client. A small local model (around 9B parameters or fewer) leaves more questions to a person and writes more wrong answers than Claude or a 27B-class model, so on one the Yes answers need the closest look.
