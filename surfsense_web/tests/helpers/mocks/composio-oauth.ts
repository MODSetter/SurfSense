import type { Page } from "@playwright/test";

/**
 * Frontend route mock for the Composio OAuth redirect.
 *
 * In normal E2E runs we DON'T need this: the backend Composio fake
 * returns a same-origin auth_url that lands directly on our callback,
 * so the browser never navigates to composio.dev.
 *
 * Reserved here for future negative tests that intentionally exercise
 * a tampered/external auth_url (e.g. validating that the frontend
 * doesn't blindly follow off-origin redirects).
 */
export async function mockComposioOAuthRedirect(
	page: Page,
	options: { rewriteTo: string }
): Promise<void> {
	await page.route(/composio\.dev/, async (route) => {
		await route.fulfill({
			status: 302,
			headers: { Location: options.rewriteTo },
			body: "",
		});
	});
}
