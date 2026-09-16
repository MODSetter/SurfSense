// Linux dev: Chromium aborts if chrome-sandbox exists but is not root+setuid.
// A pnpm install cannot set that, and Ubuntu 24.04+ AppArmor also blocks the
// user-namespace fallback. Packaged builds are not launched through this script.
import { spawnSync } from "node:child_process"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const root = join(dirname(fileURLToPath(import.meta.url)), "..")
const cli = join(root, "node_modules", "electron-vite", "bin", "electron-vite.js")

const env = { ...process.env }
const args = [cli, "dev"]
if (process.platform === "linux") {
  env.ELECTRON_DISABLE_SANDBOX = "1"
  args.push("--", "--no-sandbox")
}

const result = spawnSync(process.execPath, args, {
  cwd: root,
  env,
  stdio: "inherit",
})
process.exit(result.status === null ? 1 : result.status)
