import { defineConfig } from "electron-vite"

// No renderer entry: the renderer is the sibling `frontend/` Vite project,
// loaded by the main process as an external URL (dev) or built dist (packaged).
export default defineConfig({
  main: {},
  preload: {},
})
