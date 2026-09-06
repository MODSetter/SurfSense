import assert from "node:assert/strict";
import { test } from "node:test";
import { creditStripeStatusResponse, spendableMicros } from "@/contracts/types/stripe.types";

/**
 * The wallet has two buckets and a debit spends the allowance first, so every
 * "how much credit do I have" surface has to add them. Reading either one alone
 * is the bug this guards: the balance alone shows `$0.00` to a free user living
 * inside their monthly allowance, and the allowance alone hides purchased credit.
 */

test("adds the plan allowance to the permanent balance", () => {
	assert.equal(spendableMicros(1_000_000, 2_500_000), 3_500_000);
});

test("a free user inside their allowance is not reported as broke", () => {
	// The regression that motivated this: balance is $0, allowance is $1, and
	// the backend will happily let them chat.
	assert.equal(spendableMicros(1_000_000, 0), 1_000_000);
});

test("a negative balance nets against the allowance", () => {
	// `drain` lets the balance go negative when a job's real cost exceeds the
	// estimate it was pre-charged against. That debt is real and must reduce
	// what we claim is spendable.
	assert.equal(spendableMicros(1_000_000, -250_000), 750_000);
});

test("a negative allowance cannot inflate the balance", () => {
	// Mirrors the backend clamp. Without it a bad row would subtract from a
	// balance the user actually holds.
	assert.equal(spendableMicros(-500_000, 1_000_000), 1_000_000);
});

test("status parsing defaults the allowance for an older backend", () => {
	// A frontend deploy can land before the backend that returns the field.
	// Defaulting to 0 degrades to the previous balance-only behavior rather
	// than throwing on a schema mismatch.
	const parsed = creditStripeStatusResponse.parse({
		credit_buying_enabled: true,
		credit_micros_balance: 4_000_000,
	});
	assert.equal(parsed.credit_micros_allowance, 0);
	assert.equal(parsed.plan, "free");
	assert.equal(
		spendableMicros(parsed.credit_micros_allowance, parsed.credit_micros_balance),
		4_000_000
	);
});

test("the sidebar tooltip fields degrade instead of throwing", () => {
	// Same deploy-order risk as above, for the two fields the plan tooltip
	// reads. A zero grant makes it omit the "of $6.00" line rather than
	// rendering "of $0.00", and a null period end omits the reset date.
	const parsed = creditStripeStatusResponse.parse({
		credit_buying_enabled: true,
		credit_micros_balance: 0,
	});
	assert.equal(parsed.allowance_granted_micros, 0);
	assert.equal(parsed.allowance_period_end, null);
});

test("a period end is carried through as an ISO string", () => {
	const parsed = creditStripeStatusResponse.parse({
		credit_buying_enabled: true,
		credit_micros_balance: 0,
		credit_micros_allowance: 2_400_000,
		allowance_granted_micros: 6_000_000,
		allowance_period_end: "2026-10-04T12:00:00Z",
		plan: "pro",
	});
	assert.equal(parsed.allowance_period_end, "2026-10-04T12:00:00Z");
	assert.equal(parsed.allowance_granted_micros, 6_000_000);
	// What the tooltip renders: spent most of it, so left < granted.
	assert.ok(parsed.credit_micros_allowance < parsed.allowance_granted_micros);
});
