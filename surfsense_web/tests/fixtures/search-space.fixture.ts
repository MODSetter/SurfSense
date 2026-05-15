import fs from "node:fs";
import path from "node:path";
import { test as base } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import {
	createSearchSpace,
	deleteSearchSpace,
	type SearchSpaceRow,
} from "../helpers/api/search-spaces";
import { uniqueSearchSpaceName } from "../helpers/canary";

export type SearchSpaceFixtures = {
	/**
	 * Bearer token for the seeded test user. Worker-scoped so we only
	 * log in once per worker (logins are cheap, but caching is cheaper).
	 */
	apiToken: string;
	/**
	 * A fresh, named search space for the current test. Cleaned up
	 * automatically after the test finishes.
	 */
	searchSpace: SearchSpaceRow;
};

const STORAGE_KEY = "surfsense_bearer_token";

// Reuse the token written by tests/auth.setup.ts; on cache miss we
// mint a fresh one via /__e2e__/auth/token (rate-limit-free).
const AUTH_STATE_PATH = path.join(__dirname, "..", "..", "playwright", ".auth", "user.json");

function loadCachedBearerToken(): string | null {
	try {
		const raw = fs.readFileSync(AUTH_STATE_PATH, "utf8");
		const parsed = JSON.parse(raw) as {
			origins?: Array<{
				origin?: string;
				localStorage?: Array<{ name?: string; value?: string }>;
			}>;
		};
		for (const origin of parsed.origins ?? []) {
			for (const entry of origin.localStorage ?? []) {
				if (entry.name === STORAGE_KEY && entry.value) {
					return entry.value;
				}
			}
		}
	} catch {
		// Fall back to a fresh login.
	}
	return null;
}

export const searchSpaceFixtures = base.extend<SearchSpaceFixtures, { apiTokenWorker: string }>({
	apiTokenWorker: [
		async ({ playwright }, use) => {
			const cached = loadCachedBearerToken();
			if (cached) {
				await use(cached);
				return;
			}
			const ctx = await playwright.request.newContext();
			try {
				const token = await acquireTestToken(ctx);
				await use(token);
			} finally {
				await ctx.dispose();
			}
		},
		{ scope: "worker" },
	],
	apiToken: async ({ apiTokenWorker }, use) => {
		await use(apiTokenWorker);
	},
	searchSpace: async ({ request, apiToken }, use) => {
		const space = await createSearchSpace(
			request,
			apiToken,
			uniqueSearchSpaceName("composio-drive-e2e")
		);
		try {
			await use(space);
		} finally {
			await deleteSearchSpace(request, apiToken, space.id);
		}
	},
});
