# Incident Runbook — Checkout Service

## Scope

This runbook covers the checkout service only. Payment provider outages are handled by the payments runbook, and the storefront has its own.

## Severity

An incident is SEV-1 when customers cannot complete a purchase, SEV-2 when a payment method is degraded but others work, and SEV-3 when the effect is cosmetic or internal. Only a SEV-1 pages the on-call engineer out of hours.

## Common errors

**ERR-5041 — basket lock timeout.** The basket row could not be locked within two seconds, usually because a long-running report is holding the table. Check for a report job first, then restart the checkout workers one zone at a time.

**ERR-5107 — provider handshake refused.** The payment provider rejected the TLS handshake, almost always an expired client certificate. The certificate is rotated every 90 days and the renewal job posts to the release channel when it succeeds.

**ERR-4412 — address validation unavailable.** The address service is down. Checkout falls back to accepting unvalidated addresses after ten seconds, so this is a SEV-3 unless the fallback is also failing.

## Restarting workers

Drain one zone, wait for in-flight requests to finish, restart, and confirm the queue depth returns to normal before moving to the next zone. Never restart more than one zone at a time during business hours.

## Escalation

Escalate to the platform team if queue depth stays above 5,000 for ten minutes after a restart. The escalation rota is in the team handbook, not here, because it changes monthly.

## After an incident

Write the review within three working days. The review names the trigger, the detection gap and one change that would have caught it sooner.
