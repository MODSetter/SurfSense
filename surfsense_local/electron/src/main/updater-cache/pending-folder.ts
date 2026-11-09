import { readFileSync } from "node:fs"
import { homedir } from "node:os"
import { join } from "node:path"

export type CacheRoot = {
  platform: NodeJS.Platform
  env: Record<string, string | undefined>
  home: string
}

const here: CacheRoot = { platform: process.platform, env: process.env, home: homedir() }

/**
 * The folder electron-updater 6.8.9 downloads an update into: app-update.yml's
 * updaterCacheDirName under its per-user cache root (AppAdapter.getAppCacheDir).
 * Null when the build names no plain folder, so nothing outside it is ever touched.
 */
export function updaterPendingFolder(
  resourcesPath: string,
  root: CacheRoot = here
): string | null {
  let yml: string
  try {
    yml = readFileSync(join(resourcesPath, "app-update.yml"), "utf8")
  } catch {
    return null
  }
  const name = yml
    .match(/^updaterCacheDirName:[ \t]*(.*)$/m)?.[1]
    ?.trim()
    .replace(/^(['"])(.*)\1$/, "$2")
  if (!name || !/^[\w.-]+$/.test(name) || /^\.+$/.test(name)) return null
  return join(cacheRoot(root), name, "pending")
}

function cacheRoot({ platform, env, home }: CacheRoot): string {
  if (platform === "win32") return env.LOCALAPPDATA || join(home, "AppData", "Local")
  if (platform === "darwin") return join(home, "Library", "Caches")
  return env.XDG_CACHE_HOME || join(home, ".cache")
}
