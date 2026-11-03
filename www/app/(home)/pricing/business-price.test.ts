import assert from "node:assert/strict";
import test from "node:test";

// Run with: pnpm exec tsx --test "app/(home)/pricing/business-price.test.ts"

import { BUSINESS_PRICE_EXAMPLES, businessYearlyPrice, yearlyPriceLabel } from "./business-price";

test("Business is $200 a year for the first person and $120 for each further person", () => {
	// The figures ADR 0079 states.
	assert.deepEqual(
		[1, 2, 5, 10, 15].map((people) => yearlyPriceLabel(businessYearlyPrice(people))),
		["$200", "$320", "$680", "$1,280", "$1,880"]
	);
});

test("a licence covers at least one person, counted in whole people", () => {
	for (const people of [0, -1, 1.5, Number.NaN]) {
		assert.throws(() => businessYearlyPrice(people), RangeError, String(people));
	}
});

test("the examples the pages show are the ADR's, one person first", () => {
	assert.deepEqual(
		BUSINESS_PRICE_EXAMPLES.map((example) => [example.people, example.price]),
		[
			[1, "$200"],
			[2, "$320"],
			[5, "$680"],
			[10, "$1,280"],
			[15, "$1,880"],
		]
	);
});
