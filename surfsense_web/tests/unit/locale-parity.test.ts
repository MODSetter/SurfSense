import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

// Run with: pnpm exec tsx --test tests/unit/locale-parity.test.ts

const MESSAGES = join(process.cwd(), "messages");

function keyPaths(value: unknown, prefix = ""): string[] {
	if (typeof value !== "object" || value === null) return [prefix];

	return Object.entries(value).flatMap(([key, child]) =>
		keyPaths(child, prefix ? `${prefix}.${key}` : key)
	);
}

function load(locale: string): string[] {
	return keyPaths(JSON.parse(readFileSync(join(MESSAGES, `${locale}.json`), "utf8")));
}

test("every locale carries every key English has", () => {
	// A key missing from a locale renders as its own dotted path to users.
	const english = new Set(load("en"));

	for (const file of readdirSync(MESSAGES)) {
		const locale = file.replace(/\.json$/, "");
		if (locale === "en") continue;

		const translated = new Set(load(locale));
		const missing = [...english].filter((key) => !translated.has(key));
		const unknown = [...translated].filter((key) => !english.has(key));

		assert.deepEqual(missing, [], `${locale}.json is missing keys`);
		assert.deepEqual(unknown, [], `${locale}.json has keys en.json does not`);
	}
});
