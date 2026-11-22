import assert from "node:assert/strict";
import test from "node:test";
import { docsMarkdownPath } from "./docs-markdown-path.mts";

// Run with: pnpm exec tsx --test features/docs/docs-markdown-path.test.ts

test("a docs page's own URL serves its Markdown", () => {
	assert.equal(docsMarkdownPath("/docs/v2/install"), "/llms.mdx/docs/v2/install");
	assert.equal(docsMarkdownPath("/docs"), "/llms.mdx/docs");
});

test("a .mdx URL is left to the config rewrite, which strips the extension", () => {
	assert.equal(docsMarkdownPath("/docs/v2/install.mdx"), null);
});

test("only docs URLs are rewritten", () => {
	assert.equal(docsMarkdownPath("/docsearch"), null);
	assert.equal(docsMarkdownPath("/blog/post"), null);
});
