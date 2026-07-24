import assert from "node:assert/strict";
import { test } from "node:test";
import { AppError } from "@/lib/error";
import { fieldErrorsFromError } from "./field-errors";

// Run with: pnpm exec tsx --test lib/playground/field-errors.test.ts

function validationError(fields: { loc: string[]; msg: string }[]): AppError {
	const error = new AppError("Validation failed", 422, "Unprocessable Entity", "VALIDATION_ERROR");
	error.fields = fields;
	return error;
}

test("maps a body field failure to its top-level field name", () => {
	const error = validationError([
		{ loc: ["body", "startUrls", "0"], msg: "must be a valid http(s) URL" },
	]);
	assert.deepEqual(fieldErrorsFromError(error), {
		startUrls: "must be a valid http(s) URL",
	});
});

test("keeps the first failure per field", () => {
	const error = validationError([
		{ loc: ["body", "urls", "0"], msg: "first" },
		{ loc: ["body", "urls", "3"], msg: "second" },
	]);
	assert.deepEqual(fieldErrorsFromError(error), { urls: "first" });
});

test("returns nothing for non-AppError or errors without fields", () => {
	assert.deepEqual(fieldErrorsFromError(new Error("boom")), {});
	assert.deepEqual(fieldErrorsFromError(new AppError("no fields", 500)), {});
});
