import assert from "node:assert/strict";
import { readdirSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import {
	BUSINESS_PAGES,
	footerColumns,
	isNavMenu,
	menuItems,
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

/** A menu as its groups' headings and the pages each one links. */
function groups(entries: NavEntry[], name: string) {
	return menu(entries, name).groups.map((group) => [
		group.heading,
		group.items.map((item) => item.href),
	]);
}

/** Every link on this site that the nav and the footer carry, menus included. */
function siteHrefs(launched: boolean): string[] {
	const nav = siteNavigation(launched).flatMap((entry) =>
		isNavMenu(entry) ? menuItems(entry) : [entry]
	);
	const footer = footerColumns(launched).flatMap((column) => column.links);
	return [...nav, ...footer].filter((link) => !link.external).map((link) => link.href);
}

const STUDY_TOOLS = [
	"/features/study-guide-maker",
	"/features/flashcard-generator",
	"/features/quiz-generator",
	"/features/podcast-generator",
];

test("switched off, a For menu takes the place of For business, and the rest of the nav stays", () => {
	const nav = siteNavigation(false);
	assert.deepEqual(names(nav), ["For", "Plugins", "Docs", "Pricing", "Resources"]);
	assert.deepEqual(groups(nav, "For"), [
		["Who it's for", ["/ai-for-students", "/ai-for-teachers", "/private-ai-for-business"]],
		["Study tools", STUDY_TOOLS],
	]);
	assert.deepEqual(
		menuItems(menu(nav, "Resources")).map((item) => item.href),
		["/blog", "/announcements", "/changelog", "/contact"]
	);
});

test("switched on, the For menu adds the paid audiences and the jobs, and Plugins moves under Resources", () => {
	const nav = siteNavigation(true);
	assert.deepEqual(names(nav), ["For", "Docs", "Pricing", "Resources"]);
	assert.deepEqual(groups(nav, "For"), [
		[
			"Who it's for",
			[
				"/ai-for-lawyers",
				"/ai-for-accountants",
				"/ai-for-students",
				"/ai-for-teachers",
				"/private-ai-for-business",
			],
		],
		["Jobs", ["/jobs/contract-redline", "/jobs/security-questionnaire"]],
		["Study tools", STUDY_TOOLS],
	]);
	assert.deepEqual(
		menuItems(menu(nav, "Resources")).map((item) => item.href),
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

test("switched on, the footer groups the pages by who they are for, and the jobs sit under Product", () => {
	assert.deepEqual(
		footerColumns(true).map((column) => [column.heading, column.links.map((link) => link.href)]),
		[
			[
				"Product",
				[
					"/downloads",
					"/pricing",
					"/jobs/contract-redline",
					"/jobs/security-questionnaire",
					"/docs",
					"/plugins",
				],
			],
			[
				"Who it's for",
				[
					"/ai-for-lawyers",
					"/ai-for-accountants",
					"/ai-for-students",
					"/ai-for-teachers",
					"/private-ai-for-business",
				],
			],
			["Resources", ["/blog", "/announcements", "/changelog", "/contact"]],
			["Company", ["/privacy", "/terms"]],
		]
	);
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
