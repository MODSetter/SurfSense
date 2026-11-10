import assert from "node:assert/strict";
import { readdirSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import {
	FOOTER_COLUMNS,
	isNavMenu,
	menuItems,
	type NavEntry,
	SITE_NAVIGATION,
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

function menu(entries: NavEntry[], name: string) {
	const found = entries.filter(isNavMenu).find((entry) => entry.name === name);
	assert.ok(found, `no ${name} menu`);
	return found;
}

test("the bar opens on the For menu: who it's for, the jobs, then the study tools", () => {
	assert.deepEqual(
		SITE_NAVIGATION.map((entry) => entry.name),
		["For", "Docs", "Pricing", "Resources"]
	);
	assert.deepEqual(
		menu(SITE_NAVIGATION, "For").groups.map((group) => [
			group.heading,
			group.items.map((item) => item.href),
		]),
		[
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
			[
				"Study tools",
				[
					"/features/study-guide-maker",
					"/features/flashcard-generator",
					"/features/quiz-generator",
					"/features/podcast-generator",
				],
			],
		]
	);
});

test("Plugins sits under Resources, since the scrapers retired", () => {
	assert.deepEqual(
		menuItems(menu(SITE_NAVIGATION, "Resources")).map((item) => item.href),
		["/blog", "/announcements", "/changelog", "/plugins", "/contact"]
	);
});

test("the footer groups the pages by who they are for, and the jobs sit under Product", () => {
	assert.deepEqual(
		FOOTER_COLUMNS.map((column) => [column.heading, column.links.map((link) => link.href)]),
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

test("every page the nav and the footer link to exists", () => {
	const nav = SITE_NAVIGATION.flatMap((entry) => (isNavMenu(entry) ? menuItems(entry) : [entry]));
	const footer = FOOTER_COLUMNS.flatMap((column) => column.links);
	for (const link of [...nav, ...footer]) {
		if (link.external) continue;
		assert.ok(isPage(link.href), `${link.href} has no page`);
	}
});
