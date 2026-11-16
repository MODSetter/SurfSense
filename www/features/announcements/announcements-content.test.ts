import assert from "node:assert/strict";
import { readdirSync } from "node:fs";
import path from "node:path";
import test from "node:test";

// Run with: pnpm exec tsx --test features/announcements/announcements-content.test.ts

import { announcements } from "./announcements-data";

// Each announcement's page is `/announcements/<id>`, its text `<id>.mdx` here.
const CONTENT = path.join(__dirname, "../../content/announcements");

// Lowercase words joined by single hyphens: safe in a URL without encoding.
const URL_SAFE_ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

const ids = announcements.map((announcement) => announcement.id);
const files = readdirSync(CONTENT);

test("every announcement id is URL-safe and unique", () => {
	// A silent import failure would make the suite pass while testing nothing.
	assert.ok(ids.length > 0, "expected at least one announcement");

	for (const id of ids) {
		assert.match(id, URL_SAFE_ID, `"${id}" is not lowercase letters, digits and hyphens`);
	}
	assert.equal(new Set(ids).size, ids.length, "two announcements share an id");
});

test("every announcement has a body", () => {
	for (const id of ids) {
		assert.ok(files.includes(`${id}.mdx`), `content/announcements/${id}.mdx is missing`);
	}
});

test("every body belongs to an announcement", () => {
	for (const file of files) {
		assert.ok(
			file.endsWith(".mdx") && ids.includes(file.slice(0, -".mdx".length)),
			`content/announcements/${file} has no entry in features/announcements/announcements-data.ts`
		);
	}
});
