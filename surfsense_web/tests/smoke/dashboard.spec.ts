import { expect, test } from "@playwright/test";

/**
 * Tracer-bullet smoke test: proves the entire E2E pipeline is wired up.
 *
 * Verifies:
 *   - Web server is reachable
 *   - tests/auth.setup.ts ran and stored a valid bearer token
 *   - Dashboard route renders for an authenticated user
 *
 * Keep minimal. Connector- or feature-specific behaviour belongs under
 * tests/connectors/ or tests/<feature>/.
 */
test.describe("Smoke", () => {
	test("dashboard loads for authenticated user", async ({ page }) => {
		await page.goto("/dashboard");

		// Sidebar is <aside> (role=complementary); its visibility implies redirect + auth fetch.
		await expect(page.getByRole("complementary").first()).toBeVisible({ timeout: 60_000 });
	});
});
