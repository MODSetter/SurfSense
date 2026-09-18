import assert from "node:assert/strict";
import { test } from "node:test";
import { FREE_MODELS, freeModelLabel, isPublishedSlug } from "./free-models";

// Run with: pnpm exec tsx --test lib/free-models.test.ts

test("catalog rows have unique slugs", () => {
	const slugs = FREE_MODELS.map((model) => model.slug);
	assert.equal(new Set(slugs).size, slugs.length);
});

test("a catalog slug uses the row's own name", () => {
	assert.equal(freeModelLabel("deepseek-r1-no-login"), "DeepSeek R1");
	assert.equal(freeModelLabel("gpt-4o-no-login"), "GPT-4o");
});

test("an old hosted slug still gets a readable name", () => {
	// The URLs the closed service left in Google, which are not catalog rows.
	assert.equal(freeModelLabel("gpt-5.4-mini-no-login"), "GPT 5.4 Mini");
	assert.equal(freeModelLabel("gpt-o4-mini-no-login"), "GPT O4 Mini");
	assert.equal(freeModelLabel("claude-haiku-no-login"), "Claude Haiku");
});

test("a slug that was never published falls back instead of echoing", () => {
	// This label reaches a JSON-LD <script> block, so nothing off the URL bar
	// may survive into it verbatim.
	assert.equal(freeModelLabel("</script><script>alert(1)</script>"), "This model");
	assert.equal(freeModelLabel("Foo Bar"), "This model");
	assert.equal(freeModelLabel(""), "This model");
	assert.equal(freeModelLabel("-no-login"), "This model");
	assert.equal(freeModelLabel(`a${"b".repeat(90)}`), "This model");
});

test("the slug gate turns away everything that could break out of a script tag", () => {
	for (const slug of [
		"</script><script>alert(1)</script>",
		"%3C%2Fscript%3E%3Cscript%3Ealert(1)%3C%2Fscript%3E",
		'a"b',
		"a'b",
		"a b",
		"a/b",
		"a<b",
		"",
		"-leading-hyphen",
		`a${"b".repeat(90)}`,
	]) {
		assert.equal(isPublishedSlug(slug), false, slug);
	}
});

test("the slug gate keeps every shape the closed service could have published", () => {
	for (const slug of [
		...FREE_MODELS.map((model) => model.slug),
		"gpt-5.4-mini-no-login",
		"gpt-o4-mini-no-login",
		"GPT-4o-no-login",
		"claude_haiku_no_login",
		"o3",
	]) {
		assert.equal(isPublishedSlug(slug), true, slug);
	}
});
