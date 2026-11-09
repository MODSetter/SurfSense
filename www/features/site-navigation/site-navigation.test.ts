import assert from "node:assert/strict";
import { readdirSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import {
	BUSINESS_PAGES,
	footerColumns,
	isNavMenu,
	type NavEntry,
	siteNavigation,
} from "./site-navigation";

// Run with: pnpm exec tsx --test features/site-navigation/site-navigation.test.ts

const APP = path.join(__dirname, "../../app");

/** Every folder under `app/` that serves a page, as Next resolves it: a route group adds no segment. */
function pageRoutes(dir = APP, segments: string[] = []): string[][] {
	const routes: string[][] = [];
	for (const entry of readdirSync(dir, { withFileTypes: true })) {
		if (entry.isFile() && /^page\.(tsx|ts|mdx)$/.test(entry.name)) routes.push(segments);
		if (!entry.isDirectory()) continue;
		const group = entry.name.startsWith("(") && entry.name.endsWith(")");
		routes.push(
			...pageRoutes(path.join(dir, entry.name), group ? segments : [...segments, entry.name])
		);
	}
	return routes;
}

/** A dynamic segment takes any one part; an optional catch-all takes the rest or nothing. */
function routeMatches(route: string[], parts: string[]): boolean {
	for (const [index, segment] of route.entries()) {
		if (segment.startsWith("[[...")) return true;
		if (segment.startsWith("[...")) return parts.length > index;
		if (index >= parts.length) return false;
		if (!segment.startsWith("[") && segment !== parts[index]) return false;
	}
	return route.length === parts.length;
}

const ROUTES = pageRoutes();

function isPage(href: string): boolean {
	const parts = href.split(/[?#]/)[0].split("/").filter(Boolean);
	return ROUTES.some((route) => routeMatches(route, parts));
}

function names(entries: NavEntry[]): string[] {
	return entries.map((entry) => entry.name);
}

function menu(entries: NavEntry[], name: string) {
	const found = entries.filter(isNavMenu).find((entry) => entry.name === name);
	assert.ok(found, `no ${name} menu`);
	return found;
}

/** Every link on this site that the nav and the footer carry, menus included. */
function siteHrefs(launched: boolean): string[] {
	const nav = siteNavigation(launched).flatMap((entry) =>
		isNavMenu(entry) ? entry.items : [entry]
	);
	const footer = footerColumns(launched).flatMap((column) => column.links);
	return [...nav, ...footer].filter((link) => !link.external).map((link) => link.href);
}

test("switched off, the nav is the one the site had before Business", () => {
	const nav = siteNavigation(false);
	assert.deepEqual(names(nav), ["For business", "Plugins", "Docs", "Pricing", "Resources"]);
	assert.deepEqual(
		menu(nav, "Resources").items.map((item) => item.href),
		["/blog", "/announcements", "/changelog", "/contact"]
	);
});

test("switched on, who it's for and the jobs lead the nav, and Plugins moves under Resources", () => {
	const nav = siteNavigation(true);
	assert.deepEqual(names(nav), ["Who it's for", "Jobs", "Docs", "Pricing", "Resources"]);
	assert.deepEqual(
		menu(nav, "Who it's for").items.map((item) => item.href),
		["/ai-for-lawyers", "/ai-for-accountants", "/private-ai-for-business"]
	);
	assert.deepEqual(
		menu(nav, "Jobs").items.map((item) => item.href),
		["/jobs/contract-redline", "/jobs/security-questionnaire"]
	);
	assert.deepEqual(
		menu(nav, "Resources").items.map((item) => item.href),
		["/blog", "/announcements", "/changelog", "/plugins", "/contact"]
	);
});

test("switched off, the footer is the one the site had before Business", () => {
	assert.deepEqual(
		footerColumns(false).map((column) => [column.heading, column.links.map((link) => link.href)]),
		[
			["Product", ["/downloads", "/private-ai-for-business", "/plugins", "/pricing", "/docs"]],
			["Resources", ["/blog", "/announcements", "/changelog", "/contact"]],
			["Company", ["/privacy", "/terms"]],
		]
	);
});

test("switched on, the footer links every page the nav's menus link", () => {
	const footer = new Set(
		footerColumns(true).flatMap((column) => column.links.map((link) => link.href))
	);
	for (const entry of siteNavigation(true).filter(isNavMenu)) {
		for (const item of entry.items) {
			assert.ok(
				footer.has(item.href),
				`${item.href} is in the ${entry.name} menu but not the footer`
			);
		}
	}
});

test("every page the nav and the footer link to exists, switched on or off", () => {
	for (const launched of [false, true]) {
		for (const href of siteHrefs(launched)) {
			assert.ok(isPage(href), `${href} has no page (switched ${launched ? "on" : "off"})`);
		}
	}
});

test("until Business is on sale, nothing in the nav or the footer leads to its pages", () => {
	const before = new Set(siteHrefs(false));
	for (const href of BUSINESS_PAGES) {
		assert.ok(!before.has(href), `${href} is linked before the switch`);
	}
	const after = new Set(siteHrefs(true));
	for (const href of BUSINESS_PAGES) {
		assert.ok(after.has(href), `${href} is not linked after the switch`);
	}
});
