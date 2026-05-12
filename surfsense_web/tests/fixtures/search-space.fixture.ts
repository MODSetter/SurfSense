import { test as base } from "@playwright/test";
import { loginAsTestUser } from "../helpers/api/auth";
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

export const searchSpaceFixtures = base.extend<SearchSpaceFixtures, { apiTokenWorker: string }>({
	apiTokenWorker: [
		async ({ playwright }, use) => {
			const ctx = await playwright.request.newContext();
			try {
				const token = await loginAsTestUser(ctx);
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
