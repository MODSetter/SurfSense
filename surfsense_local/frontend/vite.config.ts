import { fileURLToPath, URL } from "node:url"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig({
  // Relative asset paths so the packaged SPA loads over file:// (Electron loadFile).
  base: "./",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/llm": "http://127.0.0.1:8000",
      "/workspaces": "http://127.0.0.1:8000",
      "/chat": "http://127.0.0.1:8000",
    },
  },
})
