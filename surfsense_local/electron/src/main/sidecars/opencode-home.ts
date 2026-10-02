/**
 * opencode's home inside SurfSense's agent folder: its settings, sessions and
 * caches, kept apart from any opencode the user runs on their own.
 */
import { existsSync, mkdirSync, writeFileSync } from "node:fs"
import { join } from "node:path"

/** The folders opencode finds through HOME and the four XDG variables. */
export function opencodeFolders(agentDir: string): {
  home: string
  config: string
  data: string
  cache: string
  state: string
} {
  const home = join(agentDir, "opencode")
  return {
    home,
    config: join(home, "config"),
    data: join(home, "data"),
    cache: join(home, "cache"),
    state: join(home, "state"),
  }
}

/**
 * Create the folders, and keep opencode from reaching npm for its plugin package.
 *
 * At startup opencode installs `@opencode-ai/plugin` into its config folder
 * unless the folder holds a `node_modules` and a lockfile naming the package.
 * No plugin ever loads (OPENCODE_PURE), so the package itself is never needed.
 */
export function prepareOpencodeHome(agentDir: string): void {
  const folders = opencodeFolders(agentDir)
  for (const folder of [folders.config, folders.data, folders.cache, folders.state]) {
    mkdirSync(folder, { recursive: true })
  }
  const configFolder = join(folders.config, "opencode")
  mkdirSync(join(configFolder, "node_modules"), { recursive: true })
  const lock = join(configFolder, "package-lock.json")
  if (existsSync(lock)) return
  const named = { "": { dependencies: { "@opencode-ai/plugin": "*" } } }
  writeFileSync(lock, JSON.stringify({ lockfileVersion: 3, packages: named }, null, 2))
}
