import type { APIRequestContext } from "@playwright/test";

/**
 * Direct backend auth helper. Uses the same /auth/jwt/login endpoint the
 * UI uses; mirrors lib/apis/auth-api.service.ts.
 *
 * Returns a bearer token specs can attach to API calls when they don't
 * want to go through the browser. The browser-side auth (localStorage)
 * is set up separately by tests/auth.setup.ts.
 */

export const BACKEND_URL = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";

const TEST_USER_EMAIL = process.env.PLAYWRIGHT_TEST_EMAIL || "test@surfsense.net";
const TEST_USER_PASSWORD = process.env.PLAYWRIGHT_TEST_PASSWORD || "TestPassword123!";

export async function loginAsTestUser(request: APIRequestContext): Promise<string> {
	const response = await request.post(`${BACKEND_URL}/auth/jwt/login`, {
		form: {
			username: TEST_USER_EMAIL,
			password: TEST_USER_PASSWORD,
			grant_type: "password",
		},
		headers: { "Content-Type": "application/x-www-form-urlencoded" },
	});

	if (!response.ok()) {
		throw new Error(
			`Login to ${BACKEND_URL}/auth/jwt/login failed (${response.status()}): ${await response.text()}`
		);
	}

	const { access_token } = (await response.json()) as { access_token: string };
	if (!access_token) {
		throw new Error("Backend response missing access_token");
	}
	return access_token;
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
