# Audience pages: the site and the repo after the Business switch

Build sheets for the redo the maintainer asked for on 9 Nov 2026: the homepage,
the nav, pages for lawyers, accountants, students, teachers and healthcare, a
page per paid job, what each licence gets, the plugins page, and the GitHub
repo's description, topics and tagline. The briefs use
[`02-page-briefs.md`](02-page-briefs.md)'s format and rules: titles of at most
60 characters, metas of at most 155, one H1, open with the answer, spell it
"air-gapped". Like every string the site ships today, nothing here uses an em
or en dash.

Page status lives in [`../portal/02-pages.md`](../portal/02-pages.md) and in
the PRs; this file says only what each page should contain.

## Decided on 9 Nov 2026

- Audience pages replace "For business" in the nav. Order: lawyers and
  accountants first, then students and teachers, then healthcare.
- Healthcare copy never says "HIPAA compliant". It says patient data stays on
  the device.
- Student and teacher pages promise only what Studio makes today (below).
- The GitHub description becomes: "Air-gapped, private AI for confidential
  documents. Open-source NotebookLM alternative that runs on your computer."

This reverses one rule of `02`'s cross-cutting page: legal, accounting and
consulting were to be H2s on one page, never vertical pages. The reason that
rule gave, a legal read for every page with compliance-adjacent copy, still
holds; see [Gates](#gates).

## What the numbers say

Pulled 9 Nov 2026, US only:
[`data/keyword-overview-audiences-2026-11.json.gz`](data/keyword-overview-audiences-2026-11.json.gz)
(Google Ads, through Sep 2026) and
[`data/clickstream-audiences-2026-11.json.gz`](data/clickstream-audiences-2026-11.json.gz)
(clickstream, through Oct 2026), beside the September and October clickstream
pulls under `data/b2b/` and `data/b2b-oct/`. Three readings matter more than any
single number.

1. **The privacy heads did not grow tenfold.** Ads has `private ai` at 2,400 in
   May and 165,000 in September; clickstream holds at about 3,000. `08` showed
   in October that this summer step is a change in Google's data for AI-phrased
   terms ([the summer step](08-b2b-artifact-jobs.md#the-summer-step-was-googles-data)).
   For privacy terms, read clickstream: `local llm` 12,769, `local ai` 12,113,
   `private ai` 3,028, `offline ai` 2,220, `self hosted ai` 908,
   `notebooklm alternative` 807, `confidential ai` 452, `private ai chatbot` 354
   (50 a year ago), `open source notebooklm` 302, `private chatgpt` 202,
   `private ai for business` 50. `air gapped ai` is below the panel's floor;
   Ads had it at 210 to 260 before the step. "Air-gapped" stays in the tagline
   because it is true and hard for others to claim, not because it is searched.
2. **Profession terms are Google families.** `ai for lawyers` is 2,400 in Ads
   and 1,312 as the exact phrase, so most of that family is lawyers.
   `ai for accountants` is 6,600 in Ads and about 50 as the exact phrase: the
   Ads record has absorbed accounting-software searches, which want bookkeeping
   automation, not a document tool. The accountant page will draw little search
   traffic. Its job is to be where outreach, trial emails and demos send
   accounting firms.
3. **Study and teaching terms are bigger than the Ads figures say.** Clickstream
   puts AI-tool phrasings two to three times above Ads (`ai flashcard maker`
   9,773 against 3,600, `ai quiz generator` 8,000 against 2,900), which
   [`data/README.md`](data/README.md) warns is usual for AI-tool terms. Take the
   lower figure as the floor. Even at the floor, students and teachers are the
   largest free audience here, and they take the NotebookLM hook best:
   `notebooklm for students` went from 253 to 658 in a year.

Each brief's table gives the Ads volume, KD and CPC from the overview pulls,
and clickstream where it was pulled ("-" where it was not, "<50" below the
floor).

## What Studio makes, which is all these pages may promise

From `surfsense_local/backend/modules/artifacts/formats.py`, with the labels of
`surfsense_local/frontend/src/features/studio/studio-formats.ts`: Markdown, Word,
Slides, Spreadsheet, Web page, PDF, Mind map, Flashcards, Quiz, Podcast, Image
and Infographic. Podcast needs a speech model; Image and Infographic need an
image model; the rest need a chat model. Each output is made from the sources
the user picks and a prompt.

There is no worksheet, lesson plan or study guide format. A worksheet or a
lesson plan is a Word or PDF file made from a prompt. A study guide is the
summary, flashcards and quiz made from one set of sources, as `02`'s study hub
already says. The pages describe them that way.

Before any student or teacher copy ships, make each promised output on the
default local model on a laptop-class machine and with a hosted key, and keep
only what passes. A check of small local models on 8 Nov 2026 found structured
outputs pass while free-form documents and citations fail below 14B. Where a
hosted model does better, the page says so.

## Gates

- **Legal pages wait for a lawyer.** [ADR 0086](../../../docs/adr/0086-the-contract-redline-ships-with-the-business-switch-on-the-word-engine.md)
  keeps "Legal marketing still waits for one", and the
  [file-agent proposal](../../../docs/proposals/file-agent/README.md) holds
  public redline pages, legal SEO pages and legal marketing for that review.
  `/ai-for-lawyers` and `/jobs/contract-redline` are all three. Recommended:
  build both now, behind `NEXT_PUBLIC_BUSINESS_LAUNCHED`; have the lawyer who
  reads the Business terms read them before switch day; record who signed off
  in the PR. Publishing without that read needs a decision that supersedes that
  line of ADR 0086.
- **Compliance-adjacent copy** follows `02`'s compliance-page rule: say only
  where the bytes are, and have it read before publishing. It covers the whole
  healthcare page and any line on the accountant page about what the IRS or the
  FTC Safeguards Rule requires.
- **Job numbers.** Both jobs ship below the 90% bar, by the maintainer's
  decision of 5 Nov 2026. Their pages may publish the measured rows; the
  redline's rows are quoted only after the maintainer has checked the eval's
  stance file.
- **The switch.** Everything that names a paid job, the Business price or the
  trial ships behind the switch flag, as the pricing pages already do. The
  student and teacher pages name no job and can ship at any time.

## The nav

Today: For business, Plugins, Docs, Pricing. After the switch:

| entry | goes to |
|---|---|
| Who it's for (menu) | Lawyers `/ai-for-lawyers`, Accountants `/ai-for-accountants`, Students `/ai-for-students`, Teachers `/ai-for-teachers`, Healthcare `/private-ai-for-healthcare`, Other professional work `/private-ai-for-business`. An item appears once its page is live. |
| Jobs (menu) | Contract redline `/jobs/contract-redline`, Security questionnaire `/jobs/security-questionnaire` |
| Docs | `/docs` |
| Pricing | `/pricing` |
| Resources (menu) | Blog, Announcements, Changelog, Plugins, Contact us |

- **Plugins** moves from the bar into the Resources menu. After the switch,
  `first-party-plugins.json` is empty, so the page shows the three built-in
  sources and third-party plugins: too little for the top bar.
- **The footer** gains a "For firms" column with the audience and job pages,
  each anchored with its keyword ("AI for lawyers").
- **`/private-ai-for-business` stays**, as the page for consultants and other
  professions. Its legal and accounting cards link the new pages, and the header
  comment in its `page.tsx` that forbade vertical pages now points here.
- Built in `features/site-navigation/site-navigation.ts`, a function of the
  switch, with tests for both sites and for every link leading to a page.

## `/` homepage

`02` already says this page is not measured on head terms: it converts traffic
from the repo, launches and brand search. What changes is the message, not the
layout.

| role | keyword | Ads | clickstream | kd |
|---|---|---|---|---|
| primary | private ai | summer step | 3,028 | 14 |
| primary | local ai | summer step | 12,113 | 27 |
| secondary | offline ai | 1,600 | 2,220 | 7 |
| secondary | self hosted ai | summer step | 908 | 12 |
| secondary | notebooklm alternative | 590 | 807 | - |
| secondary | private ai chatbot | - | 354 | - |
| tertiary | air gapped ai | 210-260 before the step | <50 | - |
| must keep | surfsense | brand, position 1 | | |

- **Title:** `Air-Gapped Private AI for Confidential Documents | SurfSense` (60)
- **Meta:** `SurfSense is free, open-source private AI that runs on your computer: a NotebookLM-style notebook for files you can't upload. No account, works offline.` (152)
- **H1:** `Air-gapped private AI for confidential documents`. The brand stays in
  the title tag and the wordmark, as today; the H1 has not carried it since
  October. The line under it carries the familiar hook: "A NotebookLM-style
  notebook that runs entirely on your own computer."
- **New band after the logos, "Who it's for":** a card per audience with one
  line and a keyword link. It is the internal-link hub for the new pages; it
  shows once Business is on sale, and a card joins once its page is live.
- **"Jobs for firms"** is a strip under the audience cards, behind the switch:
  one sentence from the user guide and a link to each job's page.
- **"Open source, extended by plugins"** becomes "Open source, with web search
  built in": the plugins it describes retire at the switch.
- **Keep** the privacy sections, the formats section, the FAQ and its schema.
  The FAQ already answers three NotebookLM questions, so it gains none.
- **Must survive:** the URL, the brand in title and H1, `SoftwareApplication`
  with price 0.

## `/ai-for-lawyers`

| role | keyword | Ads | clickstream | kd | cpc |
|---|---|---|---|---|---|
| primary | ai for lawyers | 2,400 | 1,312 | 30 | 55.59 |
| primary | legal ai tools | 1,600 | 1,312 | 24 | 82.20 |
| secondary | legal ai | 18,100 | 7,390 | 38 | 31.62 |
| secondary | chatgpt for lawyers | 480 | 403 | **1** | 43.33 |
| secondary | ai for law firms | 1,900 | 252 | 18 | 33.87 |
| link out | ai contract review | 880 | 1,261 | 19 | 97.49 |

- **Title:** `AI for Lawyers: Private Legal AI That Runs on Your Computer` (59)
- **Meta:** `Free, open-source legal AI that keeps client files on your computer. Search a matter, draft memos and decks, and redline contracts against your playbook.` (153)
- **H1:** `Private AI for lawyers: client files never leave your computer`
- **First paragraph, the answer:** SurfSense is a free, open-source AI app a
  lawyer runs on their own computer. It indexes a matter's documents on that
  disk, answers questions with a citation for each answer, and makes memos,
  chronologies and decks from them. With a local model nothing is sent
  anywhere; with the firm's own key, only the passages a question needs go to
  the provider the firm chose. There is no SurfSense account and no vendor copy.
- **H2s:**
  1. *Can lawyers use AI with client documents?* Where the bytes are: the
     index, the chats and the outputs on disk, no vendor log. What reaches a
     hosted provider when the firm picks one, and that a local model sends
     nothing. The professional-conduct conclusion is the reader's: link ABA
     Formal Opinion 512, do not paraphrase what it requires. This H2 carries
     `chatgpt for lawyers` (KD 1).
  2. *Ask across a matter, with a citation for every answer* (the free app).
  3. *Turn a case file into a memo, a chronology or a deck* (Word, PDF,
     Spreadsheet and Slides from the matter's sources).
  4. *Review a contract against your firm's playbook* (the contract redline in
     two short paragraphs, linking its page; behind the switch).
  5. *Use the model your firm approves* (a local model, or the firm's own key
     for a provider it has a contract with).
  6. *Free for every lawyer; Business adds the jobs* (Free and Business in
     three lines, linking `/pricing`).
- **FAQ** (also `FAQPage`): *Does SurfSense give legal advice?* (No: it works
  from your documents and your playbook, and a person decides.) *Does it work
  offline?* *Where are my client files stored?* *What does the contract redline
  cost?* (Business, $60 a person a year, with a 14-day trial.)
- **Schema:** `SoftwareApplication` (price 0) and `FAQPage`.
- **Links out:** `/jobs/contract-redline`, `/pricing`, `/downloads`,
  `/private-ai-for-business`, the docs page on jobs.
- **Must not:** "privileged", "ABA compliant", "secure" as a bare claim, any
  accuracy figure before the stance check, a named legal AI vendor. ChatGPT is
  named once, in the FAQ that answers `chatgpt for lawyers`, with facts only.
- **Gate:** the lawyer's read.

## `/jobs/contract-redline`

| role | keyword | Ads | clickstream | kd | cpc |
|---|---|---|---|---|---|
| primary | ai contract review | 880 | 1,261 | 19 | 97.49 |
| primary | contract review ai | 880 | 251 | 19 | 97.49 |
| secondary | contract redlining software | 210 | 50 | - | **380.91** |
| secondary | ai redlining | 40 | 50 | - | - |
| tertiary | ai legal document review | 90 | 50 | 14 | 49.05 |
| below the floor | nda review, ai nda review, contract redlining | - | <50 | - | - |

- **Title:** `AI Contract Review Against Your Own Playbook | SurfSense` (56)
- **Meta:** `SurfSense reviews a Word contract against your firm's playbook and returns tracked changes and comments, on your own computer. 14-day free trial.` (145)
- **H1:** `AI contract review against your own playbook, as tracked changes in Word`
- **First paragraph:** what it does, in the pricing copy's sentence, then the
  rule that sets it apart: it never invents a position. Where the playbook says
  nothing, the job says so and leaves the clause alone.
- **H2s:**
  1. *What you get back:* a revised copy with tracked changes by "SurfSense", a
     comment on each change, the With changes and Clean downloads, and an
     outcome per review point (changed, meets your playbook, not covered by your
     playbook, for a person).
  2. *What your playbook can be:* your positions, your own standard agreement,
     or both, chosen from Sources.
  3. *What it reviews:* the non-disclosure agreement's review points, listed as
     the [proposal](../../../docs/proposals/contract-redline-job.md) has them.
  4. *Your contract never leaves your computer.*
  5. *What it does not do yet:* headers, footers and footnotes; replies to a
     counterparty's markup; contracts that are not `.docx`.
  6. *How well it does:* the measured rows by model, once the stance check is
     done. Until then, no numbers.
  7. *Price and trial.*
- **Labels:** quote the app exactly as
  `surfsense_local/frontend/translations/en.json` has it.
- **Schema:** `SoftwareApplication` with the Business `Offer`, and `FAQPage`.
- **Links:** `/ai-for-lawyers`, `/pricing`, `/downloads`, the docs page on jobs.
- **Gate:** the lawyer's read, and the switch.

## `/ai-for-accountants`

| role | keyword | Ads | clickstream | kd | cpc |
|---|---|---|---|---|---|
| primary | ai for accountants | 6,600 (a family) | about 50 | 29 | 36.40 |
| secondary | ai for accounting firms | 110 (480 in Aug) | 50-100 | 28 | 60.11 |
| secondary | ai for bookkeepers | 170 | 50 | 28 | 35.91 |
| secondary | ai for audit | 170 | - | 8 | 30.06 |
| secondary | ai for cpa | 90 | 50 | 27 | 49.33 |
| secondary | ai for tax preparers | 70 | <50 | 26 | 48.84 |
| candidate | written information security plan | - | 253 | - | - |
| candidate | wisp template | - | 101 | - | - |

- **Title:** `AI for Accountants: Private AI for Client Financial Files` (57)
- **Meta:** `Free, open-source AI for accountants that keeps client files on your computer. Draft reports, pull figures and answer security questionnaires.` (142)
- **H1:** `Private AI for accountants: client files stay on your computer`
- **First paragraph:** free and open source; returns, statements, ledgers and
  engagement letters go into an index on the accountant's own disk; ask
  questions, summarise, build reports and spreadsheets; and, for a firm whose
  clients send security questionnaires, the job that answers them.
- **H2s:**
  1. *Client financial files stay on your machine* (where the bytes are).
  2. *Pull figures from statements into a spreadsheet* (Spreadsheet from the
     sources). Make one from a real scanned statement before the copy says it.
  3. *Client-ready reports, letters and decks* (Word, PDF, Slides).
  4. *Answer a client's security questionnaire from your own policies* (the
     job, linking its page; behind the switch). Its evidence is the security
     plan many firms already keep, which is where the WISP candidates belong;
     any line on what a regulator requires goes through the compliance read.
  5. *Use the model your firm chooses.*
- **FAQ:** *Does SurfSense connect to QuickBooks or Xero?* (No: it reads the
  files you add. List the source types from the app before publishing.) *Is it
  free for a firm?* (The app is; Business adds the jobs.) *Is client data
  uploaded?* (No, with a local model; with a hosted model, only the passages a
  question needs.)
- **Schema, links, must-nots:** as for lawyers; links to
  `/jobs/security-questionnaire`.

## `/jobs/security-questionnaire`

| role | keyword | Ads | clickstream | kd | cpc |
|---|---|---|---|---|---|
| primary | security questionnaire | - | 150 | - | - |
| secondary | security questionnaire automation | 70 | 50 | 11 | **227.98** |
| secondary | vendor security questionnaire | 40 | <50 | - | 106.82 |
| later, own pages | hecvat, caiq, sig lite | see `08` | | | |
| skip | due diligence questionnaire | 2,400 | 252 | - | 33.06 |

`08` already skips the generic DDQ head: most of its searchers mean investment
due diligence.

- **Title:** `Answer Security Questionnaires From Your Own Policies` (53)
- **Meta:** `SurfSense fills a customer's security questionnaire in their own spreadsheet from your firm's policies, cites each answer and flags what needs a person.` (152)
- **H1:** `Answer a security questionnaire in the customer's own spreadsheet, from your own policies`
- **H2s:** *What you get back* (the filled workbook, the source of each answer,
  the list for a person to review) · *What it reads* (your policies, from
  Sources) · *Which questionnaires* (any Excel workbook; the HECVAT, CAIQ and
  SIG Lite pages follow `08`) · *Nothing leaves your computer* · *How well it
  does* (the measured rows, as the eval publishes them) · *Price and trial*.
- **Links:** `/ai-for-accountants`, `/pricing`, `/downloads`.
- **Gate:** the switch.

## `/pricing`: what each licence gets

The switch copy is written: `business-pricing-content.ts` has Free, Business
($60 a person a year, a 14-day trial, up to 15 people self-serve) and
Enterprise, and twelve questions. Three changes:

1. **Free's card says what Studio makes.** Add "Studio: flashcards, quizzes,
   mind maps, slides, podcasts, and Word, PDF and spreadsheet files". It is the
   reason students and teachers download, and the card does not mention Studio
   today.
2. **A table under the cards, "What each licence gets".** Rows: the app and its
   updates; local models and your own keys; web search, YouTube and web pages;
   Studio; the security questionnaire; the contract redline; priority support;
   the feature build request; people covered; licensing inside your own
   network; a data processing agreement and a code audit; support terms.
   Columns: Free, Business, Enterprise. The cards' facts, in one quotable place.
3. **One question.** *Is SurfSense free for students and teachers?* Yes: the
   whole app is free for everyone, and a licence is needed only for the job
   plugins at work. The firm's version of the question is already answered by
   *Who needs a Business licence?*

The title stays `SurfSense Pricing: Free App, Business Licence`.

## `/plugins`

- Leaves the main nav, as above.
- Keeps its URL and its switch title, `SurfSense Plugins: Web Search, YouTube and Web Crawl Built In`.
- Gains one line that sends readers looking for the paid jobs to their pages.

## `/ai-for-students` (round two)

| role | keyword | Ads | clickstream | kd | cpc |
|---|---|---|---|---|---|
| primary | ai for students | 1,000 | 1,924 | 23 | 7.08 |
| primary | free ai for students | 720 | 2,734 | 36 | 7.80 |
| primary | ai study tool | 6,600 | 2,380 | 33 | 5.70 |
| secondary | study guide maker | 6,600 | 7,292 | 29 | 4.98 |
| secondary | ai flashcard maker | 3,600 | 9,773 | 33 | 2.73 |
| secondary | ai quiz generator | 2,900 | 8,000 | 43 | 4.57 |
| secondary | ai podcast generator | 4,400 | 10,229 | 13 | 4.95 |
| secondary | notebooklm for students | - | 658 | - | - |
| tertiary | pdf to quiz | - | 1,569 | - | - |
| tertiary | ai mind map generator | - | 1,367 | - | - |
| tertiary | pdf to flashcards | - | 1,114 | - | - |
| tertiary | quiz generator from pdf | 140 | 455 | 14 | 4.33 |
| skip | ai tutor | 6,600 | 7,393 | 37 | 9.82 |
| skip | ai presentation maker | - | 46,638 | - | - |

SurfSense is not a tutor, and the presentation-maker market belongs to `02`'s
later slides page.

- **Title:** `Free AI for Students: Flashcards, Quizzes and Study Guides` (58)
- **Meta:** `Turn your notes and PDFs into flashcards, quizzes, mind maps and podcasts, free and on your own laptop. A NotebookLM-style notebook with no account.` (148)
- **H1:** `Free AI for students: turn your notes and PDFs into flashcards, quizzes and study guides`
- **First paragraph:** `02`'s argument for every study page: free, on your
  laptop, and your files never leave it. Then what goes in (lecture slides,
  PDFs, notes, YouTube lectures) and what comes out.
- **H2s,** in order of demand:
  1. *Flashcards from your notes and PDFs*
  2. *Practice quizzes from your readings*
  3. *A study guide: a summary, flashcards and a quiz from one set of sources*
  4. *Turn a chapter into a podcast to listen to* (say which speech model)
  5. *Mind maps of a topic*
  6. *Slides for a class presentation*
  7. *Like NotebookLM, on your own laptop* (facts only)
  8. *What you need to run it* (the computer and model, honestly: what works on
     a laptop's local model and what needs a key)
  9. *Revision flashcards and quizzes* (the UK word, as `02` asks)
- **FAQ:** *Is SurfSense free for students?* *Does it work without internet?*
  *Can it read my lecture slides?* *Are my files uploaded?* *Is it the same as
  NotebookLM?*
- **Links:** `/downloads`, `/free`, `/ai-for-teachers`, and later `02`'s study
  hub, flashcards, quiz and podcast pages.
- **Verify before publishing:** every H2's output on the default local model
  and with a hosted key; slides and YouTube as sources; the podcast offline.

## `/ai-for-teachers` (round two)

| role | keyword | Ads | clickstream | kd | cpc |
|---|---|---|---|---|---|
| primary | ai for teachers | 3,600 | 4,542 | 32 | 5.15 |
| primary | ai worksheet generator | 880 | 1,316 | **1** | 6.18 |
| primary | ai lesson plan generator | 880 | 1,211 | **3** | 5.30 |
| secondary | free ai for teachers | 390 | 911 | 60 | 6.68 |
| secondary | ai tools for teachers | 1,600 | 759 | 36 | 5.96 |
| secondary | ai quiz maker | - | 7,393 | - | - |
| secondary | quiz generator from pdf | 140 | 455 | 14 | 4.33 |
| tertiary | notebooklm for teachers | - | 151 | - | - |

- **Title:** `Free AI for Teachers: Quizzes, Worksheets and Lesson Plans` (58)
- **Meta:** `Make quizzes, worksheets, lesson plans and slides from your own teaching materials, free and on your computer. Student work never leaves your machine.` (150)
- **H1:** `Free AI for teachers: quizzes, worksheets and lesson plans from your own materials`
- **First paragraph:** free and on the teacher's own computer; made from their
  syllabus, readings and slides; student work they add is never uploaded.
- **H2s:**
  1. *A quiz from your own materials* (Quiz in the app, or a printable quiz with
     an answer key as a Word or PDF file)
  2. *Worksheets as Word or PDF files*
  3. *Lesson plans from your syllabus* (Word)
  4. *Slides for tomorrow's class*
  5. *Flashcards and a podcast recap for your students*
  6. *Student work stays on your computer* (where the bytes are; no FERPA claim)
  7. *Free, with no account and no school sign-up*
- **FAQ:** *Is it free for teachers?* *Can I print the quiz?* *Is student work
  uploaded?* *Does it run on a school computer?* (answer only after checking
  an install without admin rights on each OS)
- **Links:** `/ai-for-students`, `/downloads`, `/pricing`.
- **Verify before publishing:** a printable quiz with an answer key, a
  worksheet and a lesson plan, on a local model and with a hosted key.

## `/private-ai-for-healthcare` (round three)

| role | keyword | Ads | clickstream | kd | cpc |
|---|---|---|---|---|---|
| primary | hipaa compliant ai | 4,400 | 754 | 34 | 46.33 |
| primary | ai for doctors | 720 | 706 | 43 | 6.70 |
| secondary | ai for healthcare | 14,800 | 504 | 44 | 12.68 |
| secondary | hipaa compliant chatgpt | 390 | 151 | - | 63.56 |
| secondary | hipaa compliant ai tools | 390 | 100 | 34 | 35.49 |
| tertiary | ai for therapists | 390 | 50 | 30 | 20.60 |
| tertiary | ai for nurses | 210 | 50 | 21 | 11.07 |

- **Title:** `Private AI for Healthcare: Patient Data Stays on Your Device` (60)
- **Meta:** `Free, open-source AI that runs on your own computer, so patient records are never uploaded. Summarise records, draft letters and search notes offline.` (150)
- **H1:** `Private AI for healthcare: patient records stay on your computer`
- **The rule:** the page never says "HIPAA compliant". It states where the bytes
  are, and that with a local model no patient data reaches any AI vendor, and
  lets the reader draw the conclusion. It earns `hipaa compliant ai` by
  answering the question searchers ask with those facts. The compliance read
  comes before publishing.
- **H2s:** *Is there a HIPAA compliant AI?* (the facts; compliance comes from the
  practice's own controls) · *Summarise records and referral letters* ·
  *Search across notes and guidelines* · *Paperwork, not diagnosis* (clinical
  decisions are out of scope) · *For therapists and small practices*.
- **Must not:** clinical claims, "HIPAA compliant", any promise of a business
  associate agreement.

## The GitHub repo

- **Description** (decided): `Air-gapped, private AI for confidential documents. Open-source NotebookLM alternative that runs on your computer.`
  (113 characters). The Discord link stays after it, as today. "Open-source
  NotebookLM alternative" moves to the second sentence; GitHub ranks first for
  `open source notebooklm` and `local notebooklm` on the old wording, so re-pull
  the repo's rankings four weeks after the change.
- **Topics,** 20 in place of today's nine: `06`'s sixteen (`notebooklm`,
  `notebooklm-alternative`, `notebooklm-mcp`, `rag`, `local-llm`, `self-hosted`,
  `self-hosted-ai`, `air-gapped`, `offline`, `local-first`, `privacy`,
  `private-ai`, `mcp`, `mcp-server`, `electron`, `ollama`) plus `local-ai`,
  `legal-ai`, `flashcards` and `document-ai`. Dropped: `ai`, `agent`, `agents`,
  and `web-scraping`, whose scrapers retire at the switch.
- **README:** the bold tagline under the header becomes "Air-gapped, private AI
  for confidential documents." and the banner's alt text follows it. The first
  paragraph already says "documents you can't upload" and "NotebookLM-style",
  so it stays. Make the same change in all ten `README.<locale>.md` files, in
  each locale's words (`06`). The README names no job.
- The description and topics live in the repo's settings, not in a file, so no
  PR carries them (`06`'s checklist). They change when the maintainer says so.

## Every page

- Title, meta and H1 as above; H2s that are questions searchers ask or jobs
  they do; an opening paragraph that answers the query in plain sentences.
- `SoftwareApplication` (price 0) on the audience pages, `FAQPage` wherever there
  is an FAQ, a canonical URL, Open Graph and Twitter tags as
  `/private-ai-for-business` sets them, `hreflang` `en` and `x-default` (`02`),
  and a sitemap entry.
- Each audience page links `/downloads`, `/pricing`, its job page and one
  sibling page; the homepage links all of them.
- Server components with no client JavaScript, in the homepage's shapes, as
  `/private-ai-for-business` is built.
- App labels quoted exactly as `en.json` has them, and no claim the app cannot
  show today.

## Order

1. **With the switch release:** the nav, the homepage, `/ai-for-lawyers` and
   `/jobs/contract-redline` (after the lawyer's read), `/ai-for-accountants`,
   `/jobs/security-questionnaire`, the `/pricing` changes, `/plugins` out of the
   nav, `/private-ai-for-business` relinked. The GitHub description and topics
   whenever the maintainer says.
2. **Indexed by early January,** ahead of the March and April study peak
   (`02`): `/ai-for-students` and `/ai-for-teachers`, then `02`'s study hub,
   flashcards, quiz and podcast pages.
3. **After the compliance read:** `/private-ai-for-healthcare`.
4. **Four to six weeks after each round:** re-pull `ranked_keywords` for
   surfsense.com and the repo, one call each.

## Not in this round

- **A NotebookLM comparison page.** The family is worth having
  (`notebooklm alternative` 807, `notebooklm for students` 658,
  `open source notebooklm` 302) and the homepage title no longer carries it. It
  is the first candidate for round two.
- **Pages per questionnaire** (HECVAT, CAIQ, SIG Lite): `08`'s plan, after the
  job's own page.
- **Localised pages:** `03`.
