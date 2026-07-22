import assert from "node:assert/strict";
import { test } from "node:test";
import { parseTextWithCitations } from "./citation-parser";

// Run with: pnpm exec tsx --test lib/citations/citation-parser.test.ts

const NO_URLS = new Map<string, string>();

test("parses a scraper-run handle into a run token", () => {
	const segments = parseTextWithCitations(
		"Price is $19 [citation:run_1b2c3d4e-5f60-7081-9abc-def012345678].",
		NO_URLS
	);

	assert.deepEqual(segments, [
		"Price is $19 ",
		{ kind: "run", runId: "run_1b2c3d4e-5f60-7081-9abc-def012345678" },
		".",
	]);
});

test("run handles do not collide with numeric chunk citations", () => {
	const segments = parseTextWithCitations(
		"chunk [citation:42] vs run [citation:run_ab-12].",
		NO_URLS
	);

	assert.deepEqual(segments, [
		"chunk ",
		{ kind: "chunk", chunkId: 42, isDocsChunk: false },
		" vs run ",
		{ kind: "run", runId: "run_ab-12" },
		".",
	]);
});
