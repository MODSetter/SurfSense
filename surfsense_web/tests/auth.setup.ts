import path from "node:path";
import { expect, test as setup } from "@playwright/test";

/**
 * One-time authentication setup. Logs in via the FastAPI backend directly
 * (skipping the UI) and persists the resulting localStorage token so every
 * test in the chromium project starts already authenticated.
 *
 * Mirrors the real auth flow in `lib/apis/auth-api.service.ts`:
 *   POST /auth/jwt/login  ->  { access_token }
 *   localStorage.setItem("surfsense_bearer_token", access_token)
 *
 * Requires a seeded test user in the dev/test DB. Configure via env:
 *   PLAYWRIGHT_TEST_EMAIL, PLAYWRIGHT_TEST_PASSWORD
 *   NEXT_PUBLIC_FASTAPI_BACKEND_URL  (defaults to http://localhost:8000)
 */

const authFile = path.join(__dirname, "..", "playwright", ".auth", "user.json");

const TEST_USER_EMAIL = process.env.PLAYWRIGHT_TEST_EMAIL || "test@surfsense.test";
const TEST_USER_PASSWORD = process.env.PLAYWRIGHT_TEST_PASSWORD || "TestPassword123!";
const BACKEND_URL = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";
const STORAGE_KEY = "surfsense_bearer_token";

setup("authenticate", async ({ page, request }) => {
	const response = await request.post(`${BACKEND_URL}/auth/jwt/login`, {
		form: {
			username: TEST_USER_EMAIL,
			password: TEST_USER_PASSWORD,
			grant_type: "password",
		},
		headers: { "Content-Type": "application/x-www-form-urlencoded" },
	});

	expect(
		response.ok(),
		`Login to ${BACKEND_URL}/auth/jwt/login failed (${response.status()}). ` +
			`Check that the backend is running and that PLAYWRIGHT_TEST_EMAIL ` +
			`(${TEST_USER_EMAIL}) is seeded with PLAYWRIGHT_TEST_PASSWORD. ` +
			`Body: ${await response.text()}`
	).toBeTruthy();

	const { access_token } = (await response.json()) as { access_token: string };
	expect(access_token, "Backend response missing access_token").toBeTruthy();

	await page.addInitScript(
		({ key, token }) => {
			localStorage.setItem(key, token);
		},
		{ key: STORAGE_KEY, token: access_token }
	);

	await page.goto("/dashboard");
	await expect(page).toHaveURL(/\/dashboard/);

	await page.context().storageState({ path: authFile });
});
