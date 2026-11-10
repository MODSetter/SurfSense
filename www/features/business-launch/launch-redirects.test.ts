import assert from "node:assert/strict";
import test from "node:test";

// Run with: pnpm exec tsx --test features/business-launch/launch-redirects.test.ts

// The matcher Next's server resolves `redirects()` with, called with its options, so these
// assertions cannot drift from runtime behaviour.
import { getPathMatch } from "next/dist/shared/lib/router/utils/path-match";
import { BUILT_IN_SOURCES } from "@/app/(home)/plugins/built-in-sources";
import listBeforeBusiness from "@/app/(home)/plugins/first-party-plugins-before-business.json";
import { launchRedirects, RETIRED_PLUGIN_IDS } from "./launch-redirects.mts";

/** Applies the rules the way Next does: first match wins, or no redirect. */
function redirect(pathname: string) {
	const rule = launchRedirects().find(
		(candidate) =>
			getPathMatch(candidate.source, { strict: true, removeUnnamedParams: true })(pathname) !==
			false
	);
	return rule ? { destination: rule.destination, permanent: rule.permanent } : null;
}

const idsBefore = listBeforeBusiness.plugins.map((plugin) => plugin.id);
// What stays is built into the app, on the pages its plugins had.
const idsAfter = BUILT_IN_SOURCES.map((source) => source.id);

test("the Individual checkout page sends its visitors to Business", () => {
	assert.deepEqual(redirect("/pricing/individual"), {
		destination: "/pricing/business",
		permanent: true,
	});
	assert.equal(redirect("/pricing"), null);
	assert.equal(redirect("/pricing/business"), null);
});

test("a retired scraper's page and its old address both land on /plugins", () => {
	for (const id of RETIRED_PLUGIN_IDS) {
		assert.deepEqual(redirect(`/plugins/${id}`), {
			destination: "/plugins",
			permanent: true,
		});
		assert.deepEqual(redirect(`/${id}`), { destination: "/plugins", permanent: true });
	}
});

test("the three built into the app keep their pages and their old addresses", () => {
	for (const id of idsAfter) {
		assert.equal(redirect(`/plugins/${id}`), null);
		assert.deepEqual(redirect(`/${id}`), {
			destination: `/plugins/${id}`,
			permanent: true,
		});
	}
});

test("the retired plugins are exactly the ones not built into the app", () => {
	assert.deepEqual(
		[...RETIRED_PLUGIN_IDS].sort(),
		idsBefore.filter((id) => !idsAfter.includes(id)).sort()
	);
	assert.deepEqual(
		idsAfter.filter((id) => !idsBefore.includes(id)),
		[],
		"each built-in feature had a plugin page, so its old address still means it"
	);
});
