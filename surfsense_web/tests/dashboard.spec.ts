import { expect, test } from "@playwright/test";

/**
 * Tracer-bullet test: proves the entire E2E pipeline works end-to-end.
 *
 * Verifies:
 *   - Web server is reachable
 *   - Auth setup ran successfully (storageState contains valid token)
 *   - Dashboard route renders for an authenticated user
 *
 * Keep this test minimal. Product-specific behaviour belongs in dedicated
 * spec files (new-chat, search-spaces, editor-panel, etc.).
 */
test.describe("Dashboard", () => {
	test("loads dashboard with sidebar navigation for authenticated user", async ({ page }) => {
		await page.goto("/dashboard");

		await expect(page).toHaveURL(/\/dashboard/);
		await expect(page.getByRole("navigation").first()).toBeVisible();
	});
});
