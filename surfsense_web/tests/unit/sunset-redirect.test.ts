import assert from "node:assert/strict";
import test from "node:test";

// Run with: pnpm exec tsx --test tests/unit/sunset-redirect.test.ts

import { isSunsetMode, shouldRedirectToSunset } from "../../lib/sunset";

const APP_ROUTES = [
	"/dashboard",
	"/dashboard/12",
	"/dashboard/12/researcher",
	"/dashboard/12/user-settings",
	"/dashboard/12/purchase-success",
];

// The wind-down portal. A sunset user is being sent here, so redirecting these
// would either loop or hide the pages the launch email points at.
const PORTAL_ROUTES = [
	"/",
	"/sunset",
	"/license",
	"/license/success",
	"/pricing",
	"/blog",
	"/privacy",
	"/terms",
	"/login",
	"/docs",
];

test("with the flag unset, nothing redirects", () => {
	// The launch gate: self-hosters run this code forever with no flag set.
	for (const pathname of [...APP_ROUTES, ...PORTAL_ROUTES]) {
		assert.equal(shouldRedirectToSunset(pathname, undefined), false, pathname);
		assert.equal(shouldRedirectToSunset(pathname, ""), false, pathname);
	}
});

test("a flag that does not mean yes redirects nothing", () => {
	for (const value of ["0", "false", "no", "off", "  "]) {
		assert.equal(shouldRedirectToSunset("/dashboard/12", value), false, value);
	}
});

test("with the flag on, app routes go to /sunset", () => {
	for (const pathname of APP_ROUTES) {
		assert.equal(shouldRedirectToSunset(pathname, "1"), true, pathname);
	}
});

test("with the flag on, the wind-down portal stays reachable", () => {
	for (const pathname of PORTAL_ROUTES) {
		assert.equal(shouldRedirectToSunset(pathname, "1"), false, pathname);
	}
});

test("/sunset never redirects to itself", () => {
	// A redirect loop here would take down the one page that still has a job.
	assert.equal(shouldRedirectToSunset("/sunset", "1"), false);
});

test("every spelling the backend accepts is accepted here too", () => {
	// One variable, set in two places; they must agree on what "on" means.
	for (const value of ["1", "true", "TRUE", "True", "yes", "on"]) {
		assert.equal(isSunsetMode(value), true, value);
	}
	for (const value of ["", "0", "false", "no", "off", "  ", undefined, null]) {
		assert.equal(isSunsetMode(value), false, String(value));
	}
});
