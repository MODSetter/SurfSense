/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url"
import formatjs from "@formatjs/unplugin/vite"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig({
  // Relative asset paths so the packaged SPA loads over file:// (Electron loadFile).
  base: "./",
  plugins: [
    // The catalogs supply every message, so the inline English is dropped from
    // the bundle; `formatjs extract` reads it from the source instead.
    formatjs({ removeDefaultMessage: true }),
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
      // Every message is precompiled to AST by `pnpm translations`, so the ICU
      // parser is dead weight at run time (FormatJS performance guide).
      "@formatjs/icu-messageformat-parser":
        "@formatjs/icu-messageformat-parser/no-parser.js",
    },
  },
  test: {
    setupFiles: ["./src/test-setup.ts"],
    // Dates in tests are UTC instants and the assertions spell out the day
    // (license-settings.test.tsx expects "Sep 10, 2027" for
    // 2027-09-10T00:00:00Z). Formatted in a machine's local zone west of
    // UTC that reads as the 9th, so the suite fails on a laptop and passes
    // in CI. Pin the zone tests run in instead of pinning every assertion.
    env: { TZ: "UTC" },
  },
  server: {
    host: "127.0.0.1",
    strictPort: true,
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/llm": "http://127.0.0.1:8000",
      "/workspaces": "http://127.0.0.1:8000",
      "/chat": "http://127.0.0.1:8000",
      "/artifacts": "http://127.0.0.1:8000",
    },
  },
})
