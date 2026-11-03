import assert from "node:assert/strict";
import test from "node:test";

// Run with: pnpm exec tsx --test features/business-launch/launch-redirects.test.ts

// The matcher Next's server resolves `redirects()` with, called with its options, so these
// assertions cannot drift from runtime behaviour.
import { getPathMatch } from "next/dist/shared/lib/router/utils/path-match";
import firstPartyList from "@/app/(home)/plugins/first-party-plugins.json";
import listBeforeBusiness from "@/app/(home)/plugins/first-party-plugins-before-business.json";
import { launchRedirects, RETIRED_PLUGIN_IDS } from "./launch-redirects.mts";

/** Applies the rules the way Next does: first match wins, or no redirect. */
function redirect(launched: boolean, pathname: string) {
	const rule = launchRedirects(launched).find(
		(candidate) =>
			getPathMatch(candidate.source, { strict: true, removeUnnamedParams: true })(pathname) !==
			false
	);
	return rule ? { destination: rule.destination, permanent: rule.permanent } : null;
}

const idsBefore = listBeforeBusiness.plugins.map((plugin) => plugin.id);
const idsAfter = firstPartyList.plugins.map((plugin) => plugin.id);

test("switched off, the redirects are the ones the site had before Business", () => {
	assert.deepEqual(
		launchRedirects(false),
		[
			"google-search",
			"web-crawl",
			"reddit",
			"youtube",
			"instagram",
			"tiktok",
			"google-maps",
			"amazon",
			"walmart",
			"indeed",
		].map((id) => ({ source: `/${id}`, destination: `/plugins/${id}`, permanent: true }))
	);
	assert.equal(redirect(false, "/pricing/individual"), null);
	assert.equal(redirect(false, "/plugins/google-maps"), null);
});

test("switched on, the Individual checkout page sends its visitors to Business", () => {
	assert.deepEqual(redirect(true, "/pricing/individual"), {
		destination: "/pricing/business",
		permanent: true,
	});
	assert.equal(redirect(true, "/pricing"), null);
	assert.equal(redirect(true, "/pricing/business"), null);
});

test("switched on, a retired scraper's page and its old address both land on /plugins", () => {
	for (const id of RETIRED_PLUGIN_IDS) {
		assert.deepEqual(redirect(true, `/plugins/${id}`), {
			destination: "/plugins",
			permanent: true,
		});
		assert.deepEqual(redirect(true, `/${id}`), { destination: "/plugins", permanent: true });
	}
});

test("switched on, the plugins that stay keep their pages and their old addresses", () => {
	for (const id of idsAfter) {
		assert.equal(redirect(true, `/plugins/${id}`), null);
		assert.deepEqual(redirect(true, `/${id}`), {
			destination: `/plugins/${id}`,
			permanent: true,
		});
	}
});

test("the retired plugins are exactly the ones the list loses at the switch", () => {
	assert.deepEqual(
		[...RETIRED_PLUGIN_IDS].sort(),
		idsBefore.filter((id) => !idsAfter.includes(id)).sort()
	);
	assert.deepEqual(
		idsAfter.filter((id) => !idsBefore.includes(id)),
		[],
		"a plugin new at the switch has no old address to redirect"
	);
});
