/**
 * Runnable self-check for the playground CSV serializer. No test framework —
 * run with: ``npx tsx lib/playground/csv.selfcheck.ts``
 * Exits non-zero on the first failed assertion.
 */
import assert from "node:assert/strict";
import { rowsToCsv } from "./csv";

// Union of keys, stable order, header + rows joined with CRLF.
assert.equal(
	rowsToCsv([
		{ a: 1, b: "x" },
		{ a: 2, c: true },
	]),
	"a,b,c\r\n1,x,\r\n2,,true"
);

// Explicit columns fix order and subset.
assert.equal(rowsToCsv([{ a: 1, b: 2, c: 3 }], ["c", "a"]), "c,a\r\n3,1");

// RFC 4180 quoting: commas, quotes, and newlines.
assert.equal(rowsToCsv([{ v: 'he said "hi", bye' }]), 'v\r\n"he said ""hi"", bye"');
assert.equal(rowsToCsv([{ v: "line1\nline2" }]), 'v\r\n"line1\nline2"');

// Objects/arrays are JSON-stringified (then quoted for the comma).
assert.equal(rowsToCsv([{ v: { k: 1 } }]), 'v\r\n"{""k"":1}"');

// Null/undefined become empty cells.
assert.equal(rowsToCsv([{ v: null }]), "v\r\n");

// Formula-injection guard: dangerous leads get a ' prefix, real numbers don't.
assert.equal(rowsToCsv([{ v: "=1+2" }]), "v\r\n'=1+2");
assert.equal(rowsToCsv([{ v: "+1-800" }]), "v\r\n'+1-800");
assert.equal(rowsToCsv([{ v: "@handle" }]), "v\r\n'@handle");
assert.equal(rowsToCsv([{ v: "-cmd" }]), "v\r\n'-cmd");
assert.equal(rowsToCsv([{ v: "-5" }]), "v\r\n-5");
assert.equal(rowsToCsv([{ v: -5 }]), "v\r\n-5");

// Header only when there are no rows.
assert.equal(rowsToCsv([], ["a", "b"]), "a,b");

console.log("csv.selfcheck: all assertions passed");
