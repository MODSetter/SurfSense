import { defineConfig, devices } from "@playwright/test";

const PORT = process.env.PORT || "3000";
const BACKEND_PORT = process.env.BACKEND_PORT || "8000";
const baseURL = process.env.PLAYWRIGHT_BASE_URL || `http://localhost:${PORT}`;

/**
 * Playwright configuration for SurfSense web E2E tests.
 *
 * Tests live under `tests/` and are NEVER bundled into the production Next.js
 * build (`.next/standalone/`) or the Electron desktop build, because:
 *   - This file and `tests/` are listed in `.dockerignore`.
 *   - `electron-builder.yml` only ships `.next/standalone/`, not source files.
 *   - `@playwright/test` is a `devDependency`, so production `pnpm install`
 *     with `--prod` skips it entirely.
 *
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
	testDir: "./tests",
	timeout: 30_000,
	expect: { timeout: 15_000 },
	fullyParallel: true,
	forbidOnly: !!process.env.CI,
	retries: process.env.CI ? 2 : 0,
	workers: process.env.CI ? 1 : undefined,
	reporter: process.env.CI
		? [["html", { open: "never" }], ["github"], ["list"]]
		: [["html", { open: "on-failure" }], ["list"]],
	use: {
		baseURL,
		trace: "on-first-retry",
		screenshot: "only-on-failure",
		video: process.env.CI ? "off" : "retain-on-failure",
		extraHTTPHeaders: {
			"x-playwright-test": "true",
		},
	},
	projects: [
		{
			name: "setup",
			testMatch: /.*\.setup\.ts/,
		},
		{
			name: "chromium",
			dependencies: ["setup"],
			use: {
				...devices["Desktop Chrome"],
				storageState: "playwright/.auth/user.json",
			},
		},
	],
	webServer: process.env.PLAYWRIGHT_NO_WEB_SERVER
		? undefined
		: {
				// Pin to webpack dev (Turbopack has caused stale-lock panics in E2E).
				command: "pnpm exec next dev",
				url: `http://localhost:${PORT}`,
				reuseExistingServer: !process.env.CI,
				timeout: 180_000,
				env: {
					NEXT_PUBLIC_FASTAPI_BACKEND_URL: `http://localhost:${BACKEND_PORT}`,
					NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE: "LOCAL",
				},
			},
});
