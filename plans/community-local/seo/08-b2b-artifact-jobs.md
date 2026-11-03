# B2B file jobs: what the agent should be best at

Which business jobs on files SurfSense's agent should be built and sold for,
and how it earns from them. It feeds the business strategy in
[`../file-agent-strategy.md`](../file-agent-strategy.md), the agent work in
[`docs/proposals/file-agent/`](../../../docs/proposals/file-agent/README.md)
and the page plan in [`02-page-briefs.md`](02-page-briefs.md).

**Revised 21 Oct 2026.** This replaces the 29 Sep 2026 version, which ranked
artifact jobs (questionnaires, contracts, proposals) by search demand alone; git
history keeps it. This revision re-pulls that research, adds 37 file jobs it
did not cover (extraction, organizing, redaction, review of file piles,
transcription), and tests every candidate three ways: demand and reach, who
pays and what they would pay SurfSense, and whether the product can be best at
it.

**Revised 22 Oct 2026: the B2B jobs are paid plugins.** The maintainer decided
that each B2B job ships as a plugin that runs on the user's machine and unlocks
with a SurfSense licence, the 14-day trial included, while the app, the general
agent, the engines and the shared job infrastructure stay free and open source
([ADR 0067](../../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)). That
replaces this document's earlier rule that every job and its content stay free.
The sections it changes are the headline, the note under the bets table, the
RFP and registers sections, the capability items 11 and 12 with "One paid-path
build at a time" and "Where each piece lives", "How SurfSense earns", "Pages
and reach", "The next 90 days", the kill criteria, the swap rules and the open
questions.

**Revised 1 Nov 2026: one paid licence, Business, and the scrapers retire.**
The maintainer decided that SurfSense sells one paid licence, Business, priced
per person from one person; that a job plugin unlocks only with a Business
licence or the 14-day trial; and that the Individual licence stops being sold
([ADR 0079](../../../docs/adr/0079-surfsense-sells-one-business-license-priced-per-person.md)).
Seven platform scrapers retire, and reading web pages, YouTube transcripts and
web search move into the app, free for everyone
([ADR 0080](../../../docs/adr/0080-surfsenses-scrapers-retire-and-web-pages-and-search-stay-free.md),
revised 2 Nov 2026: PostHog shows those three are the ones people use). It all
happens in one release, the one that ships the first paid job: Business
goes on sale, the scrapers retire and Individual sales stop together, so the
paid offer is never empty. Until then the scrapers and the Individual licence
stay on sale. Source: maintainer decision, 1 Nov 2026 (no permalink). None of
it is built yet. The sections it changes are the headline's third point, the RFP section,
"How SurfSense earns", "The next 90 days", the price in the kill criteria and
swap rules, and the open questions.

**Sources.** DataForSEO, pulled **21 Oct 2026**, Google US (`location_code:
2840`, `language_code: en`), data through September 2026: Google Ads volume and
CPC for 1,988 terms, clickstream exact-phrase volume for 1,492 of them, 83 SERPs
and the top 200 non-brand keywords of 17 more vendors. Archived in
[`data/b2b-oct/`](data/b2b-oct/) and rolled up by
[`data/b2b-oct/rollup.py`](data/b2b-oct/rollup.py); every demand figure below is
its output unless the text names another source. Market, price and practitioner
evidence was gathered the same day from vendor pages, G2 reviews, practitioner
forums and Upwork, and is cited inline. The product facts were checked against
`dev` at `746c5fd66` (v2.2.3).

## The headline

1. **Lead with one job: the security and due-diligence questionnaire, answered
   inside the customer's own spreadsheet from the company's own policies and an
   approved answer library.** It is the only candidate that survived the
   demand and fit tests as a lead. The searched core is **$128K a month of ad
   value at $27.20 a click**, on 5,425 exact-phrase searches. 71.2% of
   questions arrive as Excel ([Skypher](https://www.skypher.co/post/how-to-answer-security-questionnaires)),
   and the hard part, writing back without breaking the workbook, already
   ships: the Excel revise engine edits sheet XML and keeps charts, pivots and
   macros byte for byte
   ([`excel.py`](../../../surfsense_local/backend/modules/artifacts/revised_copies/engines/excel.py)).
2. **It ships before the contract redline.** The redline's edge went in
   October: Microsoft's Copilot for Legal reviews against a playbook and writes
   native tracked changes in Word
   ([MC1388706](https://mc.merill.net/message/MC1388706), 7 Oct), Clio added
   Review Playbooks on 1 Oct
   ([Clio](https://www.clio.com/enterprise/blog/clio-brings-firm-specific-judgment-into-ai-contract-review/)),
   and Anthropic's Apache-2.0 [Claude for Legal](https://github.com/anthropics/claude-for-legal)
   does the same in Claude for Word. The redline also still needs the
   `docxkit`/`crlib` clean-room fix and a lawyer's review.
3. **Revenue comes from the jobs themselves, as paid plugins** (decided
   22 Oct 2026, [ADR 0067](../../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)).
   While every job was free, every revenue test came back weak, and the only
   paid hooks were wrappers around the jobs. Businesses already pay for the
   jobs: self-serve questionnaire tools at $50 to $249 a month, Loopio about
   $24K a year for small teams. So each B2B job ships as a plugin that runs on
   the user's machine and unlocks with a Business licence, priced per person,
   or the 14-day trial (decided 1 Nov 2026,
   [ADR 0079](../../../docs/adr/0079-surfsense-sells-one-business-license-priced-per-person.md)).
   The app, the general agent, the engines and the shared job infrastructure
   stay free and open source. Firm controls and team features come later in
   Business, and Enterprise assurance is quoted.
4. **One engine, then many jobs.** Every second-wave job needs the same
   builds: page citations, a per-row or per-file runner, extraction into a
   schema with totals that tie out, per-row review beside the source, and a
   library. Build them for the questionnaire, then reuse them: RFP responses
   from the same library first, then bank statements, medical chronologies,
   and contract and lease registers.
5. **Search is small and slightly falling; reach comes from elsewhere.** The
   questionnaire core fell 4% in raw clickstream over the year. One page per
   named questionnaire is winnable (keyword difficulty 9 to 16), but most reach
   has to come from design partners, MSP and vCISO referrals, the open-source
   repo, the Show HN and published eval rows.
6. **Pure file handling is a free capability, not a business.** Converters,
   OCR, renaming and organizing pull about 1.3M exact-phrase searches a month,
   at $3.67 a click, against free tools, Acrobat and the operating system.
   Organizing a folder is $18.5K of job value in all. Build these because the
   paid jobs need them, and use them as the funnel: with decks and reports
   from the user's files and a local alternative to Claude Cowork, they are the
   free layer that organic search, user posts and creators carry, while the
   paid jobs run on confidential files nobody posts.
7. **Insurance is dropped.** Both large agency systems put submission and
   policy-check agents inside their own products within eleven days (Applied
   Epic Conductor, 29 Sep; Vertafore, GA 16 Oct), and 89% of the submissions
   value was lookups for blank ACORD forms.

**What still holds from September:** the agent writes only revised copies and
never the user's original, so a filled questionnaire is a new file beside the
customer's; the customer's own format is the product; and no page, README line
or claim ships before an eval row backs it.

## What changed since 29 September

### The summer step was Google's data

September's research saw Google Ads step up from June in unrelated AI terms
while clickstream did not, and said to re-check after mid-October. The step
held through September, and clickstream still did not move:

| term | Google Ads, May / Jun / Jul / Aug / Sep 2026 | clickstream, same months |
|---|---|---|
| private ai | 2,400 / 5,400 / 60,500 / 201,000 / 165,000 | 3,066 / 3,217 / 3,066 / 3,016 / 3,117 |
| private llm | 880 / 3,600 / 6,600 / 18,100 / 12,100 | 1,357 / 1,307 / 1,106 / 1,508 / 1,307 |
| self hosted ai | 1,000 / 4,400 / 6,600 / 14,800 / 12,100 | 754 / 804 / 905 / 905 / 905 |
| private ai for business | 50 / 1,900 / 5,400 / 12,100 / — | 50 every month |
| local ai | 4,400 / 8,100 / 12,100 / 22,200 / 18,100 | 10,256 / 10,759 / 11,262 / 12,066 / 13,223 |
| claude for excel | 9,900 / 8,100 / 6,600 / 4,400 / 4,400 | 19,960 / 21,267 / 23,077 / 23,580 / 24,384 |
| nda template (control) | 4,400 / 4,400 / 14,800 / 18,100 / 4,400 | 5,279 / 5,228 / 4,876 / 4,625 / 4,575 |
| hecvat (control) | 2,400 / 2,400 / 2,400 / 2,400 / 2,900 | 2,765 / 2,765 / 2,564 / 2,513 / 2,111 |

It is a Google data change confined to AI-phrased records. Across 17 privacy
and infrastructure heads, Ads in July to September ran at a median 4.03 times
March to May against 1.00 in clickstream. Non-AI job terms show no step (Ads
0.81, clickstream 0.91), only single-month spikes such as `nda template` in
August. For AI product names Ads moves the other way: `claude for excel` fell
in Ads while its clickstream rose 22%. Real local-AI interest grew, but by 20 to
30% (`local ai` +29%, `offline ai` +27%), not tenfold. Two corrections to
September's table: `private ai` was 60,500 in July and 201,000 in August, and
`private ai for business` never left 50 in clickstream, so the privacy-qualified
pages in [`07-what-users-do.md`](07-what-users-do.md) rest on nothing.
Archived in [`data/b2b-oct/recheck/`](data/b2b-oct/recheck/).

### The market moved

- **6 Oct.** Claude Cowork moved to Anthropic's cloud for Pro and Max; the
  "Only on your computer" option was removed and local files are copied up when
  a task needs them ([Claude help](https://support.claude.com/en/articles/15520349-use-claude-cowork-on-web-desktop-and-mobile)).
  Searches for it kept growing (clickstream 302,973 in May, 382,060 in
  September), and `claude cowork linux` nearly doubled (502 to 955), a platform
  Anthropic does not serve and SurfSense ships on.
- **6 Oct.** Claude for Google Workspace entered public beta for all paid
  plans ([9to5Google](https://9to5google.com/2026/10/06/claude-google-docs-sheet-slides/)).
- **7 Oct.** Copilot for Legal in Word, worldwide preview for Frontier tenants:
  playbook review with native tracked changes ([MC1388706](https://mc.merill.net/message/MC1388706)).
  Clio's Review Playbooks had shipped on 1 Oct.
- **8 Oct.** Google previewed persistent Gemini agents, included at no extra
  charge in Workspace business plans
  ([VentureBeat](https://venturebeat.com/orchestration/google-cloud-unveils-persistent-gemini-agents-for-long-running-tasks-and-they-get-their-own-gmail-calendar-and-drive-storage)).
- **29 Sep and 16 Oct.** Applied Epic Conductor and Vertafore's Policy Intake
  and Policy Check agents put insurance submission and policy work inside the
  agency systems ([insurance-edge](https://insurance-edge.net/2026/10/07/applied-systems-launches-epic-conductor/),
  [fintech.global](https://fintech.global/2026/10/16/vertafore-launches-ai-agents-to-automate-insurance-policy-checks)).
- **16 Oct.** NVIDIA released Nemotron 3.5 open models, including Bolt
  74B-A9B for 24 GB machines and a 4 GB E4B due 23 Oct
  ([Techstrong](https://techstrong.ai/articles/nvidia-launches-three-open-ai-models-to-power-enterprise-agents)):
  candidates for the local job rows.
- **Questionnaire vendors.** Conveyor's pricing page now shows a $0 plan
  (trust center only) and custom Enterprise, so September's "Conveyor from
  $9,600 a year" no longer holds ([Conveyor](https://www.conveyor.com/pricing)).
  Self-serve questionnaire tools list at $50 to $249 a month
  ([SourceForge](https://sourceforge.net/software/security-questionnaire-automation/)).
- **CMMC.** A DoD memo of 13 Jul 2026 put CMMC Phase II, due 10 Nov, in
  abeyance ([Greenberg Traurig](https://www.gtlaw.com/en/insights/2026/7/dod-suspends-cmmc-deadlines-and-seeks-to-reassess-requirements)),
  so it is not a timing hook for government work.

### Demand moved

- `ai contract review` is the strongest legal signal: CPC $66.60 to $97.49,
  clickstream 1,005 to 1,156.
- Clause terms kept their searches and lost their bidders: `non compete clause`
  $10.89 to $3.23 a click, `confidentiality clause` $25.22 to $1.14. Clause
  drafting fell from $94K to $32K a month.
- `acord forms` fell from $20.69 to $9.42 a click and 42% in clickstream; the
  Insurance play fell 36% like for like.
- Named security questionnaires lost exact-phrase searches over the summer:
  `hecvat` 2,765 to 2,111, `soc 2 report` 553 to 301.
- Document comparison rose: `compare pdf files` tripled in clickstream (201 to
  603), `compare documents` +45%.

### The research now covers file jobs

The 98 September use cases were re-pulled on the new footing, and 37 new ones
were added from six scouts (extraction, organizing and search, file-pile
review, competitor rankings, revenue, practitioner voice). Nine form a new
**File operations** play. Each of the 922 new terms was labelled by one agent
and re-judged by a second, with SERP checks for the ambiguous ones; the labels
and the 77 exclusions, each with its reason, are in
[`use-cases.json`](data/b2b-oct/use-cases.json).

## How this was counted

**Five kinds of term.** September's three, plus two:

| kind | what it measures | example |
|---|---|---|
| job | someone has to produce the output now | `hecvat`, `how to redact a pdf`, `lease abstraction` |
| software | a budget: what vendors pay to reach a buyer | `contract management software`, `data room` |
| profession | `ai for <profession>`, reported per play | `ai for lawyers` |
| **utility** | free-tool demand, mostly individuals | `pdf to excel`, `image to text`, `duplicate file finder` |
| **brand** | a vendor's name: buyers who search for a seller | `suralink`, `hebbia`, `diffchecker` |

Use cases are ranked on job terms only. A judged label in `use-cases.json`
overrides the wording rules.

**Volume.** A term's volume is the median of its last three months, capped at
its 12-month average, as in the rest of this folder, with three corrections:

- **AI-phrased terms** (ai, llm, gpt, chatgpt, claude, copilot, gemini, agent,
  cowork, notebooklm) and any term whose Ads stepped up threefold while
  clickstream did not are counted at their January to May Ads level, times
  their clickstream growth since. 571 terms in all are counted differently from
  Google Ads; `python rollup.py --json` lists each with its basis.
- **Merged records.** An Ads record at ten times its clickstream or more is
  counted at clickstream times the median Ads/clickstream ratio, now 1.04.
- **Single-month spikes** on non-AI terms are capped at the March to May level
  unless clickstream confirms them.

**Trend** is clickstream June to September 2026 over October 2025 to January
2026, divided by the panel's own drift. The median term fell to 0.75 of its
level over the year, so a flat term reads +33%. The tables say "trend" for this
relative figure and "raw" where the drift is left in.

**Cores.** A use case's terms mix readers. Where a verdict rests on a narrower
set, the set is defined in `use-cases.json` under `cores` and printed by the
rollup, so the figures in the bets below are reproducible.

**Ad value is not revenue,** and CPC is bidding, not value: a crowded category
shows a high CPC whether or not buyers pay for the job.

## Plays

| play | use cases (new) | job ad value | 29 Sep | $/click | trend | software ad value | profession searches |
|---|---|---|---|---|---|---|---|
| Security, privacy and compliance | 13 (4) | 997,799 | 700,829 | 24.25 | −12% | 520,902 | 4,965 |
| Legal | 20 (5) | 615,405 | 583,840 | 9.84 | −5% | 2,505,560 | 18,903 |
| Proposals, sales and procurement | 10 (2) | 508,779 | 397,507 | 9.94 | +1% | 248,235 | 1,295 |
| Format agents | 7 (1) | 487,115 | 289,779 | 7.45 | +15% | 33,915 | — |
| **File operations** | 9 (9) | 439,023 | — | 13.91 | +38% | 1,063,475 | — |
| Real estate and construction | 12 (3) | 436,657 | 285,494 | 10.27 | +10% | 147,928 | 7,579 |
| Consulting and strategy | 6 (0) | 375,607 | 320,159 | 7.14 | −5% | 8,487 | 173 |
| Finance and banking | 12 (3) | 356,717 | 166,552 | 15.93 | +25% | 893,789 | 14,512 |
| Operations and quality | 7 (1) | 331,027 | 266,745 | 7.97 | +9% | 348,657 | 4,172 |
| Marketing | 3 (0) | 261,110 | 228,230 | 8.21 | −4% | 0 | 6,915 |
| Insurance | 6 (2) | 254,646 | 103,316 | 16.81 | +7% | 63,422 | 470 |
| HR | 5 (1) | 242,156 | 180,980 | 9.92 | −11% | 22,018 | 4,572 |
| Accounting and tax | 10 (4) | 221,768 | 83,716 | 15.19 | +1% | 284,746 | 6,247 |

Product and technical writing, healthcare, nonprofit, education and government
are each under $91K. `python rollup.py` prints all 135 use cases and 18 plays.

**Read the plays table as an upper bound.** Checked by who is searching, most
headline values shrink. The recounts below were made per bet, on the use cases
each bet covers:

- **Security.** The seven questionnaire and compliance use cases hold $667K,
  and 52% of it is the wrong reader. `soc 2 report` ($98K) is the auditor's
  attestation, which no vendor writes; `third party risk management` ($62K) is
  the buyer's category term; `due diligence questionnaire` ($79K) is an Ads
  record 9.6 times its clickstream; employee-handbook and risk templates are
  HR. What remains is the questionnaire core below.
- **Contracts.** The seven contract and lease use cases hold $368K, and 64% of
  their searches are clause lookups and template downloads. The `contract
  management software` budget ($2.2M of CLM clicks) belongs to Ironclad-class
  vendors.
- **Proposals.** The five proposal use cases hold $370K, of which about $65K is
  people answering a bid. The rest is blank proposal templates ($96K), the
  issuer-side `rfp template`, and one `ai quotation` record of 3,600 that
  clickstream puts at about 50.
- **Format agents.** Of the format-agent use cases, 31% of the value is vendor
  names (`claude for excel` alone is $138K and explains 74% of the Spreadsheet
  case's rise) and 41% is how-to demand that Word answers natively.
- **File operations.** About 60% of the play's $439K is single-document
  how-to: `how to compare two word documents` ($166K, at $46 a click on a SERP
  that shows no ads) and redaction how-tos that Acrobat answers (82% of
  redaction's $130K).

## Cores the verdicts rest on

| core | searches | clickstream | ad value | $/click | KD | trend | raw | biggest terms |
|---|---|---|---|---|---|---|---|---|
| Security questionnaires the vendor answers | 4,710 | 5,425 | 128,110 | 27.20 | 11 | +28% | −4% | hecvat 2,400/$27; sig lite 320/$65; security questionnaire automation 70/$228 |
| Security policy templates (the evidence base, as pages) | 3,860 | 2,561 | 84,724 | 21.95 | 11 | −1% | −26% | information security policy 590/$31; business continuity plan template 880/$18 |
| RFP and RFI responders | 1,780 | 1,404 | 18,630 | 10.47 | 8 | +10% | −17% | rfp response 590/$22; rfp response template 480/$5 |
| Bank and card statements into a ledger | 2,450 | 7,336 | 59,683 | 24.36 | 6 | −3% | −28% | bank statement converter 1,090/$15; bookkeeping cleanup 170/$60 |
| Medical records into chronologies and summaries | 2,600 | 900 | 96,578 | 37.15 | 11 | +1% | −24% | medical records chronology 50/$440; medical chronology 390/$38 |
| Contract and lease registers from a folder | 3,280 | 1,555 | 72,987 | 22.25 | 4 | +14% | −15% | lease abstraction 480/$55; contract renewal 590/$32 |

`hecvat` alone is 51% of the questionnaire core, and September 2026 (4,721)
was the core's lowest month of the year. The medical core's value leans on one
50-search record at $440 a click ($22K); without it the core is about $75K.

## Demand that is sold, not searched

The jobs with the largest budgets have almost no job searches. Buyers search
for vendors and software instead:

| use case | job ad value | software ad value | software $/click | brand clickstream |
|---|---|---|---|---|
| Contract abstraction and obligation extraction | 12K | 1,023K | $275 | — |
| Contract portfolio register (new) | 20K | 946K | $250 | — |
| Data-room and closing-binder assembly (new) | 11K | 669K | $119 | — |
| Client document intake and filing (new) | 6K | 430K | $57 | 35,193 |
| Back-file digitization (new) | 8K | 281K | $23 | 17,395 |
| Discovery document review, small firms (new) | 16K | 271K | $46 | 1,558 |
| Tax source-document intake (new) | 0.4K | 113K | $26 | 20,409 |

Brand demand points the same way: `suralink` 33,100, `smartvault` 18,100,
`covidence` 22,200, `hebbia` 8,100, `govwin` 8,100 a month in Ads. These
markets are reached through partners, communities and the systems the files
already live in, not through job pages.

## Free-tool demand

| play | utility clickstream | $/click | biggest brand terms |
|---|---|---|---|
| File operations | 1,293,470 | 3.67 | smartvault, diffchecker, macwhisper |
| Format agents | 24,635 | 4.01 | deepl pro |
| Legal | 20,058 | 2.11 | goldfynch |

`pdf to excel` alone is about 250,000 exact-phrase searches a month at $2 a
click, served by Adobe, free web tools and Excel's own import; `image to text`
is 464,000. Converter clickstream fell 33 to 39% over the year. A local
converter page can sit in this funnel, but it should not set product direction.

## The bets

Thirteen job families were each judged by three skeptics working from the same
evidence: demand and reach, revenue and buyer, and product fit, moat and build
cost. Three strategy drafts were then written to different priorities
(revenue-first, leverage-first, reach-first), judged, and critiqued for
completeness.

| bet | demand | revenue | fit | tier |
|---|---|---|---|---|
| Questionnaires answered in the customer's file from an owned library | lead | second wave | lead | **lead** |
| RFP, RFI and DDQ responses from the same library | second wave | second wave | second wave | **second wave, first in line** |
| Bank and card statements into a ledger that ties out | second wave | second wave | capability | second wave (first extraction job) |
| Medical records into chronologies and specials | second wave | capability | second wave | second wave |
| Contract and lease registers from a folder; playbook redline | second wave | capability | second wave | second wave (multi-file only) |
| Small-firm litigation support (production, review, privilege logs) | capability | capability | second wave | capability |
| Redaction and privacy file operations | capability | capability | second wave | capability |
| Format agents: Excel, Word, PowerPoint, compare, translate | capability | capability | capability | capability |
| Deliverables from sources: decks, board packs, reports | capability | capability | capability | capability |
| Recordings into records: transcription, coding, investigations | capability | capability | capability | capability |
| Construction: submittals, bid leveling, document control | second wave | capability | capability | capability |
| File management: intake, filing, organizing, search, converters | capability | capability | capability | capability |
| Insurance: ACORD, loss runs, SOVs, policy checking | capability | skip | capability | **skip** |

Every lens scored the revenue case weak for every bet, and for the same reason:
the job and its content were free by decision, so SurfSense captured no part of
what buyers pay vendors for the job itself. That reason went on 22 Oct 2026,
when the B2B jobs became paid plugins
([ADR 0067](../../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)), so the
revenue scores above understate the jobs; the tiers stand, because they rest on
demand and fit as much as revenue. How the jobs earn is
[below](#how-surfsense-earns).

### Lead: the security and due-diligence questionnaire

**The job.** In: the customer's questionnaire workbook (`.xlsx` or `.xlsm`:
HECVAT 4, CAIQ v4, SIG Lite read from the user's own licensed copy, or a
vendor's own sheet, with dropdowns, merged cells, hidden tabs and scoping
questions), the company's policy folder, its SOC 2 report and past answered
questionnaires. Out: a revised copy of the same workbook with every answer
filled using only values each cell's dropdown allows, locked and hidden cells
untouched; a Source (document, section, quoted passage) and Confidence per
answer and an Exceptions list, written by default to a new sheet or a companion
workbook so the requester's own import still works; no "Yes" without a source;
and reviewed answers written back to the answer library.

HECVAT 4 merged the Full, Lite and On-Prem forms into one file with scoping
logic ([Campus Technology](https://campustechnology.com/Articles/2025/02/11/Educause-HECVAT-Vendor-Assessment-Tool-Gets-an-Upgrade.aspx),
11 Feb 2025), so the job and its gold set model HECVAT 4, not the retired Lite.

**Why it leads.** It is the only bet with two lead verdicts. Buyers already
pay, self-serve ($50 to $249 a month) and by contract (Loopio $24K a year for
small teams, [SpendHound](https://www.spendhound.com/marketplace/loopio-pricing);
Responsive about $14K; Vanta's questionnaire module $3K to $8K,
[Vendr](https://www.vendr.com/marketplace/vanta)). Nobody hands it to
freelancers: no Upwork posting since April asked for one. The incumbents'
complaints are the opening: answers drift or miss what the library holds
(Conveyor and Loopio reviews on G2), and output does not fit the customer's
format. And it builds the engine every later job reuses.

**What is weak, stated plainly.**

- Search is about 5,000 US searches a month and fell 4% raw; one term carries
  half the value.
- The moat is thin. Claude Code reportedly fills a 300-question CAIQ in 15 to
  25 minutes (Skypher); UpGuard and a Relevance AI agent fill sheets in place;
  [Comp AI](https://github.com/trycompai/comp) (AGPL, about 2,000 stars) answers
  from policies. What lasts is a library the customer owns and governs, any
  model including the plan the buyer already pays for, files sent only to the
  chosen model, no per-questionnaire fee, and an intact workbook.
- Local processing sets SurfSense apart but is not required by this buyer, and
  "local" holds only on a measured local model. None has been measured on the
  job.
- On a consumer Claude Pro or Max plan, data falls under consumer terms, which
  allow training if the user opts in
  ([Anthropic](https://www.anthropic.com/news/updates-to-our-consumer-terms)).
  Job setup should recommend commercial terms (Team, Enterprise, the API) or a
  local model, and say so for NDA-bound evidence.
- About 19% of questions arrive through portals (OneTrust, Whistic and the
  like), which a file job does not reach.

**Licensing.** SIG is licensed ($7,000 a year) and the CAIQ and HECVAT terms are
unconfirmed. No question text ships until CSA and EDUCAUSE confirm terms in
writing: mappings read the user's own copy, and eval samples are synthetic.
SurfSense's own completed CAIQ goes through CSA's STAR Registry, the channel CSA
names; its HECVAT is shared on request; the website shows only answers keyed by
question ID.

### Second wave, first in line: RFP and DDQ responses from the same library

Revised 1 Nov 2026: the DDQ comes first, with the security questionnaire, and
RFP and RFI responses follow it
([ADR 0079](../../../docs/adr/0079-surfsense-sells-one-business-license-priced-per-person.md)).

**The job.** In: the issuer's RFP, RFI or DDQ response workbook, the answer
library and past proposals. Out: a revised copy with each response filled, a
Source column citing the past bid, a Comply/Partial/Exception column, an
exceptions list, and approved answers written back. Next, the issuer's `.docx`
Q&A table filled by cell address; after page citations ship, a solicitation PDF
turned into a compliance matrix with Section L and M references.

All three lenses scored it second wave: the responder core is $18.6K a month and
fell 17% raw, the CUI angle has no measurable search demand, and hosted
CUI-capable options exist (Copilot in GCC High; Ask Sage, FedRAMP High). It is
first in line because it is a second paid job plugin on the same library and
engine, sold to buyers who already pay for exactly that kind of library, for an
S to M marginal build. It starts only
after the questionnaire passes its gate and a proposal manager joins as a
design partner. Loopio's prices prove buyers pay for a library; they are not a
price anchor for SurfSense.

### Second wave: the extraction stack

Three jobs share one stack (page citations, tables that keep their columns, a
schema per document type with deterministic tie-out checks, and a batch runner)
and go in this order:

1. **Bank and card statements into a ledger.** In: 12 to 36 monthly statement
   PDFs, born-digital or scanned. Out: an `.xlsx` ledger with a page cite per
   row, a tie-out sheet (opening + activity = closing), an exceptions sheet and
   a CSV/QBO export. First because statements check themselves, which makes it
   the cleanest test of the stack. The model maps each layout to the schema and
   app code moves the values, so no figure passes through model-written code.
   Not a lead: the converter family is a falling commodity (`bank statement
   converter` clickstream 5,832 to 3,720), ProperConvert already converts
   locally from $19.99 a month ([ProperSoft](https://www.propersoft.net/)), and
   QuickBooks' and Copilot's agents absorb categorizing and matching. The pull
   is regulatory: the FTC Safeguards Rule and IRS OPR Alert 2026-19 on client
   data in AI tools.
2. **Medical records into chronologies and specials.** In: a 500 to 1,000-page
   records packet. Out: a chronology with a page cite per row, a specials sheet
   that ties to the bills, and a duplicates and missing-records list. The
   clearest proof that buyers pay (EvenUp valued above $2B with 2,000+ firms;
   per-page services at $0.05 to $0.40), but searched demand is small, buyers
   search vendor names (EvenUp 6,888, Supio 5,530 in clickstream), and the
   systems the files live in bundle the job (Filevine, NetDocuments
   [ndMAX](https://artificiallawyer.com/2026/07/22/netdocuments-launches-expert-witness-plaintiff-apps/),
   CASEpeer). The PHI argument holds only on a local model.
3. **Contract and lease registers from a folder.** In: 50 to 300 signed
   agreements or leases with amendments. Out: a register with parties, term,
   key clauses and renewal and notice dates computed by formula, a page cite per
   field, amendments taking precedence, and an exceptions sheet. This is where a
   folder agent can be best in legal; `lease abstraction` (480 at $54.55) sits
   on a SERP led by an old forum thread. A user-directed redline of one
   contract stays a free edit on the shipped revise tool; the playbook redline
   is a paid job plugin, after this stack.

### Capabilities, not plays

| bet | why not a play | what to build and when |
|---|---|---|
| Litigation support | $63K of job value; review is sold, not searched; GoldFynch hosts small matters at $27 a month; highest liability | Bates numbering across a set with a production index (S to M), when the medical packet needs it |
| Redaction and privacy | 82% single-document how-to that Acrobat answers; a missed redaction is the worst reputational risk for an app sold on privacy | True burned-in redaction with a leak check (L), only when a job needs it |
| Format agents | in-app editing is bundled by Claude for Microsoft 365, Claude for Workspace and Office in Copilot | keep the revise engines excellent; they carry every job. Comparison has paying offline buyers (Draftable $129 to $261 a year) and joins the contracts wave |
| Deliverables from sources | 67 to 69% blank-template demand; bundled everywhere | the free entry point: 43% of hosted users did this ([07](07-what-users-do.md)) |
| Recordings | free local tools with speaker labels already serve the reachable reader ([Buzz](https://github.com/chidiwilliams/buzz), noScribe) | diarization and m4a/mp4 decoding (M+M) when a job needs them |
| Construction | Procore and Autodesk absorb the register; drawings cannot be read | bid leveling as a free demo on the extraction stack |
| File management | $18.5K of job value; paperless-ngx (47,000 stars) and Copilot+ file actions; the agent cannot rename or move files by design | a copy-out folder export after the batch runner |

### Skip: insurance

Applied and Vertafore now ship the job inside the agency system, ACORD licenses
its forms and gives members free extraction pages, and the play fell 36% like
for like. At most, a loss-run summary becomes a free demo of the extraction
stack.

## What the agent needs: one engine for many jobs

Effort is for one maintainer working with agents: S up to a week, M one to
three weeks, L four to eight. These are estimates, to be replaced by measured
velocity.

| # | capability | effort | serves | when |
|---|---|---|---|---|
| 1 | Job-gate eval harness (`scripts/job_eval` does not exist) and a synthetic corpus: a policy pack and three questionnaires (HECVAT 4-shaped with scoping logic, CAIQ v4-shaped, a vendor `.xlsm` with dropdowns, merged cells and hidden tabs), about 200 gold rows | M | every job | first |
| 2 | Baseline row: today's free-form Agentic fill on Sonnet 5.5 and Qwen3.8-27B | S | questionnaire | first; it decides whether item 8 moves into the beta |
| 3 | Workbook inspection and write-time validation: question and answer columns across tabs, dropdowns, locked and hidden cells, merged ranges, scoping questions; refuse off-list values; accept `.xlsm` uploads; an `add_sheet` operation (none of the eight revise operations adds a sheet) | M+S+S+S | questionnaire, RFP matrices, registers | beta |
| 4 | Provenance: Source and Confidence per answer, a check that the quoted passage exists in a ticked source, an Exceptions list, no unsupported "Yes" | M | both library jobs; the pattern for every extraction job | beta |
| 5 | Answer library v1 in the existing, unused `library` folder role, with import from past questionnaires and Loopio or Responsive exports (imported entries start unapproved) | M + S–M | both library jobs | beta |
| 6 | Per-row review: accept, edit or reject each answer beside its source, with a review record | M | both library jobs, later every extraction job | after the beta |
| 7 | Assurance basics: a no-script job profile that also turns off remote plugins, a per-workspace local-only lock (no `local_only` code exists today), an SBOM and a data-flow statement. Signed and notarized builds already ship | S–M + M | every regulated buyer | after the beta |
| 8 | Row-by-row runner: the app retrieves per row, the model answers under a schema, the engine writes; resumable, with progress, a cost cap and an exceptions list | L | the local path for the questionnaire; becomes the per-file batch runner | after the beta, or earlier if item 2 fails on context, cost or missed rows |
| 9 | Local model rows: Qwen3.8-27B as GGUF, Nemotron 3.5 Bolt 74B-A9B and E4B, one 8–14B model through the runner | S–M + hardware | every "local" claim | when a 24–32 GB machine exists ([README](../../../docs/proposals/file-agent/README.md) chases one on 1 Dec, unconfirmed) or on a rented GPU |
| 10 | Word Q&A tables filled by cell address, in SurfSense's own Word engine | M | Word questionnaires (9.6%), RFP templates | with the RFP job |
| 11 | Local paid bundles and the job-pack loader: paid plugin code delivered by the licence server only to a valid licence, checked by sha256 and run on the machine, designed in the deferred [bundles proposal](../../../docs/proposals/plugins/bundles/README.md), whose runner, SDK and author CLI are partly built; plus the loader that adds a plugin's skills and job agents ([02 phase 8](../../../docs/proposals/file-agent/02-skills-and-engines.md), `provides.skills`) | M–L + M | every paid job, since 22 Oct 2026 ([ADR 0067](../../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)) | before the questionnaire's beta, in parallel with items 1–5 |
| 12 | Team features: a library shared across installs, roles, approval by a second person, a signed change log, sealed per-client libraries. They need in-app extension points and a writable shared-library location, which would be an exception to [01's decision 9](../../../docs/proposals/file-agent/01-sources-and-folders.md) | M–L + L | both library jobs | later, once the jobs sell |
| 13 | Page-number citations end to end: a page map at ingest across the text layer, OCR and Docling, page markers in the mirror, page cites in output cells (chunks store lines only today) | M | RFP matrices, every extraction job, litigation | after the paid build |
| 14 | Extraction stack: table-preserving PDF reading (M); `analyze_data` reading extracted PDF tables so code moves values (S–M); a tie-out validator with an exceptions sheet (M); batch on item 8 | L in all | statements, then medical records, then registers | about March 2027 |
| 15 | Solicitation shredding into a compliance matrix | L | RFP | on items 13–14 |
| 16 | Later, only when a job needs them: `.eml`/`.msg` ingest (M); legacy `.doc`/`.xls`/`.ppt` via LibreOffice (M); Bates sets (S); burned-in redaction (L); diarization and m4a/mp4 (M+M); compare after the clean-room fix; linked folders (M8, L); a script sandbox before marketing to legal or government buyers | — | second-wave and capability jobs | — |

**One paid-path build at a time.** February to June 2027 would otherwise stack
roughly 25 to 45 weeks of work into 20: page cites, the RFP job, the extraction
stack, team features and linked folders. Since the jobs became paid plugins,
local bundles and the job-pack loader (item 11) come before the questionnaire's
beta rather than after it. After the beta, run the RFP job, then extraction;
team features wait until the jobs sell. Linked folders (M8) slip accordingly.

**Where each piece lives.** The shared builds are the app's: the engines, the
eval harness, the runner, provenance and its checks, per-row review, the answer
library with its import and export, the `library` and `playbook` folder roles,
page citations, the tie-out validator, the assurance basics and the bundle
runtime. They stay free and Apache-2.0, and they improve the free agent too.
Each job's own content is the job plugin's: its skill, agent, workflow steps,
mappings, playbooks, templates, eval cases and gold corpus (item 1's corpus
included), written outside the Apache-2.0 tree from the first commit
([ADR 0067](../../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)).

## How SurfSense earns

Decided 22 Oct 2026
([ADR 0067](../../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)): the free
layer distributes and the paid jobs earn. Decided 1 Nov 2026
([ADR 0079](../../../docs/adr/0079-surfsense-sells-one-business-license-priced-per-person.md)):
the jobs are sold under one paid licence, Business, priced per person. None of
it is built yet, and the pricing page still sells the Individual licence. The
switch is one release, the one that ships the first paid job: Business goes on
sale, the scrapers retire and Individual sales stop together. Until then the
scrapers and the Individual licence stay on sale.

**One paid licence: Business.** Business starts at one person; a one-person
Business licence is shown as "Solo". Anyone who uses a SurfSense job plugin for
work needs it. The job plugins unlock only with a Business licence or the
14-day trial, where ADR 0067 said "Individual, Team, or the 14-day trial". The
Individual licence ($60 the first year, then $120), which carries the scraper
plugins, priority support and one feature build request a year, stops being
sold at the switch. The jobs, in order: the security questionnaire and DDQ first; RFP and RFI
responses; bank statements into a ledger, medical chronologies, and contract
and lease registers; the contract redline against a playbook. Later come firm
controls (a firm-wide policy lock, a local audit log with exports for a WISP
and HIPAA reviews, a people roster) and team features (a shared library,
approval by a second person, sealed client workspaces).

**Price.** A founding price, locked for early customers, and a hypothesis to
test: $200 a year for the first person and $120 a year for each further
person. It replaces the earlier plan of $1,200 a year per firm and the
Individual licence's $60, then $120.

| people | a year |
|---|---|
| 1 ("Solo") | $200 |
| 2 | $320 |
| 5 | $680 |
| 10 | $1,280 |
| 15 | $1,880 |

Whether $200 is the first person's price, as written, or a base fee before $120
for each person is open question m; how many people self-serve covers before a
quoted Enterprise deal is open question k. Two anchors from the 1 Nov 2026
research, both hypotheses: per-user AI tools for lawyers, accountants and
clinicians run about $40 to $150 a month per user, and committed
questionnaire-tool plans start around $3,000 a year. Business sits well below
both.

**Billing.** Business renews automatically every year on the same licence key.
A renewal extends the same Keygen licence; the app fetches the renewed licence
file when online, and an offline machine imports the emailed file. The checkout
states the yearly renewal before payment, and cancellation and seat changes go
through Stripe's emailed customer-portal link, so SurfSense still has no
accounts.

**Trials.** One 14-day trial of the full job, and nothing else: no separate
pilots, and a design partner's trial is extended by hand. Two rules users do
not see: Gmail dots fold into one address, and a company domain gets at most
two trials a year.

**People, not devices.** The firm declares at checkout how many people use job
plugins and confirms the number at renewal. There is no device binding and no
device identifier at launch. Device activation (two computers per person, a
random code per install, never a hardware ID, with consent and an offline path)
is added only if download counts show sharing. Who counts as a person is open
question b; shared servers, offline firms, shared PCs and virtual desktops are
open question c.

**What is free and what is paid.** The app stays free and Apache-2.0,
everything it does today included, with the engines and the shared job
machinery. A licence never disables the app: when a Business licence lapses,
new job runs stop after 30 days, and every file, library and output stays
readable. When the scrapers retire, reading web pages, YouTube transcripts and
web search move into the app, free for everyone, so Add from the web keeps
working without a licence
([ADR 0080](../../../docs/adr/0080-surfsenses-scrapers-retire-and-web-pages-and-search-stay-free.md)).

| free, in the app (Apache-2.0) | paid job plugins (Business licence or the 14-day trial) |
|---|---|
| Q&A with citations, Studio, the general agent and its format skills | the security questionnaire and DDQ |
| every engine: Word revisions as tracked changes, Excel and PowerPoint revisions, PDF tools, OCR, speech-to-text, data analysis | RFP and RFI responses |
| the study pack, and the capability jobs: conversion, comparison, transcription, redaction and organizing as they are built | bank statements into a ledger; medical chronologies; contract and lease registers |
| the shared job infrastructure: catalogue and entry points, eval harness, runner, provenance, per-row review, page citations, tie-out validator, bundle runtime | the contract redline (review against a playbook, the issues list, starter playbooks) |
| the user's own files: libraries, playbooks they wrote, outputs and revised copies open and export without a licence | each job's skill, agent, workflow, mappings, playbooks, templates and eval cases |

**The line between an edit and a job.** A user who asks the general agent to
change their own file, a contract included, still gets a free revised copy with
tracked changes; that is what the free agent does today
([`surfsense-revisions`](../../../surfsense_local/backend/modules/agent/skills/surfsense-revisions/SKILL.md),
live case 9). What is paid is the job: the playbook and the review against it;
the questionnaire's mappings and answer matching. The free skill's
examples name contracts and redlining, so a follow-up rewords them.

**What can be sold, in order:**

1. **The job plugins, under Business.** The trial gives every user the full
   job for 14 days, so the job catalogue in the app is where a business user
   meets the paid layer. Whether every job is included in Business or some are
   add-ons is open question a.
2. **Public-data plugins** inside Business, on the existing plugin host,
   because only queries and public records pass through. One experiment, capped
   at two weeks and built only if the questionnaire is on time: SAM.gov
   opportunities plus USAspending awards (anchor: HigherGov at $500 a year for
   one user, [pricing](https://www.highergov.com/pricing/)). Before building,
   confirm SAM.gov's API terms for proxying (it needs a key and limits calls by
   role), prefer the user's own key or start with USAspending, which needs none,
   and publish what the plugin host logs about queries.
3. **Firm controls and team features, later, in Business, once the jobs
   sell:** a firm-wide policy lock that users cannot override (the
   per-workspace lock is free), a local audit log with exports for a WISP and
   HIPAA reviews, and a people roster; then a library shared across installs,
   roles, approval by a second person, a signed change log, and sealed
   per-client workspaces for MSPs and vCISOs, synced through the customer's own
   SharePoint, OneDrive, share or Git, so no SurfSense server is involved. The
   per-person price replaces the earlier test prices, about $1,200 a year per
   team and $2,400 per MSP. The MSP segment is unproven: no source yet shows
   MSPs answering client questionnaires in volume.
4. **Enterprise, quoted.** The assurance basics (item 7) are published free as
   proof. Enterprise adds a third-party code audit on the
   [Obsidian/Cure53 model](https://obsidian.md/security) (a first SOC 2 Type II
   costs $30K to $110K), named support and invoicing; the firm-wide policy lock
   and the audit log, Enterprise items before 1 Nov 2026, are now planned as
   Business's firm controls. Where self-serve Business ends and a quoted deal
   begins is open question k. No validated price exists yet.
5. **Paid setup through partners only.** MSPs, vCISOs and proposal
   consultancies bill their own clients for building a library or migrating
   from Loopio or Responsive; SurfSense supplies licences.

**Enforcement.** Job content cannot be kept secret from a licensee: the agent
reads it as plain text, and its prompts reach the model. A licence check in the
open-source app can be stripped by any fork
([ADR 0019](../../../docs/adr/0019-offline-licenses.md)). What holds is
delivery, since the licence server serves a job plugin and its updates only to
a valid Business licence or trial; the licence terms, under which the firm
declares how many people use the jobs; and the firm's name, shown on job
screens. There is no device binding at launch. The Business Source License used
for the remote plugins grants production use to anyone who does not resell the
work, which would let a business run a local job plugin without paying; closed
terms for the job content are open question e, and the lawyer who drafts the
terms is open question g.

**Existing buyers.** Individual licences already sold keep what they bought
until the switch, and their holders get a short notice that the scrapers
retire. At the switch, each becomes Business Solo on the same key and keeps
renewing at the price it was bought at, locked, as an early customer, with a
notice email when converted and a reminder before each renewal. Whether
Individual licences sold before the switch get the same treatment is open
question q. Hand-issued Team licences are open question l.

**Not now.** Bundled model access (a relay in the data path, thin margins, and
Claude and ChatGPT plans already work through the app); connectors to document
and practice systems before local bundles exist, because today's plugins run
only as remote MCP servers
([`list_entry.py`](../../../surfsense_local/backend/modules/plugins/lists/list_entry.py)
offers HTTP and SSE transports only; bundles, the kind that runs on the user's
machine, are [deferred](../../../docs/proposals/plugins/bundles/README.md)), so
a connector would route client files through SurfSense; and a standalone
assurance-pack product, for which no buyer evidence was found. Once item 11
exists, connectors can ship as local paid plugins like the jobs.

**What $100K a year would take.** At the founding price, 500 Solo licences,
about 150 five-person firms ($680 each) or about 80 ten-person firms ($1,280).
It is a target for the checks below, not a forecast.

## Pages and reach

**Pages**, each published only after a committed eval row:

- **HECVAT 4** (`hecvat` 2,400 at $27, KD 9), **CAIQ v4** (1,000, KD 16; Vanta
  ranks #3) and **SIG Lite** (320 at $65, read from the user's licensed copy).
- A guide: answering a security questionnaire in your own spreadsheet, from
  your own policies. It has no measured volume; it serves partners and links.
- Security policy templates mapped to SOC 2 and ISO controls, as the evidence
  base ($85K, but −26% raw; pull their SERPs first).
- **A factual Claude Cowork alternative page, now**, describing shipped
  features only: `claude cowork alternative` is 1,005 a month in clickstream at
  $25.58, SurfSense is absent from the SERP, and `claude cowork linux` is 955
  and rising. It claims no job, so the eval-row rule does not hold it back.
- A "which model can do which job" page generated from the eval matrix.
- After the RFP job: an RFP response page (`rfp response` 590, KD 3; small
  sites rank), and a compliance-matrix page once page cites ship.
- Skip: `soc 2 report`, third-party risk management, the generic DDQ head,
  CMMC timing pages, and blank proposal or quote templates.

Expected traffic is a few hundred to low thousands of visits a month, an
assumption under a ceiling of about 5,000 US searches.

**Channels**, all opt-in:

- The free layer through organic search, user posts and creators: the Cowork
  alternative, decks and reports from the user's files, converters, OCR and
  transcription. Its outputs are not confidential, so people can show them. In
  the app, the job catalogue offers each paid job with its 14-day trial.
- Ten design partners (five MSP, MSSP or vCISO firms; five security or IT
  leads at 20 to 500-person software vendors) and two proposal managers or
  consultancies, recruited through a call in the README and GitHub
  Discussions, release notes, a signup form on the site and in the app, and
  email to licence holders. Cold email to GitHub stargazers breaks GitHub's
  [acceptable use policies](https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies)
  and is not used.
- MSP and vCISO referrals; proposal consultancies as setup partners.
- The open-source repo (16,562 stars): the app, the engines and the shared job
  infrastructure. The job plugins' source sits outside the Apache-2.0 tree.
- The Show HN, which the maintainer posts the week of 22 Oct 2026, and later a
  recorded walkthrough of a HECVAT fill.
- Store listings: Windows was 68% of 2.0.x downloads and the app was in no store
  on 29 Sep; re-check before submitting to winget and the Microsoft Store.

**Proof.** The gold set at n=3, published with failures: at least 90% correct,
no unsupported "Yes", every answer sourced from the ticked scope, every write
valid for its dropdown, the file opening in Excel and LibreOffice with
validations and macros intact, and measured cost and minutes per
questionnaire. Models: Sonnet 5.5, Claude through the user's Claude Code plan, a
ChatGPT plan, and locally Qwen3.8-27B, Nemotron 3.5 Bolt and one 8–14B model in
row-by-row mode.

**Measurement.** The opt-in, ID-less usage counters, per-licence plugin call
counts, website download, trial and purchase events and the Keygen×Stripe
cohort report were decided on 21 Oct 2026 and are being built. Add a counter
for a questionnaire job run, a coupon or referral link per partner, UTM tags on
every outbound link, and one optional "how did you hear" question before
checkout, so channels can be credited without an install ID.

## The next 90 days

The timeline recommended on 1 Nov 2026, open question j's default: no paid
sale before the questionnaire passes the quality bar in the
[kill criteria](#kill-criteria); free trials with design partners in December,
once the job's eval harness and gold set (item 1) exist; and the paid launch
with the beta, about mid-January 2027. Two scopes fit the beta; the maintainer
chooses one (open question j):

- **Minimum beta, about mid-January 2027:** items 1 to 5 (harness and corpus,
  baseline, inspection and validation, provenance, library with import).
  Per-row review, assurance basics and the data plugin follow.
- **Full beta, about mid-February 2027:** items 1 to 7.

Both dates were set while the job was to ship inside the app. As a paid plugin
it also needs item 11, local paid bundles and the job-pack loader (about M–L
and M, estimates). The dates hold only if item 11 runs beside items 1 to 5;
re-date both once the harness lands.

Either way:

- **By 31 Oct.** Record the order change in
  [`file-agent-strategy.md`](../file-agent-strategy.md); correct the copy that
  names Conveyor at $9,600, says file editing is "offered by nobody credible"
  or uses CMMC timing; ask CSA and EDUCAUSE in writing about question text; ask
  the lawyer whether the provenance review still gates selling a job that ships
  no `docxkit` or `crlib` code, and which licence terms a local job plugin
  needs (open questions e and g).
- **From November.** Item 11 beside items 1 to 5: the licence server's route
  for paid bundles, install and update, and the job-pack loader. The
  questionnaire's job content goes into its plugin folder from its first
  commit. The scrapers and the Individual licence stay on sale until the
  switch; whether the Individual page and purchase email say from now that the
  licence becomes Business Solo at the switch is open question q.
- **By 15 Nov.** Publish the Cowork alternative page. Open the design-partner
  call (open questions h and i). Ship the harness and corpus and commit the
  baseline rows, failures included.
- **Through December.** Items 3 to 5 in point releases; local rows once a 24–32
  GB machine or rented GPU is confirmed. Once the harness and gold set exist,
  design partners run the job on their own questionnaires on the 14-day trial,
  extended by hand.
- **Before the first sale.** The licence server's Stripe webhook handles only
  the first checkout and full refunds today. It must handle `invoice.paid`, or
  an auto-renewal charges without extending the licence, and trace a refund of
  a subscription charge to its licence. Business gets new Keygen policies: the
  Keygen CE v1.7.2 that production runs has everything needed, and the live
  trial, individual and team policies are never edited or made strict, because
  the plugin host accepts only `VALID` and every existing key would be locked
  out. The licence server moves from the admin token to a product token, and
  validates a licence before any machine creation or file check-out, since
  Keygen does not check licence status there for admin or product callers. The
  app learns to fetch a renewed licence file. The purchase email's "The app
  never contacts a license server" and "works on every machine you install
  SurfSense on", `/pricing/individual` and `/license/activate`, which say every
  computer, and the pricing FAQ's "a single payment, not a subscription" are
  rewritten; the privacy page's "does not compute or transmit a device
  fingerprint" stays true, since there is no device identifier. Open questions
  g and m are answered first.
- **At the beta: the switch,** if the job has passed the quality bar;
  otherwise the beta stays with design partners, and the scrapers stay on sale,
  until it does. In one release the job ships as a paid plugin under Business
  on frontier models with an n=3 row, the platform scrapers retire
  ([ADR 0080](../../../docs/adr/0080-surfsenses-scrapers-retire-and-web-pages-and-search-stay-free.md)),
  Individual sales stop, and Individual holders get a notice and become
  Business Solo ([above](#how-surfsense-earns)). The pricing FAQ's line that a
  licence is only needed for the scraper plugins and priority support, and
  Terms section 5, which says a licence adds the scrapers and gates nothing
  else, change in that release.
- **About six weeks after the beta.** Run the quality and pay checks below;
  if they pass, publish the questionnaire pages and the model page, and
  decide whether the RFP job starts.

## Kill criteria

| check | when | if it fails |
|---|---|---|
| **Quality:** the Sonnet 5.5 row on the gold set is at least 90% correct, with no unsupported "Yes" and no broken dropdown or macro, after two fix cycles | about six weeks after the beta | no job pages; the beta stays with design partners; fix or demote the lead |
| **Pay intent:** at least 3 design partners commit in writing to buy a Business licence for the job at the founding price when their trial ends | about six weeks after the beta | re-check the price and the job before building the next paid job; the job stays a plugin |
| **Conversion:** at least 15% of business users who start the job's trial buy a licence, and $15K of new annual revenue from all sources | 30 Jun 2027 | stop adding paid jobs beyond the questionnaire and re-rank the bets |
| **Local claim:** a locally served model of 24 GB class or less reaches 80% correct with no unsupported "Yes" in row-by-row mode | 31 Mar 2027 | no "fully local" questionnaire claim; state the frontier-model requirement; drop CUI and PHI positioning |
| **Search:** core questionnaire clickstream averages at least 4,700 for October to December; the HECVAT and CAIQ pages reach Google's top 10 within 90 days and 100 clicks a month by day 120 | January re-pull; 90 and 120 days after publishing | keep only the HECVAT and CAIQ pages; move reach to partners. Above 6,000, add SIG Lite and PCI SAQ pages |
| **Absorption:** Microsoft, Anthropic or Google ship a questionnaire skill with a persistent library that keeps dropdowns and macros intact, or Vanta gives questionnaire automation away in its base plans | watch | demote the lead to second wave; lead with model choice, the owned library and local processing |
| **Format drift:** design partners report more than 40% of questionnaires arriving through portals | partner calls | re-scope before building past the beta |
| **RFP:** the RFP job cannot reuse the library within about four weeks of work, or no proposal manager joins as a partner | 30 Apr 2027 | RFP stays second wave |
| **Data plugin:** at least 5% of active licences call the GovCon plugin weekly | 60 days after launch | build no further data plugins |
| **Reuse:** each shared build (runner, provenance, library, page cites, tie-out validator) is reused by a second job | within eight weeks of shipping | stop job-specific work on the lead that needed it and re-rank |

**Swap rules.** Bank statements replace a failed lead if an extraction eval
shows at least 99% row recall with every statement tying out on a local model of
24 GB or less, and a test statements page reaches Google's top 5 within eight
weeks. Medical records replace it if a 24 GB-class local model passes a 500 to
1,000-page synthetic chronology at 95% row recall with every page cite valid,
and at least three PI or legal-nurse firms commit in writing to buy a Business
licence for it at its price (open question a).

## Open questions for the maintainer

Settled on 22 Oct 2026: the B2B jobs are paid plugins
([ADR 0067](../../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md)), which
answers where the paid line falls; and the maintainer posts the Show HN that
week.

Settled on 1 Nov 2026:

- **One paid licence, Business,** from one person ("Solo"); the Individual
  licence stops being sold at the switch
  ([ADR 0079](../../../docs/adr/0079-surfsense-sells-one-business-license-priced-per-person.md)).
- **One switch:** Business goes on sale, the scrapers retire and Individual
  sales stop in one release, the one that ships the first paid job; until then
  the scrapers and the Individual licence stay on sale
  ([ADR 0079](../../../docs/adr/0079-surfsense-sells-one-business-license-priced-per-person.md),
  [ADR 0080](../../../docs/adr/0080-surfsenses-scrapers-retire-and-web-pages-and-search-stay-free.md)).
- **A job plugin unlocks only with Business or the 14-day trial,** and anyone
  who uses one for work needs Business
  ([ADR 0079](../../../docs/adr/0079-surfsense-sells-one-business-license-priced-per-person.md)).
- **A founding price,** to test: $200 a year for the first person and $120 for
  each further person
  ([ADR 0079](../../../docs/adr/0079-surfsense-sells-one-business-license-priced-per-person.md)).
- **Yearly automatic renewal on the same key,** with cancellation and seat
  changes through Stripe's emailed customer-portal link, and no accounts
  ([ADR 0079](../../../docs/adr/0079-surfsense-sells-one-business-license-priced-per-person.md)).
- **One 14-day trial of the full job,** and no separate pilots
  ([ADR 0079](../../../docs/adr/0079-surfsense-sells-one-business-license-priced-per-person.md)).
- **People, not devices,** declared at checkout and confirmed at renewal, with
  no device binding or device identifier at launch, and the firm's name on job
  screens
  ([ADR 0079](../../../docs/adr/0079-surfsense-sells-one-business-license-priced-per-person.md)).
- **Individual licences already sold become Business Solo** on the same key at
  the switch, renewing at the price they were bought at, locked
  ([ADR 0079](../../../docs/adr/0079-surfsense-sells-one-business-license-priced-per-person.md)).
- **Seven platform scrapers retire,** and reading web pages, YouTube
  transcripts and web search move into the app, free for everyone, with search
  through SearXNG and the Google scraper dropped; settled 2 Nov 2026, which
  answers what was open question d
  ([ADR 0080](../../../docs/adr/0080-surfsenses-scrapers-retire-and-web-pages-and-search-stay-free.md)).
- **Unchanged:** the app stays free and Apache-2.0, an edit is free and a job
  is paid, and a licence never disables the app
  ([ADR 0079](../../../docs/adr/0079-surfsense-sells-one-business-license-priced-per-person.md)).

The four questions open since 22 Oct 2026, which other documents cite by
number: 1, a local job plugin's licence terms, is now e and g; 2, what a
business pays, was settled on 1 Nov; 3, the beta's scope, folds into j, whose
default is the minimum beta about mid-January; 4, a writable shared-library
location for team features, stays open for later as
[01's open question 10](../../../docs/proposals/file-agent/01-sources-and-folders.md#open-questions).

Still open, each with its recommended default:

- **a. Is every job included in Business, or is each job an add-on?**
  Default: all included.
- **b. Exactly who counts as a person?** Default: anyone who runs a job plugin,
  or has the agent use one, for the organization, employees and contractors
  alike, counted at the busiest month.
- **c. How do shared servers, offline and air-gapped firms, shared PCs and
  virtual desktops count?** The Docker server image is published on every `v*`
  tag, and [docker.md](../../../docs/architecture/docker.md#data-and-license)
  says one licence works on a desktop and a server. Default: count people; a
  shared server needs a licence for two or more people; offline firms pay the
  same price.
- **d. Where do the kept crawler and search run?** Settled 2 Nov 2026: inside
  the app, so the user's machine fetches pages and transcripts; search defaults
  to SurfSense's hosted SearXNG, with a setting for the firm's own.
- **e. Does job content live in a private repository, shipped as signed packs
  under a closed Job Plugin License, with old pack versions published as open
  source after 12 to 24 months?** The Business Source License, FCL, ELv2 and
  PolyForm Noncommercial all allow redistribution. Default: yes.
- **f. A sunset clause?** If SurfSense stops selling Business licences, firms
  keep running the packs they have, backed by a pre-signed licence held
  outside the company. Default: yes, on shutdown only; Enterprise may
  negotiate keeping old versions after any lapse.
- **g. The lawyer: who, on what budget, and which governing law, US first?**
  The work is the Business terms, with audit and true-up clauses, and the Job
  Plugin License. Default: the Business terms and the Job Plugin License
  first.
- **h. Who is the questionnaire job priced for?** CPA and law firms, or the
  MSPs, vCISOs and software vendors this plan names. Default: CPA and law
  firms.
- **i. Who recruits the first 3 to 5 design partners, and by when?** Default:
  start with existing licence holders who work with confidential client files.
- **j. Paid sales before the questionnaire passes this plan's quality bar?**
  Default: no; trials with design partners in December, and the paid launch
  with the mid-January beta.
- **k. Self-serve up to how many people before a quoted Enterprise deal?**
  Default: 15.
- **l. Do any hand-issued Team licences exist, and what do they become?**
  Default: they keep working to expiry and are offered Business at renewal.
- **m. Is $200 the first person's price, as written, or a base fee before
  $120 for each person?** Default: the first person's price.
- **n. Does Business include the priority support and the yearly feature build
  request that Individual carries?** Default: yes.
- **o. Where does the app fetch a renewed licence file from?** Default:
  SurfSense's licence server, so the app still never contacts Keygen
  ([ADR 0019](../../../docs/adr/0019-offline-licenses.md)), with the call
  described on the privacy page.
- **p. What does Enterprise keep once firm controls move into Business?**
  Default: more than 15 people, a site licence, an internal mirror, virtual
  desktops, a DPA, the third-party code audit, named support, invoicing and
  negotiated terms.
- **q. Do Individual licences sold before the switch also become Business Solo
  at their price?** Default: yes, and the Individual page and purchase email
  say so from now, so no new sale commits SurfSense to running the scrapers for
  a year under Terms section 5.
- **r. Are the scrapers frozen until the switch, kept running with no new
  fixes?** Default: yes.

## What would change the answer

- **A questionnaire skill from a suite vendor** with a persistent library and
  intact workbooks (the absorption check).
- **A local model that passes long-document jobs.** It would make "local" true
  for regulated buyers and could promote medical records or statements.
- **Design partners' answers** on portals versus files, on MSP volume, and on
  what they would pay.
- **The summer step persisting.** Each month it lasts adds another inflated
  month to Google's 12-month averages. Re-pull after the November data.
- **Clickstream's panel** over-represents technical users and puts AI-tool and
  brand terms 5 to 20 times above Ads, so format-agent and Cowork figures are
  nearer a ceiling than a floor.
- **Judgment calls.** The term labels, the exclusions, the cores and the mapping
  of use cases to plays live in `use-cases.json`.
- **US only.** Nothing here was pulled abroad.

## Re-running

```bash
cd plans/community-local/seo/data/b2b-oct
python rollup.py --self-check   # the rollup's tests
python rollup.py                # every table: 135 use cases, plays, cores, free-tool and brand demand, Sep vs Oct
python rollup.py --top 40       # the use-case table cut to 40 rows
python rollup.py --json out.json
```

The September rollup still runs from [`data/b2b/`](data/b2b/) and is what the
"29 Sep" columns compare against. The call shapes, file list and labelling
method are in [`data/README.md`](data/README.md#b2b-file-jobs-october-2026).
