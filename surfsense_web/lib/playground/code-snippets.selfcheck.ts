/**
 * Runnable self-check for the API-reference snippet generator. No test
 * framework — run with: ``npx tsx lib/playground/code-snippets.selfcheck.ts``
 * Exits non-zero on the first failed assertion.
 */
import assert from "node:assert/strict";
import { buildExamplePayload, buildSnippets } from "./code-snippets";
import type { FormField } from "./json-schema";

const fields: FormField[] = [
	{ name: "urls", title: "Urls", kind: "string_array", required: true },
	{ name: "sort", title: "Sort", kind: "enum", required: false, default: "new" },
	{ name: "limit", title: "Limit", kind: "integer", required: false },
	{ name: "query", title: "Query", kind: "string", required: true },
];

// Required fields get placeholders, optional-with-default keeps the default,
// optional-without-default is omitted.
const payload = buildExamplePayload(fields);
assert.deepEqual(payload, {
	urls: ["<urls>"],
	sort: "new",
	query: "<query>",
});

const snippets = buildSnippets(
	"https://api.example.com",
	"/api/v1/workspaces/1/scrapers/x/y",
	payload
);

// Every popular language is present.
assert.deepEqual(
	snippets.map((s) => s.id),
	["curl", "python", "javascript", "typescript", "go", "java", "csharp", "php", "ruby"]
);

for (const snippet of snippets) {
	// Each snippet targets the right endpoint and authenticates with the env key.
	assert.ok(
		snippet.code.includes("https://api.example.com/api/v1/workspaces/1/scrapers/x/y"),
		`${snippet.id}: missing url`
	);
	assert.ok(snippet.code.includes("SURFSENSE_API_KEY"), `${snippet.id}: missing auth env var`);
	// The payload made it into the body (PHP re-renders it as an array literal).
	const marker = snippet.id === "php" ? '"urls" =>' : '"urls"';
	assert.ok(snippet.code.includes(marker), `${snippet.id}: missing payload`);
}

// PHP array rendering handles nesting.
const php = snippets.find((s) => s.id === "php");
assert.ok(php?.code.includes('"sort" => "new"'), "php: enum default not rendered");

console.log("code-snippets.selfcheck: all assertions passed");
