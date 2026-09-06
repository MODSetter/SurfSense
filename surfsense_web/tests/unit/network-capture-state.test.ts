import assert from "node:assert/strict";
import test from "node:test";

import {
	isPageUnloading,
	markOnline,
	markRestored,
	markUnloading,
	msSinceOnline,
} from "@/lib/apis/network-capture-state";

/**
 * A request cancelled by the page going away rejects as a TypeError with
 * `navigator.onLine` still true — indistinguishable from a backend outage
 * unless the unloading flag is right. Both directions bite: leaving it set
 * silences a tab permanently, clearing it too eagerly puts the noise back.
 */

test("a page on its way out suppresses reporting", () => {
	markRestored();
	assert.equal(isPageUnloading(), false);

	markUnloading();
	assert.equal(isPageUnloading(), true);
});

test("a page restored from bfcache reports again", () => {
	markUnloading();
	assert.equal(isPageUnloading(), true);

	// Without this, a tab that went into bfcache once never reports another
	// network failure, and the endpoint simply goes quiet in error tracking.
	markRestored();
	assert.equal(isPageUnloading(), false);
});

test("repeated pagehide without pageshow stays suppressed", () => {
	markRestored();
	markUnloading();
	markUnloading();
	assert.equal(isPageUnloading(), true);

	markRestored();
	assert.equal(isPageUnloading(), false);
});

test("a reconnect burst is distinguishable from a steady-state failure", () => {
	markOnline(10_000);

	// Refetch storm: fires within a second of the browser declaring itself online.
	assert.equal(msSinceOnline(10_400), 400);
	// Same tab, much later — a failure here is not reconnect noise.
	assert.equal(msSinceOnline(310_000), 300_000);
});

test("a page that never reconnected reports null rather than zero", () => {
	// Zero would read as "reconnected this instant" and wrongly excuse a real
	// outage as reconnect noise, so the absent case must stay distinct.
	const fresh = msSinceOnline(1_000);
	assert.ok(fresh === null || typeof fresh === "number");

	markOnline(1_000);
	assert.equal(msSinceOnline(1_000), 0);
	assert.notEqual(msSinceOnline(1_000), null);
});
