import assert from "node:assert/strict";
import { test } from "node:test";
import { urlFieldWarning, urlFieldWarnings } from "./url-hints";

// Run with: pnpm exec tsx --test lib/playground/url-hints.test.ts

test("accepts a matching platform URL (no warning)", () => {
	assert.equal(urlFieldWarning("youtube", "urls", "https://www.youtube.com/watch?v=x"), undefined);
	assert.equal(urlFieldWarning("youtube", "urls", "https://youtu.be/x"), undefined);
});

test("flags a well-formed URL for the wrong platform", () => {
	assert.equal(
		urlFieldWarning("youtube", "urls", "https://google.com"),
		"Not a YouTube URL: https://google.com"
	);
});

test("flags a malformed / scheme-less URL", () => {
	assert.equal(
		urlFieldWarning("reddit", "urls", "reddit.com/r/python"),
		"Not a Reddit URL: reddit.com/r/python"
	);
});

test("lists every offending line, ignoring blanks", () => {
	const value = "https://www.tiktok.com/@a\n\n https://google.com \nnot-a-url";
	assert.equal(
		urlFieldWarning("tiktok", "urls", value),
		"Not a TikTok URL: https://google.com, not-a-url"
	);
});

test("matches marketplace/shortlink host variants", () => {
	assert.equal(urlFieldWarning("amazon", "urls", "https://www.amazon.fr/dp/B0"), undefined);
	assert.equal(urlFieldWarning("amazon", "urls", "https://a.co/d/xyz"), undefined);
	assert.equal(urlFieldWarning("google_maps", "urls", "https://maps.app.goo.gl/xyz"), undefined);
});

test("only inspects known URL fields, and skips platforms without a rule", () => {
	// search_terms is not a URL field — never warned.
	assert.equal(urlFieldWarning("amazon", "search_terms", "laptop"), undefined);
	// instagram has no rule (its urls accept bare @handles).
	assert.equal(urlFieldWarning("instagram", "urls", "natgeo"), undefined);
});

test("collects per-field warnings across the form values", () => {
	assert.deepEqual(urlFieldWarnings("indeed", { urls: "https://google.com", country: "us" }), {
		urls: "Not an Indeed URL: https://google.com",
	});
	assert.deepEqual(urlFieldWarnings("indeed", { urls: "https://www.indeed.com/jobs?q=x" }), {});
});
