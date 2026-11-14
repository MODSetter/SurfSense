import assert from "node:assert/strict";
import test from "node:test";

// Run with: pnpm exec tsx --test "app/(home)/plugins/built-in.test.ts"

import { isBuiltIn } from "./built-in";
import firstPartyList from "./first-party-plugins.json";
import listBeforeBusiness from "./first-party-plugins-before-business.json";
import { surfsensePlugins } from "./plugin-list";
import { listingFromEntry } from "./plugin-listing";

const ids = (plugins: { id: string }[]) => plugins.map((plugin) => plugin.id);

test("web search, Web Crawl and YouTube are free and built into the app", () => {
	const plugins = surfsensePlugins(firstPartyList);
	assert.deepEqual(ids(plugins), ["google-search", "web-crawl", "youtube"]);
	for (const plugin of plugins) {
		assert.equal(isBuiltIn(plugin), true, plugin.id);
		assert.equal(plugin.access, "free", plugin.id);
		assert.equal(plugin.href, `/plugins/${plugin.id}`, "each keeps the page its plugin had");
	}
	assert.deepEqual(firstPartyList.plugins, [], "the app lists no SurfSense hosted plugin");
});

test("an app list that still carries the three, licensed, lists each once, as built in", () => {
	// What the app's list holds between the scrapers' retirement and the three moving in.
	const interim = {
		plugins: listBeforeBusiness.plugins.filter((entry) =>
			["google-search", "web-crawl", "youtube"].includes(entry.id)
		),
	};
	const plugins = surfsensePlugins(interim);
	assert.deepEqual(ids(plugins), ["google-search", "web-crawl", "youtube"]);
	assert.ok(plugins.every(isBuiltIn));
});

test("another publisher's free plugin is not built into the app", () => {
	const plugin = listingFromEntry(
		{
			id: "deepwiki",
			name: "DeepWiki",
			description: "Ask questions about public repositories.",
			author: "Cognition",
			url: "https://mcp.deepwiki.com/mcp",
			auth: { type: "none" },
			access: "free",
		},
		"third-party"
	);
	assert.ok(plugin);
	assert.equal(isBuiltIn(plugin), false);
});
