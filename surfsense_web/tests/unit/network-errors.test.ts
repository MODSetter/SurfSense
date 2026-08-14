import assert from "node:assert/strict";
import test from "node:test";

import { shouldRetry } from "@/lib/auth-errors";
import { AppError, AuthenticationError, NetworkError, NotFoundError } from "@/lib/error";
import { shouldRetryQuery } from "@/lib/query-client/retry";

// Run with: pnpm exec tsx --test tests/unit/network-errors.test.ts

test("a network failure offers the user a retry", () => {
	// register/page.tsx passes `err.message`, not `err.code`, so the retry
	// affordance only appears if the sentence itself is recognised.
	const network = new NetworkError(
		"Unable to connect to the server. Check your internet connection and try again."
	);

	assert.equal(shouldRetry(network.message), true);
	assert.equal(shouldRetry(network.code ?? ""), true);
});

test("a rejected password does not offer a retry", () => {
	assert.equal(shouldRetry("REGISTER_USER_ALREADY_EXISTS"), false);
	assert.equal(shouldRetry("Password should be at least 8 characters"), false);
});

test("queries retry transient failures", () => {
	const network = new NetworkError("Unable to connect to the server.");
	const serverFault = new AppError("Something went wrong", 500, "Internal Server Error");

	assert.equal(shouldRetryQuery(0, network), true);
	assert.equal(shouldRetryQuery(0, serverFault), true);
});

test("queries give up rather than hammering a failing endpoint", () => {
	const network = new NetworkError("Unable to connect to the server.");

	assert.equal(shouldRetryQuery(2, network), false);
});

test("queries never retry an answer the server meant", () => {
	// Retrying these delays the redirect or the error the user needs to see,
	// and cannot change the outcome.
	assert.equal(shouldRetryQuery(0, new AuthenticationError("Please login again.", 401)), false);
	assert.equal(shouldRetryQuery(0, new NotFoundError("Resource not found", 404)), false);
	assert.equal(shouldRetryQuery(0, new AppError("Forbidden", 403)), false);
});
