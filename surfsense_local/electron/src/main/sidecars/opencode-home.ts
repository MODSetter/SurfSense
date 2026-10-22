/**
 * opencode's home inside SurfSense's agent folder: its settings, sessions and
 * caches, kept apart from any opencode the user runs on their own.
 */
import { mkdirSync, rmSync } from "node:fs"
import { join } from "node:path"

/** The folders opencode finds through HOME, the four XDG variables and the temp ones. */
export function opencodeFolders(agentDir: string): {
  home: string
  config: string
  data: string
  cache: string
  state: string
  temp: string
} {
  const home = join(agentDir, "opencode")
  return {
    home,
    config: join(home, "config"),
    data: join(home, "data"),
    cache: join(home, "cache"),
    state: join(home, "state"),
    temp: join(home, "temp"),
  }
}

/**
 * Create the folders, the temp one emptied: nothing runs from it before opencode
 * starts, and Bun leaves 5.6 MB in it at every start on Windows.
 */
export function prepareOpencodeHome(agentDir: string): void {
  const folders = opencodeFolders(agentDir)
  rmSync(folders.temp, { recursive: true, force: true })
  for (const folder of [folders.config, folders.data, folders.cache, folders.state, folders.temp]) {
    mkdirSync(folder, { recursive: true })
  }
}
