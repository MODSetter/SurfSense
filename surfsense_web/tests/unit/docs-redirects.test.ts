import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

// Run with: pnpm exec tsx --test tests/unit/docs-redirects.test.ts

// The copy Next matches routes with, so these assertions cannot drift from
// runtime behaviour. There is no standalone `path-to-regexp` in the tree.
import { compile, pathToRegexp } from "next/dist/compiled/path-to-regexp";
import { CURRENT_DOCS_PATH, docsRedirects, LEGACY_DOCS_PATH } from "../../lib/docs-redirects";

const matchers = docsRedirects.map((rule) => ({
	regexp: pathToRegexp(rule.source, []),
	// Next compiles destinations unvalidated, which is what lets a single
	// `:path` hold a multi-segment value like `connectors/native/reddit`.
	toDestination: compile(rule.destination, { validate: false }),
}));

/** Applies the rules the way Next does: first match wins, or no redirect. */
function redirect(pathname: string): string | null {
	for (const { regexp, toDestination } of matchers) {
		const match = regexp.exec(pathname);
		if (match) return toDestination({ path: match[1] });
	}
	return null;
}

const DOCS_CONTENT = path.join(__dirname, "../../content/docs");
const DOCS_PUBLIC = path.join(__dirname, "../../public/docs");

/** Every file below `dir`, as paths relative to it. */
function walk(dir: string, base = dir): string[] {
	return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
		const full = path.join(dir, entry.name);
		return entry.isDirectory() ? walk(full, base) : [path.relative(base, full)];
	});
}

/** Page URLs as they existed before the pivot, derived from what actually shipped. */
function legacyPageUrls(): string[] {
	const root = path.join(DOCS_CONTENT, LEGACY_DOCS_PATH);
	return (
		walk(root)
			.filter((file) => file.endsWith(".mdx"))
			.map((file) => file.replaceAll(path.sep, "/").replace(/(\/?index)?\.mdx$/, ""))
			// The root index used to be `/docs` itself, which now points at the
			// current version instead. Covered separately below.
			.filter((slug) => slug !== "")
			.map((slug) => `/docs/${slug}`)
	);
}

test("every page written before the pivot still resolves", () => {
	const urls = legacyPageUrls();
	// A silent glob failure would make this suite pass while testing nothing.
	assert.ok(urls.length > 40, `expected the full docs set, got ${urls.length}`);

	for (const url of urls) {
		assert.equal(
			redirect(url),
			`/docs/${LEGACY_DOCS_PATH}${url.slice("/docs".length)}`,
			`${url} lost its redirect`
		);
	}
});

test("the docs front door points at the current version", () => {
	assert.equal(redirect("/docs"), `/docs/${CURRENT_DOCS_PATH}`);
});

test("version folders are left alone, so nothing loops", () => {
	for (const segment of [LEGACY_DOCS_PATH, CURRENT_DOCS_PATH]) {
		assert.equal(redirect(`/docs/${segment}`), null, segment);
		assert.equal(redirect(`/docs/${segment}/installation`), null, segment);
		assert.equal(redirect(`/docs/${segment}/connectors/native/reddit`), null, segment);
	}
});

test("screenshots under public/docs are not redirected", () => {
	// Redirects run before the public directory is consulted, so a rule that
	// swallowed these would 404 every image embedded in the docs.
	const assets = walk(DOCS_PUBLIC).map((file) => `/docs/${file.replaceAll(path.sep, "/")}`);
	assert.ok(assets.length > 0, "expected screenshots under public/docs");

	for (const asset of assets) {
		assert.equal(redirect(asset), null, `${asset} would 404`);
	}
});

function metaFiles(): string[] {
	return walk(DOCS_CONTENT).filter((file) => path.basename(file) === "meta.json");
}

function readMeta(file: string): Record<string, unknown> {
	return JSON.parse(readFileSync(path.join(DOCS_CONTENT, file), "utf8"));
}

test("every meta.json matches the schema fumadocs enforces", async () => {
	// Worth asserting because the failure is so badly signposted: a wrong type
	// here surfaces as `Module not found: .../meta.json.json` from Turbopack,
	// which names neither the field nor the reason.
	const { metaSchema } = await import("fumadocs-core/source/schema");
	const files = metaFiles();
	assert.ok(files.length > 0, "expected meta.json files under content/docs");

	for (const file of files) {
		const result = metaSchema.safeParse(readMeta(file));
		const why = result.error?.issues
			.map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`)
			.join("; ");
		assert.ok(result.success, `${file} -- ${why}`);
	}
});

test("the docs split into exactly the two sections", () => {
	// `root: true` is what makes a folder its own section in the sidebar.
	// Losing it on either folder silently collapses the split.
	const roots = metaFiles()
		.filter((file) => readMeta(file).root === true)
		.map((file) => path.dirname(file).replaceAll(path.sep, "/"));

	assert.deepEqual(roots.toSorted(), [CURRENT_DOCS_PATH, LEGACY_DOCS_PATH].toSorted());
});

test("unknown docs paths still land in the legacy version", () => {
	// Better a 404 inside the old docs than a 404 at a URL with no owner.
	assert.equal(redirect("/docs/some-deleted-page"), `/docs/${LEGACY_DOCS_PATH}/some-deleted-page`);
});
