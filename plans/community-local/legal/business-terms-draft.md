# Terms for the Business licence: a draft for counsel

**Status: draft, not live.** Written 3 Nov 2026, revised 4 Nov 2026 for ADR 0083, for the lawyer who drafts the Business terms
and the Job Plugin License. Nothing here is on the site: the live
[Terms page](../../../www/app/\(home\)/terms/page.tsx) keeps its 22 Oct 2026 text until counsel
signs off, and the new text goes live in the release that ships the first paid job. The site
has had no Business switch since 10 Nov 2026, so that release is the day Business goes on
sale, and the new text must be ready before it.

**Sources.** The decisions are ADR 0080 (one Business licence, priced per person) and ADR 0081
(the scrapers retire; reading web pages, YouTube and web search move into the app), both in
[PR #2391](https://github.com/MODSetter/SurfSense/pull/2391). They amend
[ADR 0019](../../../docs/adr/0019-offline-licenses.md) (offline licences) and
[ADR 0067](../../../docs/adr/0067-b2b-jobs-ship-as-paid-plugins.md) (jobs as paid plugins), and
keep [ADR 0024](../../../docs/adr/0024-portal-without-accounts.md) (no accounts).
[ADR 0083](../../../docs/adr/0083-the-founding-price-can-change-at-a-renewal-with-notice.md) (4 Nov 2026) amends ADR 0080: the founding price
can change at a renewal, after at least 30 days' notice by email. The site's
Business copy, behind the switch, is in `www/app/(home)/pricing/`.

**How to read it.** For sections 5 and 6, today's text comes first, quoted from the live page,
then the proposed text. Brackets mark a choice for the maintainer or a question for counsel.
Where a line rests on one of ADR 0080's open questions, its letter is given; the recommended
default is written in.

## What changes, in short

- The only paid licence is **Business**. It unlocks SurfSense's job plugins, the security
  questionnaire first. The Individual licence is no longer sold, and the scraper plugins
  retire.
- Business is **priced per person**: $60 a year for each person, the first included, a
  founding price that can change at a renewal after at least 30 days' notice by email.
  One person is shown as "Solo".
- It is a **yearly subscription** that renews automatically on the same licence key, where
  today's licences are single payments.
- **Cancellation and seat changes** go through Stripe's customer portal, from a link sent by
  email. There is still no SurfSense account.
- People are counted **by contract**, as the number the firm declares, with no device
  identifier.
- When a Business licence **lapses**, new job runs stop after 30 days. Files stay readable and
  the app never stops.

## Section 5: Licences, trials, payment and refunds

### Today

> The application and its updates are free. A licence adds the scraper plugins and priority
> support and gates nothing else. You can start with a 14-day licence on an email address
> without giving us a card. Paid licences are sold through Stripe, and team licences are
> arranged by email.
>
> A licence is verified on your own machine against a cryptographic signature, so it keeps
> working offline. Do not share, resell or publish your licence file, and do not attempt to
> defeat the check. A licence is for the person or organisation it was issued to.
>
> When a licence expires, the plugins and priority support stop. The application and every
> future version of it keep working, and nothing you created with it is locked, degraded or
> taken away.
>
> A paid Individual licence includes one feature build request per licence year. [...]
>
> If a licence does not do what this site says it does, email us within 30 days of buying it
> and we will refund it in full. Beyond that, fees already paid are not refundable except
> where the law says otherwise, and your statutory cancellation rights as a consumer are
> unaffected. We may change prices for future purchases; a licence you have already bought
> keeps the terms and price you bought it on.

### Proposed

**5.1 What is free.** The application and its updates are free, including reading web pages,
YouTube videos and web search inside it. A Business licence adds SurfSense's job plugins
[and priority support and one feature build request a year (n)] and gates nothing else.

**5.2 Who needs Business.** Anyone who uses a SurfSense job plugin for work, or has the
application's agent use one for it, needs to be covered by a Business licence. That includes employees and contractors alike (b). A licence covers the
number of people stated on it, and is for the person or organisation it was issued to. A Business
licence for one person is called Business Solo.

**5.3 How people are counted.** You tell us at checkout how many people will use job plugins,
and you confirm or correct that number at each renewal. Count everyone who used a job plugin
in the busiest month of the licence year (b). [A server, virtual desktop or shared computer
that runs job plugins for several people counts each of those people; a licence on a shared
server covers at least two (c).] There is no device limit and no device identifier, and a
licence is not tied to a computer. [We may later ask each installation to activate with a
random code, never a hardware identifier, with your consent and an offline route; reserve
this here, or add it with notice under section 18?]

**5.4 Trial.** You can try the job plugins free for 14 days with a trial licence sent to an
email address, without giving us a card. Each email address gets one trial, and we may limit
how many trials one organisation receives. [Two rules are applied but not published: Gmail
addresses that differ only by dots are one address, and a company domain gets at most two
trials a year. Counsel: is the general sentence enough?] A design partner's trial may be
extended by agreement.

**5.5 Price and payment.** Business is sold through Stripe at $60 a year for each
person, the first included. This is a founding price. We may change it, but only from a
renewal of a licence, after emailing the address on the licence at least 30 days before
that renewal. [Counsel: California's automatic renewal law, as amended by AB 2863, may want
a consumer's notice of a fee change no more than 30 days before it takes effect, so "at
least 30 days" would fit only on the 30th day. Is that the promise to make, for which
buyers, and must the checkout and the purchase email also say the price can change?]
Prices include or exclude tax as shown at checkout. More than 15 people (k), or a
deployment inside your own network, is Enterprise, quoted and invoiced on a contract.

**5.6 Automatic renewal.** A Business licence is a yearly subscription. It renews
automatically at the end of each licence year, and Stripe charges the payment method you
used, until you cancel. The renewal extends the same licence key. An installation that may
go online fetches the renewed licence file; an offline one imports the file we email. We
state the renewal and its price at checkout, before you pay, [and email a reminder before
each renewal: days?]. Counsel: check the checkout and reminder wording against automatic
renewal laws (California, New York and other US states; the EU and the UK for consumers).

**5.7 Cancelling and changing the number of people.** You cancel, or change how many people
the licence covers, in Stripe's customer portal, through a link we send to the licence's
email address; no account is needed. [Cancelling stops the next renewal, and the licence
runs to the end of the year already paid: confirm the Stripe portal is set to cancel at
period end.] [Adding people mid-year is charged pro rata for the rest of the year, and
removing people takes effect at the next renewal: confirm, or choose another rule.]

**5.8 When a licence lapses.** A Business licence lapses when it is cancelled and its year
ends, when a renewal payment fails and is not recovered, or when we end it under section 10.
For 30 days after a lapse the job plugins keep working. After that, new job runs stop, and
every file, library and output you made, with or without a job plugin, stays readable and
yours. A lapse never disables the application or any of its free features. [A licence
suspended for fraud, a chargeback or a full refund stops at once, with no 30 days: confirm.]

**5.9 Your licence file.** A licence is verified on your own machine against a cryptographic
signature, so it keeps working offline. Do not share, resell or publish your licence file,
and do not attempt to defeat the check. Each job plugin shows the name of the organisation
its licence was issued to.

**5.10 Feature build request (n).** A Business licence includes one feature build request
per licence year. Send it by email to rohan@surfsense.com from the address the licence is
registered to. We reply within 5 business days with yes or no and, for a yes, the scope we
would build. A request that fits about a week of engineering work and the direction of the
product goes to the top of our queue and ships in the open source application for everyone.
There is no fixed delivery date. If we decline a request, you can send another one in its
place.

**5.11 Refunds.** If a licence does not do what this site says it does, email us within 30
days of buying it and we will refund it in full. [Does the same 30 days apply to each
renewal charge? Recommended: yes, from the renewal date.] Beyond that, fees already paid are
not refundable except where the law says otherwise, and your statutory cancellation rights as
a consumer are unaffected. [Counsel: the EU and UK 14-day right of withdrawal for digital
content, and whether checkout asks for the waiver.] A full refund suspends the licence.

**5.12 Price changes and earlier licences.** We may change prices for future purchases, and
for a licence's renewals with at least 30 days' notice by email, as 5.5 says, except for an
earlier Individual licence. An Individual licence bought before Business went on sale became
Business Solo on the same key, always renews at the price it was bought at, and otherwise keeps the terms it was bought on for the year
already paid.

## Section 6: The scraper plugins and the service behind them

### Today

> The plugins are the one paid feature that uses a service we operate. When you ask a plugin
> to fetch something, your request and its target reach that service so it can carry out the
> fetch.
>
> Use it lawfully, for data you are entitled to collect, at a reasonable volume, and respect
> the terms and technical signals of the sites you point it at. We may apply rate limits, and
> we may suspend or terminate a licence being used to attack a third party, to collect data
> unlawfully, or obtained by fraud or chargeback. Where the problem is fixable we will tell
> you before cutting you off, unless the abuse is serious enough that waiting would cause
> harm.

### Proposed: "Job plugins, web reading and the services behind them"

**6.1 Job plugins.** A job plugin runs on your own computer, inside the application, with the
model you choose. Its content (prompts, mappings, playbooks, templates and checks) is
delivered by our licence server only to a valid Business or trial licence, and is licensed to
you under the SurfSense Job Plugin License, not under the Apache License 2.0 that covers the
application [(e): link the Job Plugin License once written]. Do not copy, publish or
redistribute a job plugin's content, or use it without a valid licence.

**6.2 What reaches us.** To deliver a job plugin or a renewed licence file, the application
sends our licence server your licence key and what it asks for. Your documents, the
questions you answer and the job's output never reach us; they go only to the model you
choose. [Keep in step with the privacy page, which another change rewrites.]

**6.3 Reading the web and searching.** Reading web pages and YouTube videos runs on your own
computer, over your own connection, so the sites see your request as they would from your
browser. Web search goes through SearXNG: SurfSense's own instance unless you set your
organisation's, in which case your queries reach that instance and the search engines it
asks. Use them lawfully, for data you are entitled to collect, at a reasonable volume, and
respect the terms and technical signals of the sites you read.

**6.4 Limits and suspension.** We may apply rate limits to services we run, including the
licence server and our search instance, and we may suspend or terminate a licence being used
to attack a third party, to collect data unlawfully, or obtained by fraud or chargeback.
Where the problem is fixable we will tell you before cutting you off, unless the abuse is
serious enough that waiting would cause harm.

## The Business terms: points to draft

ADR 0080 asks for Business terms beside the Terms of Service. The points they need, each with
its recommended default:

- **Who needs Business:** anyone who uses a SurfSense job plugin for work, or has the agent
  use one, employees and contractors alike (b).
- **How people are counted:** declared at checkout, confirmed at each renewal, counted at the
  busiest month (b); shared servers, virtual desktops, shared PCs and offline firms count
  people, and a shared server needs at least two (c); offline firms pay the same price (c).
- **Audit and true-up** (g): the right to ask for a count once a year, and a true-up invoice
  for people over the licensed number at the founding or current price, with no penalty for
  a good-faith count.
- **Renewal:** yearly and automatic on the same key, stated before payment, with a reminder
  before each renewal; the founding price can change at a renewal, after at least 30 days' notice by email.
- **Cancellation and seat changes:** in Stripe's emailed customer portal, with no account;
  what cancelling mid-year does, and how adding or removing people is charged.
- **Lapse:** new job runs stop 30 days after a lapse; files, libraries and outputs stay
  readable; the application is never disabled.
- **Enterprise boundary:** more than 15 people (k), a site licence, an internal mirror,
  virtual desktops, a DPA, the code audit, named support, invoicing and negotiated terms (p).
- **If SurfSense stops selling Business** (f): firms keep running the job plugins they have,
  on a licence signed in advance and held outside the company, released on shutdown only.
- **Every job included** (a): Business covers every job plugin SurfSense ships, with no
  per-job add-on.

## Other sections the change touches

- **Section 2, the software and your rights in it:** add that job plugin content is under the
  Job Plugin License, beside the Apache and Business Source License notes.
- **Section 4, acceptable use:** "resell, sublicense or redistribute a licence file or the
  plugin service" becomes "a licence file, a job plugin or a service we run".
- **Section 10, ending this agreement:** "terminate a licence for the reasons in section 6"
  stays; add what termination does to a paid year (refund or none).
- **Section 14, indemnity:** drop "your use of the scraper plugins against a third party";
  keep the claim that material you processed infringed someone's rights, and add use of web
  reading against a site's terms.
- **Section 18, changes to these terms:** the switch is a material change for Individual
  licence holders, so each gets the email this section promises, before the release ships.

## Questions for counsel

1. Governing law and the seat of arbitration: the page leaves `GOVERNING_LAW` unset, so
   section 15 falls back to "the jurisdiction in which SurfSense is established" (g: US
   first).
2. Automatic renewal: the checkout disclosure, the consent, the renewal reminder and the
   cancellation route, against US state laws and EU and UK consumer rules.
3. Business sold to a sole practitioner (Solo) may be a consumer sale in some places: which
   consumer rights apply, and whether the 14-day withdrawal right needs a waiver at checkout.
4. The Job Plugin License: a closed licence for the packs, and whether old pack versions are
   published as open source after 12 to 24 months (e).
5. The per-person count with no technical enforcement: whether the audit and true-up clauses
   are enough, and what a firm must keep to show its count.
6. The 30 days after a lapse: whether they need stating as a licence term, a grace period or
   a courtesy.
