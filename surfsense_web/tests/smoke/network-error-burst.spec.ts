import { expect, test } from "../fixtures";

/**
 * One network blip should cost the user one error, not a stack of them.
 *
 * A dashboard load fans out roughly ten parallel backend GETs. When the
 * connection drops for a moment every one of them fails with the same
 * `NetworkError`, and each failed query independently calls `showErrorToast`,
 * so the user gets a column of identical red toasts describing a single event.
 * PostHog measured 8.4 error captures per affected session across 5.2
 * endpoints, all within the same second.
 *
 * These specs pin the two halves of that: a transient blip should end up
 * costing nothing because TanStack Query already retries, and a sustained
 * outage should surface exactly one toast rather than one per endpoint.
 */

const TOAST = "[data-sonner-toast]";
const NETWORK_MESSAGE = /Unable to connect to the server/i;

/**
 * `llm-setup-status` gates the whole shell behind a full-page error card, so
 * failing it would hide the very toasts under test. Let it through and break
 * only the data queries that render behind it.
 */
const GATING_PATHS = ["/llm-setup-status", "/auth/session", "/zero/"];

function isGating(url: string): boolean {
	return GATING_PATHS.some((path) => url.includes(path));
}

test.describe("Network error burst", () => {
	test("a sustained outage shows one error, not one per endpoint", async ({ page, workspace }) => {
		await page.route("**/api/v1/**", async (route) => {
			if (isGating(route.request().url()) || route.request().method() !== "GET") {
				return route.continue();
			}
			return route.abort("connectionfailed");
		});

		await page.goto(`/dashboard/${workspace.id}/new-chat`);

		const toasts = page.locator(TOAST).filter({ hasText: NETWORK_MESSAGE });
		await expect(toasts.first()).toBeVisible();
		// Let the whole fan-out settle, including TanStack's retry backoff, so
		// this counts the steady state rather than whichever toast landed first.
		await page.waitForTimeout(8_000);

		expect(await toasts.count()).toBe(1);
	});

	test("a blip that recovers on retry is never shown to the user", async ({ page, workspace }) => {
		const failedOnce = new Set<string>();

		await page.route("**/api/v1/**", async (route) => {
			const url = route.request().url();
			if (isGating(url) || route.request().method() !== "GET" || failedOnce.has(url)) {
				return route.continue();
			}
			failedOnce.add(url);
			return route.abort("connectionfailed");
		});

		await page.goto(`/dashboard/${workspace.id}/new-chat`);
		await page.waitForTimeout(8_000);

		const toasts = page.locator(TOAST).filter({ hasText: NETWORK_MESSAGE });
		expect(await toasts.count()).toBe(0);
	});
});
