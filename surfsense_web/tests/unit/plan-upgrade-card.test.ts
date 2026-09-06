import assert from "node:assert/strict";
import { test } from "node:test";
import { formatPeriodEnd } from "@/components/settings/plan-upgrade-card";
import { planStatusResponse } from "@/contracts/types/stripe.types";

test("formats a period end into a renewal date", () => {
	const formatted = formatPeriodEnd("2026-10-04T12:00:00Z");
	// Asserted in parts because the output is deliberately locale-aware: word
	// order is "October 4" under en-US and "4 October" under en-GB, and pinning
	// either one would fail on half the machines that run this.
	assert.ok(formatted);
	assert.match(formatted, /\b4\b/);
	assert.match(formatted, /Oct/i);
});

test("returns null for an account never put on a period", () => {
	assert.equal(formatPeriodEnd(null), null);
});

test("returns null rather than rendering 'Invalid Date' to a customer", () => {
	// The card's sentence reads correctly without a date, so a junk value has
	// to degrade to that instead of surfacing the string `new Date` produces.
	assert.equal(formatPeriodEnd("not-a-date"), null);
	assert.equal(formatPeriodEnd(""), null);
});

test("subscriptions are unavailable unless the backend says otherwise", () => {
	// Self-hosted installs have no Pro price, and the field is what hides the
	// upgrade button. Defaulting it to true would open a checkout the
	// deployment cannot complete.
	const parsed = planStatusResponse.parse({ plan: "free" });
	assert.equal(parsed.subscription_available, false);
	assert.equal(parsed.period_end, null);
	assert.equal(parsed.allowance_micros, 0);
});
