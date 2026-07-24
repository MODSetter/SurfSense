/**
 * Runnable self-check for the playground schema parser. No test framework —
 * run with: ``npx tsx lib/playground/json-schema.selfcheck.ts``
 * Exits non-zero on the first failed assertion.
 */
import assert from "node:assert/strict";
import { buildPayload, initialFormValues, parseSchemaFields } from "./json-schema";

// Mirrors the pydantic v2 ``model_json_schema()`` output for a reddit-like verb:
// a required string[], an enum with a default (allOf + default), an optional
// string (anyOf: [str, null]), and an integer with bounds + default.
const schema = {
	$defs: {
		RedditSort: { enum: ["new", "hot", "top"], title: "RedditSort", type: "string" },
	},
	properties: {
		urls: { items: { type: "string" }, type: "array", title: "Urls", description: "Target URLs" },
		sort: { allOf: [{ $ref: "#/$defs/RedditSort" }], default: "new" },
		community: { anyOf: [{ type: "string" }, { type: "null" }], default: null, title: "Community" },
		max_items: { type: "integer", minimum: 1, maximum: 100, default: 25, title: "Max Items" },
		skip_comments: { type: "boolean", default: false, title: "Skip Comments" },
	},
	required: ["urls"],
	title: "ScrapeInput",
	type: "object",
};

const fields = parseSchemaFields(schema);
const byName = Object.fromEntries(fields.map((f) => [f.name, f]));

// string[] detection
assert.equal(byName.urls.kind, "string_array");
assert.equal(byName.urls.required, true);
assert.equal(byName.urls.description, "Target URLs");

// enum resolved through allOf + $ref, default preserved
assert.equal(byName.sort.kind, "enum");
assert.deepEqual(byName.sort.enumValues, ["new", "hot", "top"]);
assert.equal(byName.sort.default, "new");
assert.equal(byName.sort.required, false);

// optional via anyOf: [str, null] -> string
assert.equal(byName.community.kind, "string");
assert.equal(byName.community.required, false);

// integer bounds
assert.equal(byName.max_items.kind, "integer");
assert.equal(byName.max_items.minimum, 1);
assert.equal(byName.max_items.maximum, 100);

// boolean
assert.equal(byName.skip_comments.kind, "boolean");

// defaults seed the form (string_array default would be joined, none here)
const initial = initialFormValues(fields);
assert.equal(initial.urls, ""); // required, no default
assert.equal(initial.sort, "new");
assert.equal(initial.max_items, 25);
assert.equal(initial.skip_comments, false);

// payload building: split lines, coerce number/bool, omit empty optionals
const payload = buildPayload(fields, {
	urls: "https://a.com\n  https://b.com  \n\n",
	sort: "top",
	community: "",
	max_items: "50",
	skip_comments: true,
});
assert.deepEqual(payload.urls, ["https://a.com", "https://b.com"]);
assert.equal(payload.sort, "top");
assert.equal("community" in payload, false); // empty optional omitted
assert.equal(payload.max_items, 50);
assert.equal(payload.skip_comments, true);

// unknown / empty schema is safe
assert.deepEqual(parseSchemaFields(undefined), []);
assert.deepEqual(parseSchemaFields({ type: "object" }), []);

console.log("json-schema self-check passed");
