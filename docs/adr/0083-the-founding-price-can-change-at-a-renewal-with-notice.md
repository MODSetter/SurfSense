# ADR 0083: Business's founding price can change at a renewal, after at least 30 days' notice by email

- **Status:** Accepted
- **Date:** 2026-11-04
- **Amends:** [ADR 0080](0080-surfsense-sells-one-business-license-priced-per-person.md): its founding price was "locked for early customers"; a Business license's price can now change at a renewal, with notice. The rest of ADR 0080 stands.
- **Source:** maintainer decision, 4 Nov 2026 (no permalink)

## Context

ADR 0080 sells Business as a yearly subscription at a founding price, $60 a year for each person, "locked for early customers and a hypothesis to test, to rise once sales justify it". The pricing pages and the Business terms draft promised the same lock. Nothing has been sold at that price yet: Business goes on sale at the switch.

A lock leaves no way to raise what an early customer pays, however long they renew, if sales show the price is too low. A Stripe subscription renews at the price it holds, and moving it to a new price at a renewal is an ordinary change.

## Decision

- The founding price stays $60 a year for each person, the first included, and Business stays a yearly subscription.
- SurfSense may change what a Business license costs, but only from a renewal, and only after emailing the address on the license at least 30 days before that renewal: the new price, the date it applies from, and how to cancel before then. New buyers pay the price shown at checkout.
- Individual licenses keep renewing at the price they were bought at when they become Business Solo: those sold by 1 Nov 2026 under ADR 0080's Decision, and those sold since under Terms section 5, "a licence you have already bought keeps the terms and price you bought it on". This ADR changes neither.
- The pricing pages say it in one line: a founding price, and a price change applies only at renewal, after at least 30 days' notice by email.

## Consequences

- No pricing page, plan or proposal promises a locked price, and the Business terms draft (5.5 and 5.12) says what the pages say, for counsel to check against automatic-renewal laws. The live Terms section 5 still says "a licence you have already bought keeps the terms and price you bought it on", which holds for Individual. The Business terms replace it before Business is sold, since `NEXT_PUBLIC_BUSINESS_LAUNCHED` does not switch `/terms`.
- Each license gets its notice 30 days before its own renewal, not in one batch: some automatic-renewal laws, California's among them, also limit how early a consumer's notice of a fee change may come, and counsel confirms the window.
- A new price is a new Stripe price and Payment Link, and a www build whose `NEXT_PUBLIC_STRIPE_LICENSE_BUSINESS_URL` names the new link. While the license server knows one Business price, the old link is deactivated in Stripe in the same step that moves `STRIPE_PRICE_LICENSE_BUSINESS`: a payment on a link whose price the server does not know is charged, answered with a 200, and gets no license.

## Where the code stands

- Nothing sends the notice. [`message.py`](../../backend/license/email/message.py) has four mail kinds, `purchase`, `resend`, `trial` and `renewal`, and nothing finds the licenses that renew in 30 days or moves a subscription to a new price.
- [`checkout.py`](../../backend/license/checkout.py) matches a Payment Link's line item against one `STRIPE_PRICE_LICENSE_BUSINESS` ([`settings.py`](../../backend/license/settings.py)), and [`purchase.py`](../../backend/license/purchase.py) drops a session whose price matches none. Renewals, seat changes and refunds never read the price ([`subscription/`](../../backend/license/subscription/), [`charged_license.py`](../../backend/license/charged_license.py)), so a subscription moved to a new price keeps renewing.
