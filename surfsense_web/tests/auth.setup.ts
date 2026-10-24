import path from "node:path";
import { expect, test as setup } from "@playwright/test";
import { acquireTestToken } from "./helpers/api/auth";

/**
 * One-time authentication setup. Acquires an access token for the seeded
 * e2e user (rate-limit-free /__e2e__/auth/token first, desktop login
 * fallback) and persists it as the session cookie so every test in the
 * chromium project starts already authenticated.
 *
 * Also pre-seeds `surfsense-tour-<userId>` so the OnboardingTour spotlight
 * for new users never intercepts clicks in journeys.
 */

const authFile = path.join(__dirname, "..", "playwright", ".auth", "user.json");

const PORT = process.env.PORT || "3000";
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || `http://localhost:${PORT}`;
const SESSION_COOKIE_NAME = process.env.SESSION_COOKIE_NAME || "surfsense_session";

/** Decode the user id (`sub`) from a JWT without verifying the signature. */
function decodeUserId(token: string): string | null {
	try {
		const payload = token.split(".")[1];
		if (!payload) return null;
		const json = Buffer.from(payload, "base64").toString("utf8");
		const obj = JSON.parse(json) as { sub?: string };
		return obj.sub ?? null;
	} catch {
		return null;
	}
}

setup("authenticate", async ({ page, request }) => {
	const access_token = await acquireTestToken(request);
	expect(access_token, "Failed to acquire e2e bearer token").toBeTruthy();

	const userId = decodeUserId(access_token);

	await page.context().addCookies([
		{
			name: SESSION_COOKIE_NAME,
			value: access_token,
			url: BASE_URL,
			httpOnly: true,
			sameSite: "Lax",
		},
	]);

	await page.addInitScript(
		({ uid }) => {
			if (uid) {
				localStorage.setItem(`surfsense-tour-${uid}`, "true");
			}
		},
		{ uid: userId }
	);

	// Use a public page so the init script can write localStorage without
	// racing the dashboard auth redirect.
	await page.goto("/login", { waitUntil: "domcontentloaded" });

	await page.context().storageState({ path: authFile });
});
