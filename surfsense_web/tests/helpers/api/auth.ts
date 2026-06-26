import type { APIRequestContext } from "@playwright/test";

/**
 * Direct backend auth helper. Uses the desktop login endpoint when the
 * rate-limit-free e2e mint endpoint is unavailable.
 *
 * Returns a bearer token specs can attach to API calls when they don't
 * want to go through the browser. The browser-side auth (cookie storage)
 * is set up separately by tests/auth.setup.ts.
 */

export const BACKEND_URL = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";

const TEST_USER_EMAIL = process.env.PLAYWRIGHT_TEST_EMAIL || "e2e-test@surfsense.net";
const TEST_USER_PASSWORD = process.env.PLAYWRIGHT_TEST_PASSWORD || "E2eTestPassword123!";
const E2E_MINT_SECRET = process.env.E2E_MINT_SECRET || "local-e2e-mint-secret-not-for-production";

/**
 * Mints a JWT for the seeded e2e user via the test-only endpoint mounted
 * by surfsense_backend/tests/e2e/run_backend.py. Bypasses the production
 * desktop login rate limit, so it's safe to call from any
 * worker / retry. Returns 404 from the backend when the endpoint isn't
 * mounted (i.e. someone is pointing the suite at a non-e2e backend).
 */
export async function mintTestToken(
	request: APIRequestContext,
	email: string = TEST_USER_EMAIL
): Promise<string> {
	const response = await request.post(`${BACKEND_URL}/__e2e__/auth/token`, {
		data: { email },
		headers: {
			"Content-Type": "application/json",
			"X-E2E-Mint-Secret": E2E_MINT_SECRET,
		},
	});
	if (!response.ok()) {
		throw new Error(
			`Mint token at ${BACKEND_URL}/__e2e__/auth/token failed (${response.status()}): ${await response.text()}`
		);
	}
	const { access_token } = (await response.json()) as { access_token: string };
	if (!access_token) {
		throw new Error("Mint response missing access_token");
	}
	return access_token;
}

export async function loginAsTestUser(request: APIRequestContext): Promise<string> {
	const response = await request.post(`${BACKEND_URL}/auth/desktop/login`, {
		data: {
			email: TEST_USER_EMAIL,
			password: TEST_USER_PASSWORD,
		},
		headers: { "Content-Type": "application/json" },
	});

	if (!response.ok()) {
		throw new Error(
			`Login to ${BACKEND_URL}/auth/desktop/login failed (${response.status()}): ${await response.text()}`
		);
	}

	const { access_token } = (await response.json()) as { access_token: string };
	if (!access_token) {
		throw new Error("Backend response missing access_token");
	}
	return access_token;
}

/**
 * Get a bearer token by trying the rate-limit-free mint endpoint first
 * and falling back to /auth/desktop/login if the e2e endpoint isn't mounted
 * (e.g. running against a non-e2e backend in local dev).
 */
export async function acquireTestToken(request: APIRequestContext): Promise<string> {
	try {
		return await mintTestToken(request);
	} catch (err) {
		const msg = err instanceof Error ? err.message : String(err);
		if (msg.includes("(404)") || msg.includes("(405)")) {
			return loginAsTestUser(request);
		}
		throw err;
	}
}

/**
 * Standard auth headers for backend API calls. Optionally injects an
 * X-E2E-Scenario header that the test-only ScenarioMiddleware in
 * surfsense_backend/tests/e2e/run_backend.py reads to flip fake behavior.
 */
export function authHeaders(token: string, extra?: Record<string, string>): Record<string, string> {
	return {
		Authorization: `Bearer ${token}`,
		"Content-Type": "application/json",
		...(extra ?? {}),
	};
}
