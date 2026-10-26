import assert from "node:assert/strict";
import test from "node:test";

// Run with: pnpm exec tsx --test features/celebration/celebrate-once.test.ts

import { celebrateOnce } from "./celebrate-once";

function memoryStorage() {
	const items = new Map<string, string>();
	return {
		getItem: (key: string) => items.get(key) ?? null,
		setItem: (key: string, value: string) => {
			items.set(key, value);
		},
	};
}

function counter() {
	let calls = 0;
	return {
		fire: () => {
			calls += 1;
		},
		get calls() {
			return calls;
		},
	};
}

test("a checkout is celebrated once, however often its page downloads the file", () => {
	const storage = memoryStorage();
	const burst = counter();

	celebrateOnce("cs_test_1", { storage, fire: burst.fire });
	celebrateOnce("cs_test_1", { storage, fire: burst.fire });

	assert.equal(burst.calls, 1);
});

test("another checkout is celebrated too", () => {
	const storage = memoryStorage();
	const burst = counter();

	celebrateOnce("cs_test_1", { storage, fire: burst.fire });
	celebrateOnce("cs_test_2", { storage, fire: burst.fire });

	assert.equal(burst.calls, 2);
});

test("a browser that refuses storage still celebrates, and nothing throws", () => {
	const refusing = {
		getItem: () => {
			throw new Error("storage blocked");
		},
		setItem: () => {
			throw new Error("storage blocked");
		},
	};
	const burst = counter();

	celebrateOnce("cs_test_1", { storage: refusing, fire: burst.fire });

	assert.equal(burst.calls, 1);
});
