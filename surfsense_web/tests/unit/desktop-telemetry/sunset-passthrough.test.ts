import assert from "node:assert/strict";
import { test } from "node:test";

// Run with: pnpm exec tsx --test tests/unit/desktop-telemetry/sunset-passthrough.test.ts

import { config } from "../../../proxy";

// The sunset proxy sends every non-public path to /sunset on the cloud
// deployment. The desktop routes are not public pages, so they rely on the
// matcher never running the proxy for them: a redirect would cost every
// update check its count and every usage report its record.
const runsProxy = (pathname: string) =>
	config.matcher.some((matcher) => new RegExp(`^${matcher}$`).test(pathname));

test("the proxy still runs on app pages, so this check means something", () => {
	assert.equal(runsProxy("/dashboard/12"), true);
});

test("the proxy never runs for the desktop update feed or usage reports", () => {
	for (const pathname of [
		"/api/updates/stable.yml",
		"/api/updates/stable-mac.yml",
		"/api/updates/stable-linux-arm64.yml",
		"/api/updates/latest.yml",
		"/api/usage",
	]) {
		assert.equal(runsProxy(pathname), false, pathname);
	}
});
