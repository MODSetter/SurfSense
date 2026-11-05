import assert from "node:assert/strict";
import test from "node:test";

// Run with: pnpm exec tsx --test features/business-launch/business-launched.test.ts

import { isBusinessLaunched } from "./business-launched.mts";

test("only the exact string true turns the Business launch on", () => {
	assert.equal(isBusinessLaunched("true"), true);
	for (const value of [undefined, "", "false", "TRUE", "1", "yes", " true"]) {
		assert.equal(isBusinessLaunched(value), false, `${JSON.stringify(value)} must leave it off`);
	}
});
