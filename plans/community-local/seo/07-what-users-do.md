# What people actually use SurfSense for

The demand documents in this folder ([`01-keyword-research.md`](01-keyword-research.md)
and its companions) measure what strangers type into Google. This one measures
what our own users typed into the product, and it exists because the two
disagree about who the product is for.

**Source:** the hosted production database, read-only, 17 Sep 2026. Chat content
only — thread titles and user-role messages. Connector counts, document types
and upload volumes are deliberately excluded: they measure which integrations
Cloud happened to ship, not what anyone wanted.

**Corpus:** 29,591 threads and 251,866 messages between 5 Nov 2025 and 17 Sep
2026, 126,571 of them user-authored.

## The headline

Among users who state a task at all, **professional work outnumbers study by
about 1.8 to 1**, and the single most common thing anyone does is **turn a
document they already have into a deliverable** — a deck, a report, a briefing,
an infographic, a podcast.

The page plan in [`02-page-briefs.md`](02-page-briefs.md) writes almost every
Studio page for a student. The features are right. The reader is wrong.

## How this was counted, and why it is not a message count

Three corrections separate this from a naive query.

**1. Count users, not messages.** Traffic is power-law: the top 10 accounts are
11.3% of all user messages and the top 100 are 31.3%, against a mean of 11.2 and
a **median of 3**. A message-weighted share measures a handful of heavy accounts.
The largest single one is generating Spanish-language alternative-history
football content — thousands of messages about Sergio Ramos signing for Boca
Juniors, with images and podcasts. Real usage, but it is one person's hobby and
it would otherwise outweigh several hundred law firms. Every share below counts
a user once per domain no matter how much they send.

**2. Exclude users who never state a task.** 56% of users with a message, and
77% of users with a titled thread, only greet the assistant or ask what it can
do — "Greeting", "Greeting in Persian", "AI Capabilities Overview", "what can u
do are like notebook but worst". Leaving them in the denominator deflates every
real share. They are reported here and then excluded.

**3. Read the corpus before classifying it.** The first pass used a
hand-written English taxonomy and matched 5-7% of rows, which is a statement
about the taxonomy rather than the users. The classifier was rebuilt after
reading 170 random thread titles, one per user. That read is also the accuracy
check on the numbers below.

The classifier is still keyword rules over short strings, so **treat these as
well-calibrated estimates, not measurements**. Two independent cuts — thread
titles, which are model-written summaries of intent, and raw user queries — are
reported separately; where they agree, the finding is safe. They agree on the
ratio that matters.

**To reproduce.** The analysis scripts were deliberately not committed — they
read production directly and there is no reason for that to live in the repo —
so the method is written out here instead. Two read-only queries against the
hosted Postgres:

```sql
-- thread titles, one row per titled thread
select created_by_id, created_at::date, left(title, 200)
from new_chat_threads where title is not null and title <> '';

-- user turns, truncated: some messages are whole pasted documents
select author_id, created_at::date,
       left(regexp_replace(content->0->>'text', '\s+', ' ', 'g'), 300)
from new_chat_messages where role = 'USER' and content->0->>'text' is not null;
```

Then, in any language: group by user id; drop users whose only rows match the
greeting/capability patterns; apply the domain patterns to each remaining user's
rows; count each user **once per domain**. The domain patterns are the list in
"What people do" plus the non-English terms for the same jobs — the corpus is
majority non-English and an English-only pattern set undercounts by roughly half
in the professional domains. Sample 170 titles at random, one per user, and read
them before trusting any of it.

## What people do

Share of users who stated a task. A user can appear in more than one row.

| domain | by thread title | by query | |
|---|---|---|---|
| **content_creation** | **42.7%** | **42.9%** | deck, report, podcast, infographic, mind map, image |
| study_learning | 21.5% | 31.0% | exams, flashcards, chapters, coursework |
| engineering | 11.8% | 17.6% | * |
| sales_marketing | 7.2% | 14.0% | * |
| consulting_reports | 6.0% | 9.7% | * |
| healthcare | 5.0% | 9.0% | * |
| legal | 4.8% | 8.3% | * |
| finance_accounting | 4.9% | 7.1% | * |
| meetings_email_ops | 3.5% | 7.0% | * |
| creative_entertainment | 6.8% | 5.9% | roleplay, fiction, fan content |
| government_policy | 1.4% | 3.0% | * |
| **any professional domain** (*) | **39.7%** | **52.7%** | |

Base: 2,410 users by title, 4,840 by query. Professional-to-study is **1.8:1**
on titles and **1.7:1** on queries.

Study is not small and nothing here argues for dropping it. It argues against
leading with it.

## The deliverable job, in users' own words

This is the 43%, and it is not homework. Lightly trimmed, one per user:

- "Create a slide deck and a narrated video overview from these sources"
- "core idea should be professional technical for clear presentation that CEO of
  brokerage companies can understand it"
- an electrical specialist drafting a response to a numbered inspection report
- "Campaign Brief / Creative Deck — Purpose: inspire stakeholders with a visual,
  concise, storytelling-driven overview of your campaign's creative direction"
- a Persian request for a stakeholder infographic for a 48-unit housing
  cooperative
- a French documentary bundle justifying the technical organisation of a carbon
  study meeting
- "@الزراعة الذكية.docx make a powerful presentation"

And the professional domains are genuinely professional. From legal:

- a CCMA arbitration evidence bundle, indexed and paginated, asked for on the
  free tier by a disabled applicant
- a Russian contractor checking whether a US service agreement can pay in USDT
- a Canadian immigration sponsorship matter
- a law firm's letter in a building dispute, over keys a contractor failed to
  return by the deadline in a notice
- a code of conduct reviewed against the Corporations Act and anti-discrimination
  law

**The shape is always the same: a file goes in, a professional artefact comes
out.** That matters for what can honestly be promised, because it is exactly
what the local app does — `DocumentType` is `FILE`, `NOTE`, `ARTIFACT`, and
uploads are PDF, DOCX, PPTX, XLSX, HTML, CSV, MD, TXT and images. No connector
is needed for any request quoted above.

## Two things the docs currently get wrong

**YouTube ingestion does not exist in the local app.**
[`01-keyword-research.md`](01-keyword-research.md) says "the app ingests
YouTube, so the sources page gets an H2 for it", and
[`02-page-briefs.md`](02-page-briefs.md) lists YouTube lectures as a study-guide
source. There is no YouTube handling anywhere in the app's source — the string
appears only in the bundled tokenizer's vocabulary and in third-party packages
inside build output. That was a Cloud capability. Both claims are corrected in
place.

**"OpenAI Proxy" is a real and unplanned usage mode.** 1,367 workspaces are
named "OpenAI Proxy Space" and 730 threads are titled "OpenAI Proxy" — people
using SurfSense as an OpenAI-compatible gateway rather than as a notebook. Out
of scope by decision, recorded so it is not rediscovered as a surprise.

## What the demand data says about the deliverable job

Pulled 17 Sep 2026, Google US desktop (`location_code: 2840`,
`language_code: en`), same method as the rest of the folder. Archived as
`data/keyword-overview-deliverable.json`,
`data/keyword-ideas-deliverable.json.gz` and
`data/keyword-overview-workintercept.json`. `legal ai` is the one figure below
that comes from the discovery pull rather than an overview pull.

### The literal phrasing has no demand

The obvious words for this job are almost unsearched:

| keyword | volume | kd | cpc |
|---|---|---|---|
| pdf to presentation | 110 | 19 | 2.89 |
| document to presentation | 10 | 75 | 0 |
| ai presentation from pdf | 10 | 69 | 13.65 |
| automate report writing | 10 | — | 0 |
| talk to your documents | 10 | — | 0 |
| chat with documents | 40 | 31 | 6.09 |

The "chat with X" family keeps shrinking — `chat with pdf` is 390 and down 76%,
confirming what `01` already says. **Nobody searches for the mechanic.** Do not
build a page around "turn your documents into a deliverable" as a phrase; build
it around who the reader is and what they are afraid of.

### The NotebookLM-at-work intercept does not exist

Worth recording because it is the obvious idea and it is wrong:

| keyword | volume |
|---|---|
| notebooklm enterprise | 320 |
| notebooklm for business | 30 |
| notebooklm business | 30 |
| notebooklm for research | 50 |
| notebooklm for work / for lawyers / data security | 10 each |

No page. People worried about confidentiality at work do not phrase it as a
NotebookLM question.

### What does have demand: privacy, qualified by "for business"

| keyword | volume | kd | cpc | history |
|---|---|---|---|---|
| **ai workspace** | 2900 | **12** | 17.86 | 320/mo a year ago, peaked 8,100 in Apr 2026, now 1,300-1,600 |
| **private ai for business** | 1600 | — | — | 10-260/mo until May 2026, then 1,900 → 5,400 → 12,100 |
| secure ai for business | 2900 | **16** | — | 10/mo until Jun 2026, then 8,100 → 27,100 |
| ai knowledge base | 880 | 28 | **61.34** | stable 590-1,300 all year |
| document ai | 1900 | 29 | 14.53 | stable, −32%; partly Google's product name |

`private ai for business` has **three consecutive months** of growth and is the
safest of these. `secure ai for business` has **two**, which by this folder's own
rule ("a row whose `recent` still equals `volume` has held for three months") is
not yet proven — it is a candidate, not a plan. Both sit directly on top of the
privacy cluster `01` already identified as the landing page's addressable
demand, which is the useful part: **this is not a new strategy, it is the
existing one with a business qualifier.**

### And the professions, which is where the money is

The user decision for this pass was cross-cutting pages rather than verticals.
The data does not contradict that choice so much as complicate it, and the
complication should be on the record:

| keyword | volume | kd | cpc | history |
|---|---|---|---|---|
| legal ai | 18100 | 38 | 29.54 | stable 14,800-22,200 all year, +22% |
| ai for accountants | 6600 | 29 | **36.40** | stable 5,400-9,900, −18% |
| ai for lawyers | 2400 | 30 | **55.59** | stable 1,900-2,900, −17% |
| ai for small business | 2900 | 31 | 25.63 | 1,000 → 12,100 over the year |
| ai contract review | 880 | 19 | **66.60** | stable, +14% |
| ai for compliance | 480 | 22 | **66.03** | 50-110 until May, then 1,000-1,900 for three months |
| ai for professional services | 210 | **2** | **64.86** | two months only; top 10 average **6.1** referring domains |
| ai for audit | 170 | **8** | 30.06 | two months only |
| ai for consultants | 210 | 26 | 31.36 | two months only |

`ai for lawyers` and `ai for accountants` are durable, mid-difficulty and carry
$36-56 clicks. They are five to twenty times the volume of any cross-cutting
deliverable phrasing, and nothing else in this research comes close on CPC.

**The reconciliation, and it is not a fudge:** one cross-cutting page can carry
these terms as sections without becoming ten vertical pages. The job is
identical across professions — confidential file in, professional artefact out —
so the page argues the job once and names the professions as proof, in copy and
in H2s. That captures the profession vocabulary without ten legal reviews and
without ten thin pages. If a single profession later earns its own page on
measured traffic, `ai for lawyers` is the one to promote first.

## International: the tension, resolved

Your users are majority non-English — 18% of thread titles and 21% of queries
contain non-Latin script before counting Spanish, Portuguese and French, which
are Latin-script and very common. [`03-international.md`](03-international.md)
concludes the US is 68% of the value index and defers localisation. Both are
true, and they are not in conflict: **users are not searchers, and searchers are
not buyers.**

Professional terms pulled in three non-English markets, same day and method:

| market | best professional term | volume | kd | cpc |
|---|---|---|---|---|
| Spain (`es`) | ia para abogados | 390 | 15 | 5.34 |
| Mexico (`es`) | ia para abogados | 480 | **1** | 1.43 |
| Brazil (`pt`) | criar apresentação com ia | 2900 | **7** | 1.66 |
| Brazil (`pt`) | ia para contadores | 320 | — | 2.59 |
| Brazil (`pt`) | ia para empresas | 390 | — | **12.15** |

Against `ai for lawyers` at 2,400 and **$55.59**, `ia para abogados` is 480 at
**$1.43**. Volumes run an order of magnitude lower and clicks are worth a
twentieth. **The US-first conclusion holds and should not be revisited on the
strength of the user mix.**

One cheap exception is worth taking. The Brazilian privacy terms are growing
fast against almost no competition:

| keyword | volume | trend | referring domains in top 10 |
|---|---|---|---|
| ia local | 480 | **+614%** | **1.2** |
| ia offline | 390 | **+182%** | **0.3** |
| ia para documentos | 210 | +191% | 24.7 |
| notebooklm em português | 1600 | +53% | 1,057 |

A top-10 average of 0.3 referring domains means effectively nobody is competing.
That is a translation of a page that will exist anyway, not a localisation
programme — it belongs in the `hreflang` work `03` already plans, with
Portuguese promoted ahead of Japanese and German on cost-to-win rather than on
market size.

Spain and Mexico were pulled but are not archived, matching the convention in
[`data/README.md`](data/README.md#not-saved-here); the call shape is one
`keyword_overview/live` per market and the figures above are the result.

## What this changes

1. **Reframe the Studio pages for the professional deliverable buyer**, keeping
   one study hub as a seasonal page. The features do not change; the reader,
   title tags, H2s and examples do. Specified in
   [`02-page-briefs.md`](02-page-briefs.md).
2. **Add the business qualifier to the privacy cluster** on the landing page —
   `private ai for business`, `ai workspace` — rather than opening a new front.
3. **Name professions inside the cross-cutting page** to capture `ai for
   lawyers` / `ai for accountants` vocabulary without vertical pages.
4. **Do not build** a NotebookLM-at-work page, a "chat with your documents"
   page, or a page targeting the literal deliverable phrasings.
5. **Keep the US-first plan**, and add Portuguese to the cheap end of the
   `hreflang` list.
6. **Correct the YouTube claims** in `01` and `02`.

## What would change the answer

- The classifier is keyword rules; a labelled sample scored by hand would move
  these shares by a few points in either direction. The 1.7-1.8:1 ratio is
  robust to that, the individual domain shares less so.
- `secure ai for business`, `ai for consultants`, `ai for audit` and `ai for
  professional services` are each two months old. Re-pull before committing a
  page to any of them.
- The corpus is Cloud usage, and Cloud shipped connectors the local app does not
  have. Connector-shaped demand is excluded here by instruction, but a local app
  with no Gmail will not retain the subset of these users whose job depended on
  it. That is a product risk, not an SEO one, and it is not sized in this
  document.
