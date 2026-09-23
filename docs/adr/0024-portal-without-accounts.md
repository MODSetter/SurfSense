# ADR 0024: The license portal has no accounts and no license tables; Stripe and Keygen are the system of record

- **Status:** Accepted
- **Date:** 2026-09-12
- **Source:** [Pivot plan L39](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L39), [Pivot plan L44–45](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L44-L45), [Pivot plan L245](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L245), [Pivot plan L310](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L310), [Pivot plan L321](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L321), [License routes plan L7–16](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/portal/01-license-routes.md#L7-L16), [License routes plan L60–65](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/portal/01-license-routes.md#L60-L65), [License routes plan L109–112](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/portal/01-license-routes.md#L109-L112)

## Context

Licenses cannot depend on the hosted accounts. Google login survives only inside the hosted app during the tail, for export, and hosted user data is purged at T+30. Buyers still have to purchase, download, re-download and claim a trial. The portal as built is in [license/portal](../architecture/license/portal.md).

## Decision

- No account anywhere on the portal. Stripe Checkout collects the email. The webhook creates the Keygen license with metadata (`plan`, `email`, the Stripe customer and checkout session ids) and writes the Keygen license id into the Stripe customer's metadata.
- Delivery happens twice: the success page serves the file by checkout session id, and the file is emailed.
- Re-download is "resend my license": email in, a Keygen lookup by metadata email, and the files mailed to that same address, rate-limited. The route answers the same whether or not a license was found, so it cannot be used to probe emails. Control of the inbox is what replaced the login.
- A trial is the same shape: email in, one per email, enforced by a Keygen lookup on a folded `trialKey` plus a disposable-domain blocklist, and the license out by email.
- No license tables. Stripe and Keygen are the system of record, and Keygen's list endpoint filters by metadata, so lookups need no table of ours.
- Fulfilment is idempotent without a table. The Keygen license id is a uuid5 of the checkout session, or of the folded email for a trial, so a second fulfilment collides inside Keygen and the loser reads the winner's license (`derive_license_id()` in [`surfsense_backend/app/license/issue.py`](../../surfsense_backend/app/license/issue.py)).
- Keygen runs self-hosted, as Keygen CE (recorded 14 Sep 2026), and production uses it (maintainer-confirmed, 22 Sep 2026). It is meant to be internal-only: the backend's license routes call it, and so will the scraper API's `validate-key` check once license mode exists. The backend reaches it through `KEYGEN_API_URL` and falls back to Keygen Cloud when that is unset ([`surfsense_backend/app/license/keygen.py`](../../surfsense_backend/app/license/keygen.py)).

## Consequences

- Every delivery checks out a fresh file, so two files for one license differ in `meta.issued`. The app keeps one license file and replaces it with whichever file is imported next, which meets contract 1's rule that a resent file replaces the stored one ([contract 1](../contracts/01-license-file.md)).
- Keygen metadata is the only index. A filter key with the wrong casing returns an empty list rather than an error, which reads as "no license exists".
- A buyer who mistypes the email still gets the file on the success page, and support re-issues it from the Stripe record.
- Self-hosting Keygen means owning its uptime. It is off the app's request path, so an outage blocks new purchases and scraper validation, not installed apps.
