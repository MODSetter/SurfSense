import path from "node:path";
import { expect, test as setup } from "@playwright/test";
import { acquireTestToken } from "./helpers/api/auth";

/**
 * One-time authentication setup. Acquires a bearer token for the seeded
 * e2e user (rate-limit-free /__e2e__/auth/token first, /auth/jwt/login
 * fallback) and persists it via localStorage so every test in the
 * chromium project starts already authenticated.
 */

const authFile = path.join(__dirname, "..", "playwright", ".auth", "user.json");

const STORAGE_KEY = "surfsense_bearer_token";

setup("authenticate", async ({ page, request }) => {
	const access_token = await acquireTestToken(request);
	expect(access_token, "Failed to acquire e2e bearer token").toBeTruthy();

	await page.addInitScript(
		({ key, token }) => {
			localStorage.setItem(key, token);
		},
		{ key: STORAGE_KEY, token: access_token }
	);

	// Use a public page so the init script can write localStorage without
	// racing the dashboard auth redirect.
	await page.goto("/login", { waitUntil: "domcontentloaded" });

	await page.context().storageState({ path: authFile });
});
