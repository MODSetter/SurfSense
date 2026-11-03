import assert from "node:assert/strict";
import test from "node:test";

// Run with: pnpm exec tsx --test "app/(home)/plugins/built-in.test.ts"

import { isBuiltIn } from "./built-in";
import firstPartyList from "./first-party-plugins.json";
import listBeforeBusiness from "./first-party-plugins-before-business.json";
import { listingFromEntry, type PluginListing } from "./plugin-listing";

function listings(entries: unknown[], publisher: PluginListing["publisher"]) {
	return entries.map((entry) => {
		const listing = listingFromEntry(entry, publisher);
		assert.ok(listing, `an entry the page cannot show: ${JSON.stringify(entry).slice(0, 80)}`);
		return listing;
	});
}

test("before Business, every SurfSense plugin needs the licence and none is built in", () => {
	for (const plugin of listings(listBeforeBusiness.plugins, "surfsense")) {
		assert.equal(plugin.access, "license", plugin.id);
		assert.equal(isBuiltIn(plugin), false, plugin.id);
	}
});

test("from Business on, every SurfSense plugin is free and built into the app", () => {
	const plugins = listings(firstPartyList.plugins, "surfsense");
	assert.deepEqual(
		plugins.map((plugin) => plugin.id),
		["google-search", "web-crawl", "youtube"]
	);
	for (const plugin of plugins) {
		assert.equal(isBuiltIn(plugin), true, plugin.id);
		assert.equal(plugin.signIn, "none", plugin.id);
	}
});

test("another publisher's free plugin is not built into the app", () => {
	const [plugin] = listings(
		[
			{
				id: "deepwiki",
				name: "DeepWiki",
				description: "Ask questions about public repositories.",
				author: "Cognition",
				url: "https://mcp.deepwiki.com/mcp",
				auth: { type: "none" },
				access: "free",
			},
		],
		"third-party"
	);
	assert.equal(isBuiltIn(plugin), false);
});
