import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
	plugins: [react()],
	test: {
		environment: "jsdom",
		globals: true,
		setupFiles: ["./tests/setup.tsx"],
		include: ["./tests/**/*.{test,spec}.{ts,tsx}"],
		exclude: ["node_modules", ".next", "out"],
		coverage: {
			provider: "v8",
			reporter: ["text", "json", "html", "lcov"],
			include: ["lib/**/*.{ts,tsx}", "hooks/**/*.{ts,tsx}"],
			exclude: ["**/*.d.ts", "**/*.test.{ts,tsx}", "**/node_modules/**"],
		},
		testTimeout: 10000,
	},
	css: {
		// Disable PostCSS for tests
		postcss: {},
	},
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "./"),
		},
	},
});
