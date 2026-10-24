import assert from "node:assert/strict";
import test from "node:test";

// Run with: pnpm exec tsx --test app/(home)/pricing/individual/individual-checkout.test.ts

import { checkoutHref, isPaymentLink } from "@/app/(home)/pricing/individual/checkout-link";

test("the checkout link carries only the channel as client_reference_id", () => {
	const href = checkoutHref("https://buy.stripe.com/test_abc?prefilled_promo_code=EARLY", "hn");
	const url = new URL(href);
	assert.equal(url.origin + url.pathname, "https://buy.stripe.com/test_abc");
	assert.equal(url.searchParams.get("client_reference_id"), "hn");
	assert.equal(url.searchParams.get("prefilled_promo_code"), "EARLY");
	assert.deepEqual([...url.searchParams.keys()].sort(), [
		"client_reference_id",
		"prefilled_promo_code",
	]);
});

test("the /contact fallback is linked without parameters", () => {
	assert.equal(isPaymentLink("/contact"), false);
	assert.equal(checkoutHref("/contact", "hn"), "/contact");
});
