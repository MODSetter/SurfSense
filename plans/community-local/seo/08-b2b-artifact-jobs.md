# B2B artifact jobs: what the agent should be best at

Which business jobs an agent that creates and edits artifacts should be built
and sold for. Demand is sized from Google, then checked three ways: against
clickstream, against what vendors in each job rank for, and against
practitioners describing the work. It feeds the agent work in
[`docs/proposals/agent/`](../../../docs/proposals/agent/README.md) and the
page plan in [`02-page-briefs.md`](02-page-briefs.md).

**Source:** DataForSEO, pulled **29 Sep 2026**, Google US (`location_code:
2840`, `language_code: en`). 1,511 terms with data, 376 of them also measured
in clickstream, and the top 200 non-brand keywords of 15 vendors. Archived in
[`data/b2b/`](data/b2b/), mapped in
[`data/b2b/use-cases.json`](data/b2b/use-cases.json) and rolled up by
[`data/b2b/rollup.py`](data/b2b/rollup.py). Every figure below is its output
unless the text names another file.

## The headline

Three jobs, in this order. In each one a confidential file goes in and the
customer's own format has to come out.

1. **Security questionnaires and compliance documents.** Fill the customer's
   questionnaire (HECVAT, CAIQ, SIG, PCI SAQ or their own spreadsheet) from the
   company's policies and past answers, and draft the SOC 2 and ISO 27001
   documents those answers point to. The largest job demand of any play:
   **$701K of ad value a month at $23.58 a click**, and the security
   questionnaire case is growing (+12%).
2. **Legal.** Review and redline a contract against the firm's playbook, draft
   clauses, and build the personal-injury demand package: medical chronology,
   records summary, demand letter. **$584K a month at $11.49**, the highest
   profession CPC in the research ($56.65), and the largest steady
   exact-phrase demand of any profession: `ai for lawyers`, about 1,300 a
   month in clickstream all year.
3. **Proposals.** Answer an RFP or a government solicitation from past
   proposals, into its own compliance matrix and response template. **$398K a
   month at $9.57**, and another $336K bid on proposal, CPQ and procurement
   software.

**The edit is the product, delivered as a revised copy.** The high-value
version of every job above edits a file the user did not write: the
customer's questionnaire, the counterparty's contract, the agency's response
template. The accepted agent proposal already fits this. The agent writes
only into its own output folder and never edits the user's files
([README](../../../docs/proposals/agent/README.md)), so a filled
questionnaire or a tracked-changes redline is a new file beside the original.
In-place editing and undo are not needed for any of the three.

**Excel, Word and PowerPoint editing are capabilities, not a play.** They are
the only group growing (+19%, the Excel agent +82%), but the searches name
the incumbents: `claude for excel` 6,600, `copilot in excel` 2,900, `powerpoint
ai` 2,900. Build them because every job above needs them. Do not sell them as
the product, because Claude and Copilot already live inside the apps.

**Local is why a buyer would pick SurfSense for all three.** Security
evidence is shared under NDA, legal work is privileged, and government
proposals carry CUI and ITAR data that practitioners say they keep out of
hosted models. The same argument covers the second wave: client tax data and
patient records.

## How this was counted

**Three kinds of term.** Every term is sorted by its wording before it is
summed, because the three kinds measure different things:

| kind | rule | what it measures |
|---|---|---|
| job | everything that is not the other two: `nda template`, `ai contract review`, `hecvat` | someone who has to produce the artifact now |
| software | ends in `software`, `platform`, `system`, `app`, `tool` or `solution`, plus a short override list | a budget: what vendors pay to reach a buyer |
| profession | `ai for <profession>` and its variants, and `legal ai` | a family of searches, reported per play |

Use cases are ranked on job terms only. Software is reported as a budget
signal beside them, and profession terms are grouped into plays.

**Ad value** is Σ(`recent` × CPC) a month, where `recent` is the median of
the last three months capped at the 12-month average, as elsewhere in this
folder. It ranks use cases. It is not revenue.

**Clickstream catches merged Google Ads records.** Google Ads volumes come
from keyword-planner records that can absorb searches for other phrases.
Clickstream counts the exact phrase from a browsing panel. Across the 307
non-profession terms measured both ways, the median Ads volume is 1.34 times
clickstream. A non-profession term at ten times or more has absorbed
something else, so it is rescaled to its clickstream figure times 1.34.
Examples: `regulatory impact assessment` 135,000 is counted as 203, `system
security plan` 22,200 as 474, and `rfi in construction` 3,600 as 270.
`ai for <profession>` records are families by design (`ai for law firms` is
about ten times its exact phrase), so the rule skips them. That is why
profession volumes are reported separately and not summed with jobs.

**Eighteen terms are excluded by judgment**, each with its reason in
`use-cases.json`. The main groups:

- the wrong reader: `cost segregation study` (owners buying a study),
  `letter of explanation` (borrowers), `financial affidavit` (the parties to a
  case);
- a different meaning: `credit memo` (mostly the accounting credit note),
  `board book` (children's books), `ai quote generator` (sayings);
- a brand: `think cell`.

**Trend** compares January–May 2026 with September–December 2025, each term
capped at three times its median. June to August are left out (next section).

## The summer step is in Google Ads, not in searches

Google Ads shows a step up from June to August 2026 across unrelated AI
terms. Clickstream for the same phrases does not:

| term | Google Ads, May → Aug 2026 | clickstream, May → Aug 2026 |
|---|---|---|
| private ai | 2,400 → 60,500 | 3,078 → 3,028 |
| private llm | 880 → 18,100 | 1,362 → 1,514 |
| self hosted ai | 1,000 → 14,800 | 757 → 908 |
| private ai for business | 50 → 12,100 | 50 → 50 |
| legal ai software | 720 → 3,600 | 706 → 555 |
| ai for law firms | 1,600 → 2,400 | 302 → 252 |
| ai for hospitals | 50 → 1,600 | 50 all year |
| local ai | 5,400 → 12,100 | 10,296 → 12,113 |

The Ads series for the privacy terms are the 14 Sep pulls (`data/`); the
clickstream series are the 29 Sep pulls (`data/b2b/`). `local ai` is the
control: it grew in both sources, steadily, all year.

Two earlier readings depend on the step. The "Summer 2026" section of
[`01-keyword-research.md`](01-keyword-research.md) reads the privacy step as
a response to *United States v. Heppner*. Item 2 of "What this changes" in
[`07-what-users-do.md`](07-what-users-do.md) adds `private ai for business`
to the landing page, and clickstream sees about 50 searches a month for that
phrase. `ai workspace`, the other half of that item, holds: 302 → 1,160 in
clickstream over the year. Neither document is changed here.

Clickstream also falls broadly. Over the year the median term fell 25% among
templates, checklists and clauses, 18% among AI-tool terms and 26% among
everything else. Falling template searches are therefore not, on their own,
evidence that people moved to AI. The terms that rose are specific products:
`claude for legal` 50 → 3,230, `claude powerpoint` about 250 → 6,000,
`notebooklm` 1.27M → 3.12M.

## Plays

| play | use cases | job ad value | $/click | trend | software ad value | profession searches | profession $/click |
|---|---|---|---|---|---|---|---|
| Security, privacy and compliance | 9 | 700,829 | 23.58 | −4% | 444,210 | 6,400 | 31.69 |
| Legal | 15 | 583,840 | 11.49 | −11% | 1,233,879 | 11,970 | 56.65 |
| Proposals, sales and procurement | 8 | 397,507 | 9.57 | −17% | 336,460 | 910 | 54.97 |
| Consulting and strategy | 6 | 320,159 | 6.44 | −11% | 3,822 | 430 | 47.32 |
| Format agents | 6 | 289,779 | 6.50 | +19% | 74,586 | — | — |
| Real estate and construction | 9 | 285,494 | 8.96 | +1% | 59,146 | 8,340 | 17.78 |
| Operations and quality | 6 | 266,745 | 7.13 | 0% | 215,269 | 7,890 | 20.26 |
| Marketing | 3 | 228,230 | 7.57 | −16% | 0 | 8,980 | 24.21 |
| HR | 4 | 180,980 | 8.55 | −8% | 8,246 | 7,330 | 58.80 |
| Finance and banking | 9 | 166,552 | 10.20 | −3% | 150,159 | 13,970 | 24.31 |
| Insurance | 4 | 103,316 | 16.99 | +3% | 34,418 | 570 | 31.70 |
| Healthcare | 5 | 99,624 | 8.58 | +3% | 4,775 | 14,040 | 12.01 |
| Accounting and tax | 6 | 83,716 | 11.59 | −4% | 112,488 | 6,300 | 36.99 |

Nonprofit, product and technical writing, education and government are each
under $70K. `python rollup.py` prints all 17 plays and the 98 use cases.

Read the software column with its biggest term. Legal's $1.23M is 83%
`contract management software` (3,600 at $284), which is contract-lifecycle
buyers, not drafting. Security's is spread across `trust center`, `grc
software`, `cmmc compliance software` and `policy management software`.
Proposals' is 75% CPQ and procurement software. Nonprofit's $181K is 99%
`grant management software`.

## The jobs, with their evidence

The top use cases inside the three plays, from the rollup. Trend is January–May
against September–December:

| use case | job ad value | $/click | trend | biggest job terms (searches/$ a click) |
|---|---|---|---|---|
| Contracts: drafting and redlining | 218,471 | 13.96 | −28% | `ai contract review` 880/$67, `nda template` 8,100/$7, `contract template` 3,600/$7 |
| SOC 2 and ISO 27001 documentation | 209,650 | 34.31 | −4% | `soc 2 report` 1,900/$53, `soc 2 compliance checklist` 480/$65 |
| RFP, proposal and questionnaire response | 150,264 | 8.35 | −24% | `business proposal template` 6,600/$9, `rfp template` 4,400/$7 |
| Policies, compliance docs, risk assessments | 144,547 | 16.81 | −5% | `employee handbook template` 4,400/$15, `ai risk assessment` 320/$58 |
| Quotes, order forms and CPQ | 117,436 | 14.04 | −22% | `quote template` 2,900/$17, `configure price quote` 170/$153 |
| Security questionnaires | 94,939 | 20.55 | +12% | `hecvat` 2,400/$26, `caiq` 1,000/$7, `security questionnaire automation` 50/$109 |
| Clause drafting | 94,188 | 8.94 | +1% | `indemnification clause` 3,600/$9, `non compete clause` 2,900/$11 |
| Personal-injury litigation documents | 90,754 | 9.82 | −2% | `demand letter` 5,400/$8, `medical chronology` 390/$31 |
| Privacy documents: DPIAs, RoPAs, HIPAA | 85,562 | 19.52 | +3% | `privacy policy generator` 2,900/$20, `hipaa risk assessment` 320/$40 |
| Vendor risk assessments | 64,126 | 46.13 | −11% | `third party risk management` 880/$54, `vendor risk assessment` 260/$44 |
| Legal research memos | 62,326 | 22.34 | −20% | `legal memo template` 2,400/$17, `ai legal research` 390/$55 |
| Pen-test and vulnerability reports | 40,153 | 49.57 | +4% | `pen test report` 480/$70 |
| Contract abstraction | 38,283 | 57.14 | −18% | `ai contract management` 390/$61, `contract abstraction` 40/$132 |
| Government proposals | 32,709 | 8.02 | −1% | `compliance matrix` 390/$34, `capability statement` 2,400/$4 |

The named questionnaires are the clearest single job in the research. `hecvat`
(the higher-education vendor questionnaire), `caiq`, `sig questionnaire` and
`pci saq` together hold 3,700 to 4,400 searches a month in clickstream, every
month of the year. The generic phrasing, `security questionnaire`, has 140 in
Ads.

`ai contract review` is the largest AI-phrased legal job. It holds 880 at $67
in Ads and rose from 807 to 1,261 a month in clickstream, against a falling
background.

## Who already wins these searches

From the ranked pulls, non-brand keywords only:

| vendor | what ranks | examples (searches/$ a click, position) |
|---|---|---|
| Spellbook | a clause library, one page per clause | `non-compete clause` 4,400/$11 #5, `liability limitation clause` 1,300/$8 #3; the homepage is #1 for `ai contract drafting` 70/$231 |
| EvenUp | guides to the personal-injury documents | `medical chronology` 390/$31 #4, `medical records summary` 170/$40 #5, `demand letter` 5,400/$8 #14 |
| Conveyor | product pages | `security questionnaire automation` 90/$109 #2, `trust center` 1,900/$93 #21 |
| Vanta | SOC 2 explainers and product pages | `soc 2` 22,200/$77 #5, `soc 2 auditor` 1,900/$256 #2, `third party risk management software` 720/$173 #2 |
| Inventive | the homepage and RFP guides | `ai rfp software` 1,600/$32 #2, `rfp software` 480/$41 #4, `rfi in construction` #8 |
| Manus | one "playbook" page per artifact | `ai quotation` 2,900/$14 #2 (a quotation generator), `market research tool` 1,300/$27 #2, `ai report` 1,000/$11 #3 |
| Gamma, Genspark | the homepage, one tool page | `slide creator` 9,900/$4 #1 (Gamma), `ai presentation maker` 9,900/$9 #8 (Genspark) |
| MagicSchool | one page per teacher tool | `rubric generator` 2,900/$5 #1, `ai for schools` 2,900/$6 #1 |

Datarails ranks for Excel budget templates (`budget excel template` 18,100,
#13) and finance glossary pages. Fieldguide, GovDash and Blue J rank for
guides and glossaries, and Rogo only for its brand. Skywork's traffic is pages
its users published.

**The pattern: one page per artifact, or per atomic unit of one.** Spellbook
ranks a page per clause, Manus a page per artifact, MagicSchool a page per
tool.

## What practitioners say

Public threads, paraphrased. Each links to the source.

- **Personal injury.** A paralegal writes that the firm's AI now summarises
  medical records, drafts demand letters and selects discovery documents,
  which by their account was about 90% of the assistant's job
  ([r/paralegal, 469 upvotes, 24 Jul 2026](https://www.reddit.com/r/paralegal/comments/1v5abes/being_replaced_by_ai/)).
- **Security questionnaires.** Sysadmins describe the same questions reworded
  by every customer, answers they want to reuse, and hours spent finding
  evidence
  ([thread](https://www.reddit.com/r/sysadmin/comments/1rkwxpt/why_do_all_security_reviews_feel_the_same/)).
  One got a 40-question NIS2 assessment from their largest customer while
  having to assess their own suppliers
  ([254 upvotes](https://www.reddit.com/r/sysadmin/comments/1v8tekg/our_biggest_customer_sent_a_40question_nis2/)).
  Others report a 199-question audit
  ([thread](https://www.reddit.com/r/sysadmin/comments/1trskka/3_months_into_a_senior_system_administrator_role/))
  and a PCI self-assessment of over 200 questions
  ([thread](https://www.reddit.com/r/sysadmin/comments/1ovn5p5/best_way_to_get_pci_compliant/)).
- **Government proposals.** Contractors say they keep ITAR, CUI and
  proprietary data out of hosted models and work in a private cloud. They call
  the GovCon AI tools too expensive and not FedRAMP-authorised
  ([r/GovernmentContracting](https://www.reddit.com/r/GovernmentContracting/comments/1nyl9px/what_ai_tools_are_you_actually_using_in_your/)),
  and most proposal work is still copying and pasting
  ([thread](https://www.reddit.com/r/GovernmentContracting/comments/1pcgjgz/)).
- **Consulting decks.** A consultant ran Claude and ChatGPT as an associate:
  about 100 pages of sources became a ghost deck
  ([r/consulting, 497 upvotes](https://www.reddit.com/r/consulting/comments/1vri8fx/i_used_claude_and_chatgpt_as_i_would_an_associate/)).
  Another turns raw text into a formatted slide and a workbook into a tracker
  slide
  ([143 upvotes](https://www.reddit.com/r/consulting/comments/1vqg0h7/using_claude_as_a_powerpoint_magic_wand/)).
  A third thread is about the liability of an unreviewed AI deliverable
  ([420 upvotes](https://www.reddit.com/r/consulting/comments/1t39o3p/)).
- **Accounting and FP&A.** The work is still Excel, Word and PDF. ChatGPT gets
  journal entries wrong, and K-1 extraction needs a human check
  ([r/Accounting, 302 comments](https://www.reddit.com/r/Accounting/comments/1p6q2rl/are_you_guys_actually_using_ai_in_your/)).
  A staff accountant has AI write VBA macros, so the arithmetic is
  deterministic
  ([thread](https://www.reddit.com/r/Accounting/comments/1v12xrz/how_i_use_ai_as_a_staff_accountant/)).
  FP&A analysts want two budgets in and a variance analysis out
  ([thread](https://www.reddit.com/r/FPandA/comments/1st2g51/)), and monthly
  packs of tables with commentary
  ([thread](https://www.reddit.com/r/FPandA/comments/1pvreck/)). A thread on an
  IRS Office of Professional Responsibility alert tells preparers to keep client
  data on secure, approved AI
  ([r/taxpros](https://www.reddit.com/r/taxpros/comments/1w3seof/irs_office_of_professional_responsibility/)).
- **Real estate and construction.** An analyst builds DCF models in Excel with
  Cowork and then Claude Code, in place of Argus
  ([r/CommercialRealEstate](https://www.reddit.com/r/CommercialRealEstate/comments/1tklaap/)).
  The wins named elsewhere are lease abstraction, due-diligence review and comp
  write-ups
  ([thread](https://www.reddit.com/r/CommercialRealEstate/comments/1oui48f/)).
  In construction they are RFIs, submittals and specifications, with security
  worries
  ([r/Construction](https://www.reddit.com/r/Construction/comments/1rlln96/ai_tools_for_construction_documents/)).
- **The incumbent.** Claude users compare Cowork with Claude Code. Claude Code
  produces better documents, and Cowork cannot switch models or rewind
  ([r/ClaudeAI](https://www.reddit.com/r/ClaudeAI/comments/1uq109i/)).

Four requirements recur across these threads: reuse of past answers, the
customer's own format, numbers that tie out, and review before anything ships.

## What the agent needs for these jobs

| the job needs | today | where it is addressed |
|---|---|---|
| read the whole policy set or records bundle | Studio sends the first 24,000 characters of the selection ([Known gaps](../../../docs/architecture/studio.md#known-gaps)) | `search_sources` and `read_source` ([02-tools](../../../docs/proposals/agent/02-tools.md)) |
| write into the user's file: fill their questionnaire, redline their contract, use their template | Studio writes new files from source text; no format takes a file to write into | no proposal yet. The output folder makes it a copy, not an in-place edit |
| fill an existing workbook | xlsxwriter, the declared library, only writes new files; openpyxl is in the lock only as a transitive dependency | declare openpyxl for the XLSX path |
| tracked changes in a DOCX | python-docx has no tracked-changes API | a revision writer at the XML level, or a library that has one |
| cite the page or clause behind each answer | `studio.md` describes no source reference in any format | `read_around_citation` (02) finds the chunk; the artifact needs a source column or a comment |
| numbers that tie out | the model writes the spreadsheet code | formulas in the sheet, not values the model computed; a rule in the XLSX `SKILL.md` |
| reuse past answers | artifacts are searchable documents already | nothing to build: past questionnaires and proposals are sources |
| trust from the security buyer | model-written Office code runs unsandboxed in the worker (Known gaps) | the sandbox runner `studio.md` names; a security buyer will ask |

Two of these block all three plays: writing into the user's file, and a
grounded answer per question with its citation. Reading more than 24,000
characters is already on the agent's path.

## Tiers

**Test first.** One workflow and one page per job, measured before anything
else is built:

1. Fill a security questionnaire from your policies.
2. Redline a contract against your playbook.
3. Answer an RFP from past proposals.

**Build as capabilities.** Every job uses these:

- fill an existing workbook, with formulas;
- write a tracked-changes redline;
- lay out slides on the user's template;
- cite the source of each answer;
- treat past artifacts as sources.

**Second wave.** Good fit, smaller or harder market:

| play | why second |
|---|---|
| Insurance | COI review, ACORD forms, policy comparison at $63 a click, but $103K in total |
| Real estate and construction | lease abstraction at $42 a click, offering memorandums, RFIs and submittals |
| Finance, FP&A and accounting | variance commentary and workpapers; practitioners want numbers they can tie out, and accounting's job demand is $84K once `cost segregation study` is out |
| Healthcare | clinical letters; `ai prior authorization` is $135 a click on 140 searches |

**Skip for now:**

| play | why |
|---|---|
| Marketing collateral and meeting minutes | high volume at $3-10 a click, and owned by template sites and meeting tools |
| HR documents | template demand at $8.55 a click, and $8K of software budget in these pulls |
| Education | MagicSchool ranks #1 for the tools, at about $5 a click |
| Government documents, grant writing, translation | under $6 a click |
| Consumer legal (family, estate) | written by the parties, not by firms |

## How this relates to 07

[`07-what-users-do.md`](07-what-users-do.md) chose cross-cutting pages with
professions named inside them. It promotes `ai for lawyers` first if a
profession earns its own page. This document supports that order. `ai for
lawyers` is steady at about 1,300 a month in clickstream. `claude for legal`
rose from 50 to 3,230. Legal carries the highest profession CPC.

It adds a second kind of page, which 07 did not consider: the **job page**.
The vendors that win organically rank one page per artifact, not one per
profession (above). A page such as "fill a security questionnaire from your
own policies" is cross-cutting inside its play and names the professions as
proof, which is 07's rule. Whether to add job pages to the plan is an open
decision. This document does not make it.

## What would change the answer

- **The summer step.** Re-pull Google Ads after mid-October 2026. If the step
  holds while clickstream stays flat, it is a Google data change, and every
  figure in this folder since June should be read as inflated.
- **Clickstream's panel** likely over-represents technical users. It puts
  AI-tool and brand terms 5-20 times above Ads (`chatgpt agent` 25,740 vs
  4,400, `excel ai` 13,072 vs 1,300). So the format-agent demand above is a
  floor.
- **Search misses in-app demand.** Someone who asks Claude inside Excel does
  not search for it. Demand for editing inside the apps is under-counted, and
  the incumbents hold it.
- **Judgment calls.** The term classes, the eighteen exclusions and the
  mapping of use cases to plays all live in `use-cases.json`. Excluding
  `cost segregation study` (6,600 at $28) is the largest single call. If
  do-it-yourself studies are a real segment, Accounting and tax gains about
  $187K.
- **CPC is bidding, not value.** A crowded category shows a high CPC whether or
  not buyers pay for the job. `soc 2 auditor` at $256 is the auditors' market,
  not the documents'.
- **US only.** [`03-international.md`](03-international.md) and 07 conclude
  US-first, and nothing here was pulled abroad.

## Re-running

```bash
cd plans/community-local/seo/data/b2b
python rollup.py --self-check   # the rollup's tests
python rollup.py                # every table: 98 use cases, 17 plays, exclusions, watch lists
python rollup.py --top 30       # the use-case table cut to 30 rows
```

The call shapes, file list and clickstream notes are in
[`data/README.md`](data/README.md#b2b-artifact-jobs). To add a use case, add
its terms to `use-cases.json`, pull them with `keyword_overview/live` into
`data/b2b/`, and run a clickstream check on any term over 300 searches.
